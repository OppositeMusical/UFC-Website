import { useEffect, useState } from "react";
import {
  formatSize,
  useVersionJson,
  type PlatformArtifact,
  type VersionInfo,
} from "../lib/versionJson";

type Status = "loading" | "ready" | "unavailable";

const RELEASES_URL = "https://github.com/OppositeMusical/UFC-Website/releases";

/**
 * The "no build published" state has two audiences. On a dev machine the
 * useful thing to say is which script produces one; on the public site that
 * same text is a leaked internal instruction telling visitors to run Python.
 */
function isLocalhost(): boolean {
  if (typeof window === "undefined") return false;
  const { hostname } = window.location;
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "[::1]";
}

/**
 * Confirms a same-origin artifact is actually there before offering it.
 *
 * The installer is a ~180MB build artifact and is gitignored, so a deploy
 * built from the repo (Railway, Netlify, a fresh clone) has a version.json
 * pointing at /downloads/... with no file behind it. Without this check the
 * page renders a confident-looking button that 404s - the exact failure the
 * placeholder-URL guard below exists to prevent.
 *
 * Only relative URLs are probed: an absolute one points at a release host
 * that will refuse a cross-origin HEAD, and a CORS failure is not evidence
 * the file is missing.
 */
async function assetExists(url: string): Promise<boolean> {
  if (!url.startsWith("/")) return true;
  try {
    const res = await fetch(url, { method: "HEAD" });
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * showDirectoryPicker() is Chromium-only (Chrome/Edge) and needs a secure
 * context. Firefox and Safari get an ordinary download link instead - the
 * end result is the same file, they just pick the destination through the
 * browser's own save dialog.
 */
function supportsFolderPicker(): boolean {
  return typeof window !== "undefined" && "showDirectoryPicker" in window && window.isSecureContext;
}

type Transfer =
  | { state: "idle" }
  | { state: "saving"; percent: number }
  | { state: "done"; folder: string }
  | { state: "error"; message: string };

function WhatsNew({ info }: { info: VersionInfo }) {
  if (!info.releaseNotes || info.releaseNotes.length === 0) return null;
  return (
    <div className="whats-new">
      <h3>
        What's new in {info.version}
        {info.releasedAt ? <span> · {info.releasedAt}</span> : null}
      </h3>
      <ul>
        {info.releaseNotes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </div>
  );
}

export default function DownloadButton() {
  const { data: info, checked } = useVersionJson();
  const [status, setStatus] = useState<Status>("loading");
  const [transfer, setTransfer] = useState<Transfer>({ state: "idle" });
  const [portableOpen, setPortableOpen] = useState(false);

  useEffect(() => {
    if (!checked) return;
    // A downloadUrl still pointing at the placeholder release host is
    // worse than no button: it looks live and 404s on click.
    const isReal = Boolean(info?.downloadUrl) && !info!.downloadUrl.includes("your-org");
    if (!isReal) {
      setStatus("unavailable");
      return;
    }
    let cancelled = false;
    assetExists(info!.downloadUrl).then((exists) => {
      if (!cancelled) setStatus(exists ? "ready" : "unavailable");
    });
    return () => {
      cancelled = true;
    };
  }, [checked, info]);

  async function handlePickFolder(artifact: PlatformArtifact) {
    if (!artifact) return;

    let dir: FileSystemDirectoryHandle;
    try {
      dir = await (window as unknown as {
        showDirectoryPicker: (o?: { mode?: string }) => Promise<FileSystemDirectoryHandle>;
      }).showDirectoryPicker({ mode: "readwrite" });
    } catch {
      // AbortError when the user cancels the picker - not a failure worth
      // reporting, just return to idle.
      setTransfer({ state: "idle" });
      return;
    }

    setTransfer({ state: "saving", percent: 0 });

    try {
      const response = await fetch(artifact.downloadUrl);
      if (!response.ok || !response.body) throw new Error(`Download failed (${response.status})`);

      const fileName = artifact.fileName || "MMA-Assist-portable.zip";
      const handle = await dir.getFileHandle(fileName, { create: true });
      const writable = await handle.createWritable();

      // Streamed chunk by chunk rather than response.blob(): this archive is
      // ~230MB and buffering it in memory before writing risks an OOM on a
      // modest machine, and gives no progress feedback on a slow connection.
      const total = Number(response.headers.get("content-length")) || artifact.sizeBytes || 0;
      const reader = response.body.getReader();
      let received = 0;

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        await writable.write(value);
        received += value.byteLength;
        if (total) setTransfer({ state: "saving", percent: Math.min(99, Math.round((received / total) * 100)) });
      }
      await writable.close();

      setTransfer({ state: "done", folder: dir.name });
    } catch (err) {
      // Most likely cause is CORS: release assets are served from another
      // origin, and a cross-origin fetch without permissive headers cannot
      // be streamed. The plain <a download> fallback is unaffected because
      // the browser, not JS, performs that request.
      setTransfer({
        state: "error",
        message: `Could not save to that folder (${err instanceof Error ? err.message : "unknown error"}).`,
      });
    }
  }

  if (status === "loading") {
    return (
      <div className="download-cta">
        <span className="btn btn--primary is-loading" aria-busy="true">
          <span className="btn__spinner" aria-hidden="true" />
          Checking for a build
        </span>
      </div>
    );
  }

  if (status === "unavailable" || !info) {
    return (
      <div className="download-cta">
        <span className="btn btn--disabled" aria-disabled="true">
          Build not available yet
        </span>
        {isLocalhost() ? (
          <p className="download-card__version">
            No packaged build is published here yet. Build one locally with{" "}
            <code>python scripts/build_release.py</code> from <code>backend/</code>.
          </p>
        ) : (
          <p className="download-card__version">
            The Windows build isn't published yet. Check the{" "}
            <a href={RELEASES_URL} target="_blank" rel="noreferrer">
              releases page
            </a>{" "}
            for the latest build.
          </p>
        )}
      </div>
    );
  }

  // The manifest's primary Windows artifact is always the NSIS installer -
  // the only Windows target electron-updater can update in place. The
  // portable zip lives under platforms.winPortable.
  const portable: PlatformArtifact | null = info.platforms?.winPortable ?? null;
  const size = formatSize(info.sizeBytes);

  return (
    <div className="download-cta">
      <a className="btn btn--primary btn--download" href={info.downloadUrl} download>
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M12 3v12" />
          <path d="M7 12l5 5 5-5" />
          <path d="M4 21h16" />
        </svg>
        Download for Windows
      </a>

      <p className="download-card__version">
        Version {info.version}
        {size ? ` · ${size}` : ""} · Windows 10/11 (64-bit)
      </p>
      <p className="download-card__meta">
        Installer · Fighter database included · <strong>Updates itself</strong> — later
        releases install from inside the app.
      </p>

      <WhatsNew info={info} />

      {info.sha256 && (
        <p className="download-card__hash">
          <span>SHA-256</span>
          <code>{info.sha256}</code>
        </p>
      )}

      {portable && (
        <div className="portable-option">
          <button
            type="button"
            className="link-button"
            onClick={() => setPortableOpen((open) => !open)}
            aria-expanded={portableOpen}
          >
            {portableOpen ? "Hide" : "Prefer not to install? Get the portable version"}
          </button>

          {portableOpen && (
            <div className="portable-option__body">
              <p className="download-card__meta">
                A zip you extract anywhere — nothing is installed and the app keeps its data
                in a <code>data</code> folder beside the exe. It does{" "}
                <strong>not</strong> update itself; you download and replace it by hand.
              </p>
              {supportsFolderPicker() ? (
                <button
                  type="button"
                  className="btn btn--secondary"
                  onClick={() => handlePickFolder(portable)}
                  disabled={transfer.state === "saving"}
                >
                  {transfer.state === "saving"
                    ? `Saving… ${transfer.percent}%`
                    : "Choose Folder & Download"}
                </button>
              ) : (
                <a className="btn btn--secondary" href={portable.downloadUrl} download>
                  Download portable zip
                </a>
              )}

              {transfer.state === "saving" && (
                <div className="transfer-bar" role="progressbar" aria-valuenow={transfer.percent} aria-valuemin={0} aria-valuemax={100}>
                  <span className="transfer-bar__fill" style={{ width: `${transfer.percent}%` }} />
                </div>
              )}
              {transfer.state === "done" && (
                <p className="transfer-note transfer-note--ok">
                  Saved to <strong>{transfer.folder}</strong>. Extract the zip there, then run{" "}
                  <code>MMA Assist.exe</code>.
                </p>
              )}
              {transfer.state === "error" && (
                <p className="transfer-note transfer-note--err">
                  {transfer.message}{" "}
                  <a href={portable.downloadUrl} download>
                    Download normally instead
                  </a>
                  .
                </p>
              )}

              {portable.sizeBytes && (
                <p className="download-card__version">{formatSize(portable.sizeBytes)} zip</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
