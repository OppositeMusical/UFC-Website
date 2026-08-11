"use strict";

/**
 * Guards the electron-builder `files` whitelist against the failure that
 * shipped in the first v0.5.0 build.
 *
 * `build.files` is a whitelist: anything not matched is simply absent from
 * app.asar. updater.js and datamigrate.js were added to the repo but never
 * to that list, so the packaged app threw
 *
 *     Cannot find module './datamigrate'
 *
 * on launch - for every user, immediately, with no earlier signal. Nothing
 * in the build output hints at it: electron-builder does not warn about
 * source files it was not asked to include, and every unit test passes
 * because they run against the repo, not the package.
 *
 * These are static checks against package.json, so they cost nothing and
 * run in the normal suite rather than only at release time.
 */
const test = require("node:test");
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");
const pkg = JSON.parse(fs.readFileSync(path.join(ROOT, "package.json"), "utf8"));

/** electron-builder patterns, reduced to what this project actually uses. */
function matchesPattern(name, pattern) {
  const escaped = pattern.replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, "[^/\\\\]*");
  return new RegExp(`^${escaped}$`).test(name);
}

function isPackaged(name) {
  return pkg.build.files.some((pattern) => matchesPattern(name, pattern));
}

const rootJs = fs
  .readdirSync(ROOT)
  .filter((f) => f.endsWith(".js") && fs.statSync(path.join(ROOT, f)).isFile());

test("every root-level module is covered by build.files", () => {
  for (const file of rootJs) {
    assert.ok(
      isPackaged(file),
      `${file} exists but no build.files pattern matches it - it would be missing from app.asar`
    );
  }
});

test("every relative require resolves to a file that gets packaged", () => {
  // The direct cause of the shipped crash.
  for (const file of rootJs) {
    const source = fs.readFileSync(path.join(ROOT, file), "utf8");
    const requires = [...source.matchAll(/require\("\.\/([a-zA-Z0-9_-]+)"\)/g)].map((m) => m[1]);

    for (const target of requires) {
      const resolved = `${target}.js`;
      assert.ok(
        fs.existsSync(path.join(ROOT, resolved)),
        `${file} requires "./${target}" but ${resolved} does not exist`
      );
      assert.ok(
        isPackaged(resolved),
        `${file} requires "./${target}", but ${resolved} is not matched by build.files - ` +
          `the packaged app would throw "Cannot find module './${target}'" on launch`
      );
    }
  }
});

test("splash.html is packaged", () => {
  // Loaded by path at runtime rather than required, so the require scan
  // above would never notice it going missing.
  assert.ok(isPackaged("splash.html"));
});

test("electron-updater is a production dependency", () => {
  // electron-builder only bundles production deps. Demoting this to
  // devDependencies would drop it from app.asar and break main.js's
  // require("./updater") -> require("electron-updater") chain.
  assert.ok(
    pkg.dependencies && pkg.dependencies["electron-updater"],
    "electron-updater must be in dependencies, not devDependencies"
  );
  assert.ok(
    !(pkg.devDependencies && pkg.devDependencies["electron-updater"]),
    "electron-updater must not also be a devDependency"
  );
});

test("the app entry point is packaged", () => {
  assert.ok(isPackaged(pkg.main), `main entry "${pkg.main}" is not matched by build.files`);
});
