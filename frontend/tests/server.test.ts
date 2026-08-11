/**
 * Regression tests for server.js request handling.
 *
 * The bug these exist for: `decodeURIComponent` throws URIError on a
 * malformed percent-escape, it was called from inside the request handler,
 * and an uncaught throw there ends the Node process. `curl https://site/%zz`
 * took the whole marketing site down and burned a Railway restart - one
 * unauthenticated GET, no payload, no auth.
 *
 * The server is spawned as a real child process rather than imported,
 * because "the process is still alive afterwards" is precisely the property
 * under test and an in-process import cannot observe it.
 */
import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { spawn, type ChildProcess } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const PORT = 8123;
const BASE = `http://127.0.0.1:${PORT}`;

let server: ChildProcess;

async function waitForReady(timeoutMs = 15000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`${BASE}/healthz`);
      if (res.ok) return;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error("server did not become ready");
}

beforeAll(async () => {
  server = spawn(process.execPath, [path.join(ROOT, "server.js")], {
    cwd: ROOT,
    env: { ...process.env, PORT: String(PORT) },
    stdio: "ignore",
  });
  await waitForReady();
}, 20000);

afterAll(() => {
  server?.kill();
});

describe("malformed request paths", () => {
  // Each of these throws URIError out of decodeURIComponent.
  const malformed = ["/%zz", "/%", "/a%2", "/%E0%A4%A"];

  it.each(malformed)("answers 400 for %s instead of crashing", async (target) => {
    const res = await fetch(`${BASE}${target}`);
    expect(res.status).toBe(400);
  });

  it("is still serving traffic after every malformed request", async () => {
    for (const target of malformed) {
      await fetch(`${BASE}${target}`).catch(() => {});
    }
    const res = await fetch(`${BASE}/healthz`);
    expect(res.status).toBe(200);
    expect(await res.text()).toBe("ok");
  });
});

describe("normal routing still works", () => {
  it("serves index.html at the root", async () => {
    const res = await fetch(`${BASE}/`);
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toContain("text/html");
  });

  it("falls back to the SPA for a client-side route", async () => {
    const res = await fetch(`${BASE}/download`);
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toContain("text/html");
  });

  it("404s a missing file rather than handing back HTML", async () => {
    // A 200 of index.html for a .js miss masks the real failure.
    const res = await fetch(`${BASE}/does-not-exist.js`);
    expect(res.status).toBe(404);
  });

  it("refuses to escape dist/ via encoded traversal", async () => {
    const res = await fetch(`${BASE}/..%2f..%2fpackage.json`);
    expect([400, 404]).toContain(res.status);
  });

  it("never caches version.json", async () => {
    const res = await fetch(`${BASE}/version.json`);
    expect(res.headers.get("cache-control")).toContain("no-store");
  });
});
