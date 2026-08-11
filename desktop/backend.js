"use strict";

const { spawn } = require("node:child_process");
const net = require("node:net");
const http = require("node:http");
const path = require("node:path");
const fs = require("node:fs");

const READY_PREFIX = "UFC_PREDICTOR_READY";
const HEALTH_TIMEOUT_MS = 90_000;
const HEALTH_INTERVAL_MS = 250;

let child = null;

/**
 * Asks the OS for a free port by binding one and immediately releasing it.
 *
 * There is a small race between releasing and the backend binding, but it
 * beats a hard-coded 8765: that collides with a second copy of the app, an
 * unrelated dev server, or a leftover process from a crash - and the user
 * just sees a window that never loads.
 */
function getFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });
}

/**
 * Where the app keeps its data (SQLite + ChromaDB).
 *
 * Deliberately different per platform, because "portable" is a Windows
 * idea and forcing it onto macOS would be actively wrong:
 *
 *   1. An existing UFC_PREDICTOR_DATA_DIR always wins - that's how tests
 *      and dev runs point somewhere specific, and silently overriding it
 *      would make those unreproducible.
 *   2. macOS, packaged: ~/Library/Application Support (Electron's
 *      userData). See the note at the branch for why not beside the app.
 *   3. Windows, packaged: <folder containing the exe>/data, so the app and
 *      its data travel together and deleting the folder removes both.
 *   4. Anything else: null, and the backend falls back to its own default
 *      (platformdirs user data dir).
 *
 * Returns null rather than throwing when a location isn't usable. A user
 * who extracts into Program Files, a read-only share, or a mounted image
 * should still get a working app, not a startup failure - the data
 * re-seeds from the bundle, so nothing is lost.
 */
/**
 * True when this copy was put here by the NSIS installer rather than
 * extracted from the portable zip.
 *
 * There is no flag from electron-builder that distinguishes them: both
 * targets package the identical `win-unpacked` tree, so anything inside
 * resources/ is byte-for-byte the same. What the installer *does* leave
 * behind is its uninstaller, beside the exe. Matched loosely by pattern so
 * a change to electron-builder's naming doesn't silently flip every user
 * to a fresh data directory.
 */
function isInstalledBuild(appFolder) {
  try {
    return fs.readdirSync(appFolder).some((name) => /^unins.*\.exe$/i.test(name));
  } catch {
    return false;
  }
}

function resolveDataDir(isPackaged, userDataDir = null) {
  const explicit = process.env.UFC_PREDICTOR_DATA_DIR;
  if (explicit && explicit.trim()) return { dir: explicit, source: "environment" };

  if (!isPackaged) return { dir: null, source: "default (dev run)" };

  // macOS does not do portable. A packaged app is a signed .app bundle and
  // process.execPath points *inside* it (Contents/MacOS/...), so writing a
  // data folder beside the binary would put user data inside the bundle -
  // which breaks the code signature, is wiped by any update that replaces
  // the .app, and fails outright in /Applications for a non-admin user.
  // ~/Library/Application Support is the platform convention, and Electron
  // hands it to us as userData.
  if (process.platform === "darwin") {
    return { dir: userDataDir, source: "macOS (~/Library/Application Support)" };
  }

  // process.execPath is the Electron exe the user launched, so its parent is
  // the folder they extracted the app into. electron-builder's own portable
  // target exports PORTABLE_EXECUTABLE_DIR for the same purpose; honour it
  // first so both packaging styles land in the same place.
  const appFolder = process.env.PORTABLE_EXECUTABLE_DIR || path.dirname(process.execPath);
  const candidate = path.join(appFolder, "data");

  // An existing data folder beside the exe always wins, and is checked
  // before the installed-build test on purpose. This is the compatibility
  // guarantee for everyone already running the portable build: extracting a
  // newer zip over the old folder, or any future change to how "installed"
  // is detected, must never quietly point them at an empty directory and
  // re-seed. Their chats and predictions would still be on disk, but the
  // app would look like it had lost them.
  if (fs.existsSync(candidate)) {
    return { dir: candidate, source: "portable (existing data folder beside the app)" };
  }

  // Installed by NSIS: user data belongs in the profile, not in the install
  // directory, which the updater replaces wholesale on every update.
  if (isInstalledBuild(appFolder)) {
    return { dir: userDataDir, source: "installed (user profile)" };
  }

  try {
    fs.mkdirSync(candidate, { recursive: true });
    // mkdir can succeed on a read-only mount that only fails on write, so
    // prove writability rather than assuming it.
    const probe = path.join(candidate, ".write-test");
    fs.writeFileSync(probe, "");
    fs.unlinkSync(probe);
    return { dir: candidate, source: "portable (next to the app)" };
  } catch (err) {
    return { dir: null, source: `not writable at ${candidate} (${err.code}) - using AppData` };
  }
}

