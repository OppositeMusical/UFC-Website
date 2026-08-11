"use strict";

require("./stub-electron");

const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const { resolveSource, looksLikeDataDir, PAYLOAD } = require("../datamigrate");

function tempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "mma-migrate-test-"));
}

function makeDataDir(parent, name = "data") {
  const dir = path.join(parent, name);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "ufc_predictor.db"), "sqlite");
  return dir;
}

test("a folder containing the database is accepted directly", () => {
  const root = tempDir();
  const data = makeDataDir(root);
  assert.strictEqual(resolveSource(data), data);
});

test("the app folder is accepted, resolving to its data subfolder", () => {
  // What a user will actually pick: the folder holding MMA Assist.exe.
  // Expecting them to know the database lives one level down is a good way
  // to have the import fail for no reason.
  const root = tempDir();
  const data = makeDataDir(root);
  assert.strictEqual(resolveSource(root), data);
});

test("a folder with no MMA Assist data is rejected", () => {
  const root = tempDir();
  fs.writeFileSync(path.join(root, "notes.txt"), "unrelated");
  assert.strictEqual(resolveSource(root), null);
});

test("an empty data folder is rejected - there is nothing to import", () => {
  const root = tempDir();
  fs.mkdirSync(path.join(root, "data"));
  assert.strictEqual(resolveSource(root), null);
});

test("a nonexistent path is rejected rather than throwing", () => {
  assert.strictEqual(resolveSource(path.join(tempDir(), "nope")), null);
});

test("looksLikeDataDir keys on the database, not on the folder name", () => {
  const root = tempDir();
  const oddlyNamed = makeDataDir(root, "my-old-stuff");
  assert.ok(looksLikeDataDir(oddlyNamed));
  assert.ok(!looksLikeDataDir(root));
});

test("the payload covers everything the app writes", () => {
  // Mirrors app/config.py. If a new file joins the data directory and is
  // not listed here, a migrating user loses it silently.
  assert.deepStrictEqual(
    [...PAYLOAD].sort(),
    [".secrets.enc", ".secrets.key", "chroma_db", "ufc_predictor.db"]
  );
});
