#!/usr/bin/env node
/**
 * Checks that everything naming a version agrees, before a tag is treated as a
 * release.
 *
 * The release chain in README.md is four steps whose outputs feed each other,
 * and it says outright that "nothing detects a stale input - skipping one ships
 * a mismatched build rather than failing loudly". This is that detector. It
 * cannot rebuild the artifacts, but it can refuse to bless a tag whose numbers
 * do not line up.
 *
 * Usage: node .github/scripts/check-release.mjs <expected-version>
 *        (the version, without a leading "v")
 */
import { readFileSync } from "node:fs";

const expected = (process.argv[2] ?? "").replace(/^v/, "");
if (!expected) {
  console.error("usage: check-release.mjs <version>");
  process.exit(2);
}

const problems = [];
const notes = [];

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch (err) {
    problems.push(`could not read ${path}: ${err.message}`);
    return null;
  }
}

// desktop/package.json is the single source of truth for the version:
// electron-builder stamps the installer from it, main.js passes it to the
// backend as --app-version, and build_release.py reads it back off the
// installer filename.
const pkg = readJson("desktop/package.json");
if (pkg && pkg.version !== expected) {
  problems.push(
    `tag says ${expected} but desktop/package.json says ${pkg.version}. ` +
      "Run backend/scripts/set_version.py before tagging.",
  );
}

// version.json is both the download pointer and the update manifest that
// installed copies poll, so a stale one strands existing users.
const manifest = readJson("frontend/public/version.json");
if (manifest) {
  if (manifest.version !== expected) {
    problems.push(
      `tag says ${expected} but frontend/public/version.json says ${manifest.version}. ` +
        "Regenerate it with backend/scripts/build_release.py and commit it - " +
        "publishing that manifest is what announces the release.",
    );
  }

  const win = manifest.platforms?.win ?? manifest;

  if (!/^[0-9a-f]{64}$/i.test(win.sha256 ?? "")) {
    problems.push("version.json has no well-formed sha256 for the Windows build.");
  }
  if (!Number.isInteger(win.sizeBytes) || win.sizeBytes <= 0) {
    problems.push("version.json has no plausible sizeBytes for the Windows build.");
  }
  if (typeof win.fileName === "string" && !win.fileName.includes(expected)) {
    problems.push(
      `version.json fileName "${win.fileName}" does not contain ${expected}, ` +
        "which usually means the manifest was regenerated from an older build.",
    );
  }

  // A relative downloadUrl points at frontend/public/downloads/, which is
  // gitignored and therefore absent from any host that builds from the repo.
  // The Download page fails safe on this, but it is worth saying at release
  // time rather than letting the button read "Build not available yet".
  if (typeof win.downloadUrl === "string" && win.downloadUrl.startsWith("/")) {
    notes.push(
      `downloadUrl is relative (${win.downloadUrl}). frontend/public/downloads/ is ` +
        "gitignored, so nothing will be behind it once deployed. Re-run " +
        "build_release.py --github-release OWNER/REPO to point it at the release.",
    );
  }

  if (!Array.isArray(manifest.releaseNotes) || manifest.releaseNotes.length === 0) {
    notes.push("version.json has no release notes; the update banner will look empty.");
  }
}

for (const note of notes) {
  console.log(`::warning::${note}`);
}
for (const problem of problems) {
  console.log(`::error::${problem}`);
}

if (problems.length > 0) {
  console.error(`\n${problems.length} release consistency problem(s).`);
  process.exit(1);
}
console.log(`Release ${expected}: version sources agree.`);