/**
 * Resolves how to launch the backend.
 *
 * Packaged: the PyInstaller build is copied in as an extraResource, so we
 * run the exe directly - there is no Python on the user's machine.
 * Dev: run run.py out of the backend virtualenv.
 */
function resolveCommand(isPackaged, resourcesPath) {
  if (isPackaged) {
    // PyInstaller drops the .exe suffix on POSIX.
    const binary = process.platform === "win32" ? "UFCPredictor.exe" : "UFCPredictor";
    const exe = path.join(resourcesPath, "backend", binary);
    if (!fs.existsSync(exe)) {
      throw new Error(
        `Packaged backend missing at ${exe}. Run \`pyinstaller pyinstaller/app.spec\` in backend/ before building.`
      );
    }
    return { command: exe, args: [], cwd: path.dirname(exe) };
  }

  const repoRoot = path.resolve(__dirname, "..");
  const backendDir = path.join(repoRoot, "backend");
  const venvPython =
    process.platform === "win32"
      ? path.join(backendDir, ".venv", "Scripts", "python.exe")
      : path.join(backendDir, ".venv", "bin", "python");
  const python = fs.existsSync(venvPython) ? venvPython : process.platform === "win32" ? "python" : "python3";

  return { command: python, args: [path.join(backendDir, "run.py")], cwd: backendDir };
}

function pollHealth(port, deadline) {
  return new Promise((resolve, reject) => {
    const attempt = () => {
      if (Date.now() > deadline) {
        reject(new Error("Backend did not become healthy in time"));
        return;
      }
      const req = http.get(
        { host: "127.0.0.1", port, path: "/health", timeout: 2000 },
        (res) => {
          res.resume();
          if (res.statusCode === 200) resolve();
          else setTimeout(attempt, HEALTH_INTERVAL_MS);
        }
      );
      req.on("error", () => setTimeout(attempt, HEALTH_INTERVAL_MS));
      req.on("timeout", () => {
        req.destroy();
        setTimeout(attempt, HEALTH_INTERVAL_MS);
      });
    };
    attempt();
  });
}

/**
 * Spawns the backend and resolves with its base URL once /health answers.
 *
 * `onLog` receives backend stdout/stderr lines so a failed start is
 * diagnosable - without it a Python traceback vanishes and the user just
 * gets "could not start".
 */
