"use strict";

/**
 * Lets the pure logic in updater.js / datamigrate.js be tested outside
 * Electron.
 *
 * Both modules `require("electron")` at the top level, which throws in a
 * plain Node process. Intercepting the load is enough: the functions under
 * test here (error classification, release-note normalisation, source-folder
 * resolution) never touch the Electron APIs - they are the parts worth
 * unit-testing precisely because they are pure.
 *
 * Anything that genuinely drives autoUpdater or shows a dialog is left to
 * the manual install test in docs/SPEC.md section 13.3; mocking it here
 * would assert that the mock works, not that updates do.
 */
const Module = require("node:module");

const stub = {
  app: { isPackaged: false, getPath: () => "", getVersion: () => "0.0.0-test" },
  dialog: { showMessageBox: async () => ({ response: 1 }), showOpenDialog: async () => ({ canceled: true, filePaths: [] }) },
  ipcMain: { handle: () => {} },
  shell: { openExternal: () => {} },
  contextBridge: { exposeInMainWorld: () => {} },
  ipcRenderer: { invoke: async () => {}, on: () => {}, removeListener: () => {} },
  BrowserWindow: class {},
  Menu: { setApplicationMenu: () => {}, buildFromTemplate: () => {} },
};

const updaterStub = {
  autoUpdater: {
    on: () => {},
    setFeedURL: () => {},
    checkForUpdates: async () => {},
    downloadUpdate: async () => {},
    quitAndInstall: () => {},
  },
};

const originalLoad = Module._load;
Module._load = function patchedLoad(request, ...rest) {
  if (request === "electron") return stub;
  if (request === "electron-updater") return updaterStub;
  return originalLoad.call(this, request, ...rest);
};

module.exports = { stub, updaterStub };
