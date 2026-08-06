"use strict";

const { app, BrowserWindow, Menu, shell, dialog } = require("electron");
const path = require("node:path");
const { startBackend, stopBackend } = require("./backend");

const startupLog = [];
function log(line) {
  startupLog.push(line);
  if (startupLog.length > 400) startupLog.shift();
  console.log(line);
}

let mainWindow = null;
let splashWindow = null;
let backendUrl = null;
let quitting = false;

/**
 * A second launch would spawn a second backend against the same SQLite
 * database. Focus the existing window instead.
 *
 * `boot()` is registered only when the lock is held. Calling app.quit() on
 * its own is not enough: quit is asynchronous, so an unconditional
 * whenReady().then(boot) still fires first and spawns a backend process
 * that the quitting instance then abandons - an orphaned server holding a
 * port and the database file.
 *
 * The lock is app-wide, so this also stops a portable copy running
 * alongside an installed one. That is stricter than strictly necessary
 * (two portable folders have separate databases and could safely coexist),
 * but Electron scopes the lock per application, not per data directory.
 */
const hasSingleInstanceLock = app.requestSingleInstanceLock();

if (!hasSingleInstanceLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
}

function createSplash() {
  splashWindow = new BrowserWindow({
    width: 420,
    height: 300,
    frame: false,
    resizable: false,
    show: true,
    backgroundColor: "#0a0a0c",
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  });
  splashWindow.loadFile(path.join(__dirname, "splash.html"));
  splashWindow.on("closed", () => {
    splashWindow = null;
  });
}

function createMainWindow(url) {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 940,
    minHeight: 600,
    backgroundColor: "#0a0a0c",
    // Don't show until the page has painted - otherwise the user gets a
    // white flash and an empty frame while the first render happens.
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  mainWindow.loadURL(url);

  mainWindow.once("ready-to-show", () => {
    if (splashWindow) splashWindow.close();
    mainWindow.show();
    mainWindow.focus();
  });

  // Anything not served by our local backend belongs in the user's real
  // browser - an Electron window with no chrome is a bad place to land on
  // ollama.com, and worse for anything asking for credentials.
  const isInternal = (target) => target.startsWith(url) || target.startsWith(backendUrl || url);

  mainWindow.webContents.setWindowOpenHandler(({ url: target }) => {
    if (!isInternal(target)) {
      shell.openExternal(target);
      return { action: "deny" };
    }
    return { action: "allow" };
  });

  mainWindow.webContents.on("will-navigate", (event, target) => {
    if (!isInternal(target)) {
      event.preventDefault();
      shell.openExternal(target);
    }
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

function buildMenu() {
  const template = [
    {
      label: "File",
      submenu: [
        {
          label: "Open in Browser",
          click: () => backendUrl && shell.openExternal(backendUrl),
        },
        { type: "separator" },
        { role: "quit" },
      ],
    },
    {
      label: "View",
      submenu: [
        { role: "reload" },
        { role: "forceReload" },
        { type: "separator" },
        { role: "resetZoom" },
        { role: "zoomIn" },
        { role: "zoomOut" },
        { type: "separator" },
        { role: "togglefullscreen" },
        { role: "toggleDevTools" },
      ],
    },
    {
      label: "Help",
      submenu: [
        {
          label: "Show Startup Log",
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: "info",
              title: "Startup Log",
              message: "Backend startup output",
              detail: startupLog.slice(-40).join("\n") || "(no output)",
            });
          },
        },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

async function boot() {
  createSplash();
  buildMenu();

  try {
    const { url } = await startBackend({
      isPackaged: app.isPackaged,
      resourcesPath: process.resourcesPath,
      // Only meaningful for an installed build. In dev, app.getVersion()
      // returns the repo's package.json version, which says nothing about
      // what the user has installed - so don't pretend it does.
      appVersion: app.isPackaged ? app.getVersion() : null,
      // macOS keeps user data in ~/Library/Application Support rather
      // than beside the app - Electron resolves that path for us.
      userDataDir: app.getPath("userData"),
      onLog: log,
    });
    backendUrl = url;
    createMainWindow(url);
  } catch (err) {
    if (splashWindow) splashWindow.close();
    // Surface the backend's own output - the Python traceback is almost
    // always the actual answer, and it is otherwise invisible in a
    // packaged app with no console.
    dialog.showErrorBox(
      "MMA Assist could not start",
      `${err.message}\n\n--- Backend output ---\n${startupLog.slice(-25).join("\n")}`
    );
    app.quit();
  }
}

if (hasSingleInstanceLock) app.whenReady().then(boot);

// On Windows, closing the window means quitting. On macOS it does not: apps
// stay alive in the Dock with no windows open, and quitting on close would
// read as the app crashing. Keeping the process alive also keeps the backend
// warm, so re-opening is instant instead of another cold Python start.
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

// macOS: clicking the Dock icon with no windows open should reopen one.
// backendUrl is already known, so this skips straight past the splash and
// the health poll.
app.on("activate", () => {
  if (mainWindow === null && backendUrl && !quitting) createMainWindow(backendUrl);
});

// Every exit path funnels through here so the Python process can't outlive
// the window: quitting, closing the last window, or the OS logging out.
app.on("before-quit", () => {
  if (quitting) return;
  quitting = true;
  stopBackend();
});

process.on("exit", stopBackend);
process.on("SIGINT", () => {
  stopBackend();
  process.exit(0);
});
process.on("SIGTERM", () => {
  stopBackend();
  process.exit(0);
});