async function startBackend({
  isPackaged,
  resourcesPath,
  appVersion,
  userDataDir = null,
  onLog = () => {},
  beforeStart = null,
}) {
  const port = await getFreePort();
  const { command, args, cwd } = resolveCommand(isPackaged, resourcesPath);

  const { dir: dataDir, source: dataSource } = resolveDataDir(isPackaged, userDataDir);

  onLog(`Starting backend: ${command} ${args.join(" ")} (port ${port}, version ${appVersion || "dev"})`);
  onLog(`Data directory: ${dataDir || "%LOCALAPPDATA%"} [${dataSource}]`);

  // Hook for anything that must touch the data directory before SQLite and
  // the seed bootstrap do - currently the portable->installed import. Runs
  // here rather than in main.js so the directory is resolved exactly once.
  // A failure is logged, not fatal: a broken import must still leave a
  // working app.
  if (beforeStart) {
    try {
      await beforeStart({ dataDir, dataSource });
    } catch (err) {
      onLog(`beforeStart hook failed: ${err.message}`);
    }
  }

  // --app-version comes from Electron's own package.json, which is what
  // electron-builder stamps the installer with. Passing it down keeps one
  // source of truth: the backend never declares a version of its own, so
  // the two can't drift and report different numbers to the update check.
  const versionArgs = appVersion ? ["--app-version", appVersion] : [];

  const env = { ...process.env, UFC_PREDICTOR_NO_BROWSER: "1", PYTHONUNBUFFERED: "1" };
  if (dataDir) env.UFC_PREDICTOR_DATA_DIR = dataDir;

  child = spawn(command, [...args, "--port", String(port), "--no-browser", ...versionArgs], {
    cwd,
    env,
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });

  let exitInfo = null;
  child.stdout.on("data", (buf) => {
    const text = buf.toString();
    text.split(/\r?\n/).filter(Boolean).forEach((line) => onLog(line));
  });
  child.stderr.on("data", (buf) => {
    const text = buf.toString();
    text.split(/\r?\n/).filter(Boolean).forEach((line) => onLog(`[stderr] ${line}`));
  });

  const spawnFailed = new Promise((_resolve, reject) => {
    child.on("error", (err) => reject(new Error(`Could not launch the backend: ${err.message}`)));
    child.on("exit", (code, signal) => {
      exitInfo = { code, signal };
      // Only an error if it dies before we ever went healthy; a normal
      // shutdown resolves this promise's race long after it stopped mattering.
      reject(new Error(`Backend exited early (code ${code}${signal ? `, signal ${signal}` : ""})`));
    });
  });

  const healthy = pollHealth(port, Date.now() + HEALTH_TIMEOUT_MS);

  // Whichever settles first wins: a crash surfaces immediately instead of
  // making the user wait out the full health timeout.
  await Promise.race([healthy, spawnFailed]);

  if (exitInfo) throw new Error("Backend exited during startup");
  return { url: `http://127.0.0.1:${port}/`, port };
}

/**
 * Stops the backend. Electron's own exit does not reap child processes, so
 * skipping this leaves an orphaned Python server holding the SQLite file
 * and a port after every quit.
 */
function stopBackend() {
  if (!child || child.exitCode !== null || child.signalCode !== null) {
    child = null;
    return;
  }

  const pid = child.pid;
  const proc = child;
  child = null;

  if (process.platform === "win32") {
    // The PyInstaller exe is a process tree (bootloader -> real app), and
    // proc.kill() only signals the parent, orphaning the server underneath.
    // taskkill /T takes the whole tree with it.
    spawn("taskkill", ["/pid", String(pid), "/T", "/F"], { windowsHide: true, stdio: "ignore" });
    return;
  }

  proc.kill("SIGTERM");
  setTimeout(() => {
    if (proc.exitCode === null) proc.kill("SIGKILL");
  }, 4000);
}

/**
 * stopBackend(), but resolves only once the process has actually gone.
 *
 * stopBackend is fire-and-forget, which is fine when the whole app is
 * exiting anyway. It is NOT fine before an update installs: the NSIS
 * installer replaces resources/backend, and Windows refuses to overwrite a
 * running executable or its loaded DLLs. Handing control to the installer
 * while UFCPredictor.exe is still winding down produces a half-written
 * install, so the update path awaits this instead.
 *
 * Resolves rather than rejects on timeout - blocking the update forever
 * because a process took too long to die is worse than proceeding and
 * letting the installer report a locked file.
 */
function stopBackendAndWait(timeoutMs = 15000) {
  // Captured first: stopBackend() clears the module-level handle.
  const proc = child;
  stopBackend();

  if (!proc || proc.exitCode !== null || proc.signalCode !== null) return Promise.resolve();

  return new Promise((resolve) => {
    const finish = () => {
      clearTimeout(timer);
      resolve();
    };
    const timer = setTimeout(finish, timeoutMs);
    proc.once("exit", finish);
  });
}

module.exports = { startBackend, stopBackend, stopBackendAndWait, getFreePort, resolveDataDir };
