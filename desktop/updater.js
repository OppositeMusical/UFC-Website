"use strict";

/**
 * In-app updates, wrapping electron-updater.
 *
 * Distribution model (see docs/SPEC.md section 13.2): Windows ships an NSIS
 * installer for the self-updating channel plus a portable zip for manual
 * users. electron-updater only supports NSIS on Windows - `zip` and
 * `portable` are not auto-updatable targets - so the portable build keeps
 * the old "open the download page" behaviour and reports `unsupported`
 * here.
 *
 * Two rules shape this file:
 *
 *  1. NOTHING here takes a URL, path, or version from the caller. The feed
 *     is pinned at build time by the `publish` block in package.json and
 *     baked into resources/app-update.yml. The renderer displays LLM output
 *     on the chat page, so an IPC method that accepted a download location
 *     would turn any future XSS into remote code execution. The renderer
 *     may say "go"; it may never say "go here".
 *
 *  2. The Python backend must be dead before the installer runs. Windows
 *     will not overwrite a running exe, and resources/backend is 294MB of
 *     exactly that.
 */

const { app } = require("electron");
const { autoUpdater } = require("electron-updater");

const { stopBackendAndWait } = require("./backend");

// Local-testing escape hatch: point at a directory served over HTTP that
// holds latest.yml + the installer, so the download/verify/install path can
// be exercised without cutting a real GitHub release for every attempt.
// Never set in a shipped build.
const ENV_FEED_OVERRIDE = "UFC_PREDICTOR_UPDATE_FEED";

let log = () => {};
let broadcast = () => {};
let configured = false;

/**
 * Last known state, replayed to any renderer that asks. A window opened
 * (or reloaded) mid-download must be able to render the current progress
 * rather than showing "idle" over a live transfer.
 */
let state = { status: "idle" };

function setState(next) {
  state = next;
  broadcast(state);
}

function isSupported() {
  // Dev runs have no app-update.yml, and checkForUpdates() throws rather
  // than returning a useful result. Say so instead of surfacing that error.
  return app.isPackaged;
}

/**
 * Turns an electron-updater error into something a user can act on.
 *
 * The signature case is the one that matters here. The app is signed with a
 * self-signed certificate, and electron-updater verifies the downloaded
 * installer's Authenticode signature against `win.publisherName`. On a
 * machine where the user never imported the certificate into Trusted Root,
 * that check fails - correctly, and it must keep failing - but the raw
 * message reads like a corrupt download, which invites exactly the wrong
 * response.
 */
function describeError(err) {
  const raw = (err && (err.message || String(err))) || "Unknown error";
  const lower = raw.toLowerCase();

  if (lower.includes("publisher") || lower.includes("signature") || lower.includes("not signed")) {
    return {
      message: "The update's signature could not be verified, so it was not installed.",
      hint:
        "MMA Assist is signed with a self-signed certificate. Install certs/code-signing.cer " +
        "into Trusted Root Certification Authorities (desktop/scripts/trust-cert.ps1), then " +
        "try again. If you did not expect this, do not install the update.",
      raw,
    };
  }
  if (lower.includes("enotfound") || lower.includes("enetunreach") || lower.includes("etimedout")) {
    return {
      message: "Could not reach the update server.",
      hint: "Check your internet connection and try again. The app works fine offline.",
      raw,
    };
  }
  if (lower.includes("404")) {
    return {
      message: "No published update was found.",
      hint: "The release may still be uploading. Try again shortly.",
      raw,
    };
  }
  return { message: "The update failed.", hint: raw, raw };
}

