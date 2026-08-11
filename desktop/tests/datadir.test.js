"use strict";

/**
 * resolveDataDir decides where the user's chats, predictions and fighter
 * database live. Getting it wrong does not crash anything - it silently
 * points the app at an empty directory, which re-seeds and presents itself
 * as a fresh install. That looks exactly like data loss, so every branch is
 * pinned here.
 */
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const { resolveDataDir } = require("../backend");

const USER_DATA = "C:\\Users\\test\\AppData\\Roaming\\MMA Assist";

function tempAppFolder() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "mma-assist-test-"));
}

let savedEnv;

test.beforeEach(() => {
  savedEnv = {
    data: process.env.UFC_PREDICTOR_DATA_DIR,
    portable: process.env.PORTABLE_EXECUTABLE_DIR,
  };
  delete process.env.UFC_PREDICTOR_DATA_DIR;
  delete process.env.PORTABLE_EXECUTABLE_DIR;
});

test.afterEach(() => {
  if (savedEnv.data === undefined) delete process.env.UFC_PREDICTOR_DATA_DIR;
  else process.env.UFC_PREDICTOR_DATA_DIR = savedEnv.data;
  if (savedEnv.portable === undefined) delete process.env.PORTABLE_EXECUTABLE_DIR;
  else process.env.PORTABLE_EXECUTABLE_DIR = savedEnv.portable;
});

test("an explicit data dir always wins", () => {
  process.env.UFC_PREDICTOR_DATA_DIR = "D:\\somewhere\\else";
  const { dir, source } = resolveDataDir(true, USER_DATA);
  assert.strictEqual(dir, "D:\\somewhere\\else");
  assert.match(source, /environment/);
});

test("a dev run defers to the backend's own default", () => {
  assert.strictEqual(resolveDataDir(false, USER_DATA).dir, null);
});

test("an existing data folder beside the exe is reused", () => {
  // The compatibility guarantee for existing portable users.
  const appFolder = tempAppFolder();
  const dataDir = path.join(appFolder, "data");
  fs.mkdirSync(dataDir);
  process.env.PORTABLE_EXECUTABLE_DIR = appFolder;

  const { dir, source } = resolveDataDir(true, USER_DATA);
  assert.strictEqual(dir, dataDir);
  assert.match(source, /existing data folder/);
});

test("an existing data folder wins even when an uninstaller is present", () => {
  // Someone who extracted the portable zip over an installed copy, or any
  // future change to how "installed" is detected. Their data must not be
  // orphaned on an ordering technicality.
  const appFolder = tempAppFolder();
  const dataDir = path.join(appFolder, "data");
  fs.mkdirSync(dataDir);
  fs.writeFileSync(path.join(appFolder, "Uninstall MMA Assist.exe"), "");
  process.env.PORTABLE_EXECUTABLE_DIR = appFolder;

  assert.strictEqual(resolveDataDir(true, USER_DATA).dir, dataDir);
});

test("an installed build with no data yet uses the user profile", () => {
  const appFolder = tempAppFolder();
  fs.writeFileSync(path.join(appFolder, "Uninstall MMA Assist.exe"), "");
  process.env.PORTABLE_EXECUTABLE_DIR = appFolder;

  const { dir, source } = resolveDataDir(true, USER_DATA);
  assert.strictEqual(dir, USER_DATA);
  assert.match(source, /installed/);
});

test("a fresh portable extract creates a data folder beside the exe", () => {
  const appFolder = tempAppFolder();
  process.env.PORTABLE_EXECUTABLE_DIR = appFolder;

  const { dir, source } = resolveDataDir(true, USER_DATA);
  assert.strictEqual(dir, path.join(appFolder, "data"));
  assert.match(source, /portable/);
  assert.ok(fs.existsSync(dir), "the folder should have been created");
});

test("an unwritable location falls back rather than failing to start", () => {
  process.env.PORTABLE_EXECUTABLE_DIR = path.join(
    "\\\\?\\Z:\\definitely-not-mounted",
    "nested"
  );
  const { dir } = resolveDataDir(true, USER_DATA);
  assert.strictEqual(dir, null);
});
