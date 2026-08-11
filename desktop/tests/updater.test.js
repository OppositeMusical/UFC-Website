"use strict";

require("./stub-electron");

const test = require("node:test");
const assert = require("node:assert");

const { describeError, normaliseNotes } = require("../updater");

// --- error classification ---------------------------------------------
//
// The user-facing half of the updater. A wrong classification here is worse
// than a raw stack trace, because it tells someone confidently to do the
// wrong thing.

test("a signature failure explains the certificate, not a bad download", () => {
  // This is the failure a real user hits: they installed MMA Assist but
  // skipped importing the self-signed certificate, so electron-updater
  // refuses the installer. Reading that as "corrupt download" sends them
  // round a retry loop that cannot succeed.
  const result = describeError(new Error("New version is not signed by the application owner"));
  assert.match(result.hint, /certificate/i);
  assert.match(result.hint, /trust-cert/i);
});

test("a publisher mismatch is treated as a signature problem", () => {
  const result = describeError(new Error("publisherNames: OppositeMusical, expected ..."));
  assert.match(result.hint, /certificate/i);
});

test("a signature failure never suggests installing anyway", () => {
  const result = describeError(new Error("signature verification failed"));
  assert.match(result.hint, /do not install/i);
});

test("an offline machine is told it is offline", () => {
  const result = describeError(new Error("getaddrinfo ENOTFOUND github.com"));
  assert.match(result.message, /reach the update server/i);
  assert.match(result.hint, /offline/i);
});

test("a 404 reads as 'not published yet', not as a failure of the app", () => {
  const result = describeError(new Error("HttpError: 404 Not Found"));
  assert.match(result.message, /no published update/i);
});

test("an unrecognised error still surfaces its detail", () => {
  const result = describeError(new Error("something exotic happened"));
  assert.match(result.hint, /something exotic happened/);
  assert.strictEqual(result.raw, "something exotic happened");
});

test("a non-Error value does not throw", () => {
  assert.ok(describeError(undefined).message);
  assert.ok(describeError("plain string").message);
});

// --- release notes ------------------------------------------------------
//
// GitHub release bodies arrive as HTML. The renderer writes these with
// textContent so there is no injection risk either way, but leaving tags in
// means the user reads "<p>Fixed the thing</p>".

test("HTML release notes are flattened to plain lines", () => {
  const notes = normaliseNotes("<ul><li>Fixed a crash</li>\n<li>Faster startup</li></ul>");
  assert.deepStrictEqual(notes, ["Fixed a crash", "Faster startup"]);
});

test("markdown bullets lose their leading marker", () => {
  assert.deepStrictEqual(normaliseNotes("- One\n* Two"), ["One", "Two"]);
});

test("the array form used by multi-version updates is flattened", () => {
  const notes = normaliseNotes([
    { version: "0.5.0", note: "Self-updating" },
    { version: "0.4.1", note: "Security fixes" },
  ]);
  assert.deepStrictEqual(notes, ["Self-updating", "Security fixes"]);
});

test("absent or empty notes produce an empty list, not a crash", () => {
  assert.deepStrictEqual(normaliseNotes(null), []);
  assert.deepStrictEqual(normaliseNotes(""), []);
  assert.deepStrictEqual(normaliseNotes([]), []);
  assert.deepStrictEqual(normaliseNotes("\n\n  \n"), []);
});
