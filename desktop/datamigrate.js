"use strict";

/**
 * One-time data import when a portable user moves to the installed build.
 *
 * The portable build keeps everything in `data/` beside the exe. The
 * installed build keeps it in the user profile, because the NSIS updater
 * replaces the install directory wholesale on every update and anything
 * living there would be destroyed.
 *
 * That difference is correct but it strands the switcher: the installed
 * copy starts with an empty data directory, re-seeds the bundled fighter
 * database, and presents itself as a fresh install. The user's chats and
 * saved predictions are still on disk in the old folder - they just are not
 * where the app is looking, which is indistinguishable from data loss.
 *
 * So: offer, once, on the first run that finds an empty data directory.
 * Never guess and never copy silently - the source folder is chosen by the
 * user, and doing this without asking would be a surprising write.
 */

const { dialog } = require("electron");
const fs = require("node:fs");
const path = require("node:path");

// Everything the app writes, per app/config.py. chroma_db is a directory;
// the rest are files. Anything not listed here (logs, stray temp files) is
// deliberately left behind.
const PAYLOAD = ["ufc_predictor.db", "chroma_db", ".secrets.enc", ".secrets.key"];

// A data directory with no database in it has nothing worth keeping,
// whatever else happens to be lying around.
const MARKER = "ufc_predictor.db";

function looksLikeDataDir(dir) {
  try {
    return fs.existsSync(path.join(dir, MARKER));
  } catch {
    return false;
  }
}

/**
 * Accepts either the data folder itself or the app folder containing it,
 * because "pick your old MMA Assist folder" is the instruction a user can
 * actually follow - most will not know the database lives one level down.
 */
function resolveSource(chosen) {
  if (looksLikeDataDir(chosen)) return chosen;
  const nested = path.join(chosen, "data");
  if (looksLikeDataDir(nested)) return nested;
  return null;
}

function copyPayload(sourceDir, targetDir, log) {
  let copied = 0;
  for (const entry of PAYLOAD) {
    const from = path.join(sourceDir, entry);
    const to = path.join(targetDir, entry);
    if (!fs.existsSync(from)) continue;
    try {
      // recursive covers chroma_db; force:false so an existing file in the
      // target is never clobbered - the target is supposed to be empty, and
      // if it is not, the safe move is to keep what is already there.
      fs.cpSync(from, to, { recursive: true, force: false, errorOnExist: false });
      copied += 1;
    } catch (err) {
      log(`[migrate] could not copy ${entry}: ${err.message}`);
    }
  }
  return copied;
}

/**
 * Runs before the backend starts, so the imported database is in place by
 * the time SQLite opens it and before the seed bootstrap decides the
 * directory is empty.
 *
 * Returns true if data was imported. Never throws - a failed import must
 * leave the user with a working, if empty, app.
 */
async function maybeOfferImport({ dataDir, dataSource, log = () => {} }) {
  // Only for the installed build, and only when there is nothing to lose.
  if (!dataDir || dataSource !== "installed (user profile)") return false;
  if (looksLikeDataDir(dataDir)) return false;

  const { response } = await dialog.showMessageBox({
    type: "question",
    buttons: ["Choose folder...", "Start fresh"],
    defaultId: 0,
    cancelId: 1,
    title: "Import your existing data?",
    message: "Bring across data from a portable copy of MMA Assist?",
    detail:
      "If you used the portable (zip) version before, your chats, saved predictions and " +
      "fighter database are in a 'data' folder next to the old MMA Assist.exe.\n\n" +
      "Choose that folder to copy them over. Starting fresh is fine too - the app ships " +
      "with the fighter database already built in.",
  });

  if (response !== 0) {
    log("[migrate] user chose to start fresh");
    return false;
  }

  const picked = await dialog.showOpenDialog({
    title: "Select your old MMA Assist folder",
    properties: ["openDirectory"],
    buttonLabel: "Import",
  });
  if (picked.canceled || !picked.filePaths.length) return false;

  const source = resolveSource(picked.filePaths[0]);
  if (!source) {
    await dialog.showMessageBox({
      type: "warning",
      title: "Nothing to import",
      message: "That folder doesn't contain MMA Assist data.",
      detail:
        `Looked for ${MARKER} in the folder you chose and in a 'data' subfolder of it. ` +
        "Pick the folder containing MMA Assist.exe, or its 'data' folder directly.",
    });
    return false;
  }

  fs.mkdirSync(dataDir, { recursive: true });
  const copied = copyPayload(source, dataDir, log);
  log(`[migrate] imported ${copied} item(s) from ${source}`);

  if (copied > 0) {
    await dialog.showMessageBox({
      type: "info",
      title: "Import complete",
      message: "Your data was imported.",
      detail: "The old folder was left untouched - delete it once you're happy everything is here.",
    });
  }
  return copied > 0;
}

module.exports = { maybeOfferImport, resolveSource, looksLikeDataDir, PAYLOAD };
