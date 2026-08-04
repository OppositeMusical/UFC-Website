/**
 * Static file server for the built marketing site.
 *
 * Deliberately dependency-free (Node stdlib only) rather than `serve` or
 * express: the only things this needs beyond "send a file" are an SPA
 * fallback and three specific cache policies, and getting those wrong has
 * already caused a real bug - a cached version.json kept sending users to
 * a download URL that no longer existed.
 *
 * `vite preview` is not used because its own docs say it is not intended
 * as a production server.
 */

// ESM, because package.json declares "type": "module" - CommonJS require()
// would throw at startup here.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const PORT = Number(process.env.PORT) || 8080;
const HOST = "0.0.0.0"; // Railway routes to the container's external interface.
const DIST = path.join(__dirname, "dist");

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".txt": "text/plain; charset=utf-8",
  ".exe": "application/octet-stream",
  ".zip": "application/zip",
  ".map": "application/json; charset=utf-8",
};

function cacheControlFor(pathname) {
  // The release manifest is a pointer to the current download AND the feed
  // installed copies poll for updates. A cached copy strands users on a
  // stale version - never cache it.
  if (pathname === "/version.json") return "no-store, must-revalidate";

  // Vite fingerprints these, so the name changes whenever the bytes do.
  if (pathname.startsWith("/assets/")) return "public, max-age=31536000, immutable";

  // Installers carry their version in the filename, same reasoning.
  if (pathname.startsWith("/downloads/")) return "public, max-age=31536000, immutable";

  // index.html is the bootstrap that references the hashed assets; caching
  // it would pin visitors to an old asset graph after a deploy.
  return "no-cache";
}

function resolveSafe(pathname) {
  // Normalise before joining so "..%2f" style traversal can't escape dist/.
  const decoded = decodeURIComponent(pathname.split("?")[0]);
  const target = path.join(DIST, path.normalize(decoded));
  if (!target.startsWith(DIST)) return null;
  return target;
}

function sendFile(res, filePath, pathname, statusCode = 200) {
  const ext = path.extname(filePath).toLowerCase();
  const stat = fs.statSync(filePath);

  res.writeHead(statusCode, {
    "Content-Type": MIME[ext] || "application/octet-stream",
    "Content-Length": stat.size,
    "Cache-Control": cacheControlFor(pathname),
    "X-Content-Type-Options": "nosniff",
  });
  fs.createReadStream(filePath).pipe(res);
}

const server = http.createServer((req, res) => {
  if (req.method !== "GET" && req.method !== "HEAD") {
    res.writeHead(405, { Allow: "GET, HEAD" }).end("Method Not Allowed");
    return;
  }

  const pathname = new URL(req.url, `http://${req.headers.host}`).pathname;
  const target = resolveSafe(pathname);

  if (!target) {
    res.writeHead(400).end("Bad Request");
    return;
  }

  // Health endpoint for Railway's checks - answers before touching disk.
  if (pathname === "/healthz") {
    res.writeHead(200, { "Content-Type": "text/plain" }).end("ok");
    return;
  }

  try {
    if (fs.existsSync(target) && fs.statSync(target).isFile()) {
      sendFile(res, target, pathname);
      return;
    }

    // SPA fallback: /about and /download are client-side routes with no
    // file behind them, so a direct visit or refresh must still boot the
    // app. Anything with a file extension is a genuine miss - falling back
    // to HTML there would hand a broken .js a 200 and mask the failure.
    if (!path.extname(pathname)) {
      const index = path.join(DIST, "index.html");
      if (fs.existsSync(index)) {
        sendFile(res, index, "/index.html", 200);
        return;
      }
    }

    res.writeHead(404, { "Content-Type": "text/plain" }).end("Not Found");
  } catch (err) {
    console.error(`error serving ${pathname}:`, err.message);
    res.writeHead(500, { "Content-Type": "text/plain" }).end("Internal Server Error");
  }
});

if (!fs.existsSync(DIST)) {
  console.error(`No build output at ${DIST}. Run \`npm run build\` first.`);
  process.exit(1);
}

server.listen(PORT, HOST, () => {
  console.log(`Serving ${DIST} on http://${HOST}:${PORT}`);
});

// Railway sends SIGTERM on redeploy; exit promptly instead of being killed.
for (const signal of ["SIGTERM", "SIGINT"]) {
  process.on(signal, () => server.close(() => process.exit(0)));
}