function configure() {
  if (configured) return;
  configured = true;

  // The user asks for the download explicitly; a 244MB transfer must not
  // start because someone opened Settings.
  autoUpdater.autoDownload = false;
  // We control installation, including tearing the backend down first.
  autoUpdater.autoInstallOnAppQuit = false;
  autoUpdater.logger = { info: log, warn: log, error: log, debug: () => {} };

  const feedOverride = process.env[ENV_FEED_OVERRIDE];
  if (feedOverride) {
    log(`[updater] feed overridden: ${feedOverride}`);
    autoUpdater.setFeedURL({ provider: "generic", url: feedOverride });
  }

  autoUpdater.on("checking-for-update", () => setState({ status: "checking" }));

  autoUpdater.on("update-available", (info) => {
    setState({
      status: "available",
      version: info.version,
      releaseNotes: normaliseNotes(info.releaseNotes),
      releasedAt: info.releaseDate || null,
      sizeBytes: totalSize(info),
    });
  });

  autoUpdater.on("update-not-available", (info) => {
    setState({ status: "not-available", version: info && info.version });
  });

  autoUpdater.on("download-progress", (p) => {
    setState({
      status: "downloading",
      percent: Math.max(0, Math.min(100, Math.round(p.percent || 0))),
      transferred: p.transferred,
      total: p.total,
      bytesPerSecond: p.bytesPerSecond,
    });
  });

  autoUpdater.on("update-downloaded", (info) => {
    setState({ status: "downloaded", version: info.version });
  });

  autoUpdater.on("error", (err) => {
    log(`[updater] error: ${err && err.stack ? err.stack : err}`);
    setState({ status: "error", ...describeError(err) });
  });
}

// electron-updater hands back either a string (often HTML from a GitHub
// release body) or an array of {version, note}. The renderer writes these
// with textContent, so the only job here is to get to plain lines.
function normaliseNotes(notes) {
  if (!notes) return [];
  if (Array.isArray(notes)) {
    return notes.map((n) => (typeof n === "string" ? n : n && n.note)).filter(Boolean);
  }
  if (typeof notes === "string") {
    return notes
      .replace(/<[^>]+>/g, "")
      .split(/\r?\n/)
      .map((line) => line.replace(/^\s*[-*]\s*/, "").trim())
      .filter(Boolean);
  }
  return [];
}

function totalSize(info) {
  if (!info || !Array.isArray(info.files)) return undefined;
  return info.files.reduce((sum, f) => sum + (f.size || 0), 0) || undefined;
}

function init({ onLog = () => {}, onState = () => {} } = {}) {
  log = onLog;
  broadcast = onState;
  if (!isSupported()) {
    state = {
      status: "unsupported",
      reason: app.isPackaged
        ? "This build does not support in-app updates."
        : "Development build - in-app updates are disabled.",
    };
  }
}

function getState() {
  return state;
}

async function check() {
  if (!isSupported()) return state;
  configure();
  try {
    await autoUpdater.checkForUpdates();
  } catch (err) {
    // The 'error' event usually fires too, but not on every throw path -
    // setting state here as well keeps the UI from hanging on "checking".
    setState({ status: "error", ...describeError(err) });
  }
  return state;
}

async function download() {
  if (!isSupported()) return state;
  configure();
  if (state.status !== "available") {
    // Nothing to fetch. Re-check rather than silently doing nothing, so a
    // stale window that missed the result still converges.
    await check();
    if (state.status !== "available") return state;
  }
  try {
    setState({ status: "downloading", percent: 0 });
    await autoUpdater.downloadUpdate();
  } catch (err) {
    setState({ status: "error", ...describeError(err) });
  }
  return state;
}

/**
 * Quits and hands over to the installer. Does not return on success.
 */
async function install() {
  if (!isSupported()) return state;
  if (state.status !== "downloaded") {
    return { status: "error", message: "No downloaded update is ready to install.", hint: "" };
  }

  log("[updater] stopping backend before handing over to the installer");
  await stopBackendAndWait();

  // isSilent=TRUE. This is not a preference - with `oneClick: false` the
  // NSIS build is an *assisted* installer, so a non-silent quitAndInstall
  // renders the full setup wizard and blocks on it. Verified by driving a
  // real 0.5.0 -> 0.5.1 update: the app quit, the installer launched, and
  // then sat waiting for someone to click Next. The user already consented
  // by pressing "Restart & Install"; making them click through setup again
  // is not self-updating, and if they close the wizard the app is simply
  // gone until they start it by hand.
  //
  // isForceRunAfter=true relaunches the new version when it finishes.
  setImmediate(() => autoUpdater.quitAndInstall(true, true));
  return { status: "installing" };
}

module.exports = { init, check, download, install, getState, isSupported, describeError, normaliseNotes };
