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
 * Resolves how to launch the backend.
 *
 * Packaged: the PyInstaller build is copied in as an extraResource, so we
 * run the exe directly - there is no Python on the user's machine.
 * Dev: run run.py out of the backend virtualenv.
 */
function resolveCommand(isPackaged, resourcesPath) {
  if (isPackaged) {
    const exe = path.join(resourcesPath, "backend", "UFCPredictor.exe");
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
async function startBackend({ isPackaged, resourcesPath, appVersion, onLog = () => {} }) {
  const port = await getFreePort();
  const { command, args, cwd } = resolveCommand(isPackaged, resourcesPath);

  onLog(`Starting backend: ${command} ${args.join(" ")} (port ${port}, version ${appVersion || "dev"})`);

  // --app-version comes from Electron's own package.json, which is what
  // electron-builder stamps the installer with. Passing it down keeps one
  // source of truth: the backend never declares a version of its own, so
  // the two can't drift and report different numbers to the update check.
  const versionArgs = appVersion ? ["--app-version", appVersion] : [];

  child = spawn(command, [...args, "--port", String(port), "--no-browser", ...versionArgs], {
    cwd,
    env: { ...process.env, UFC_PREDICTOR_NO_BROWSER: "1", PYTHONUNBUFFERED: "1" },
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

module.exports = { startBackend, stopBackend, getFreePort };
