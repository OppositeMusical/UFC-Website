import { useEffect, useState } from "react";

interface VersionInfo {
  version: string;
  downloadUrl: string;
  /** "installer" = the Electron desktop build; anything else is a raw archive. */
  kind?: string;
  fileName?: string;
  sizeBytes?: number;
  sha256?: string;
  releasedAt?: string;
  releaseNotes?: string[];
}

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

function formatSize(bytes?: number): string | null {
  if (!bytes) return null;
  return `${(bytes / (1024 * 1024)).toFixed(0)} MB`;
}

/**
 * Confirms a same-origin artifact is actually there before offering it.
 *
 * The installer is a ~180MB build artifact and is gitignored, so a deploy
 * built from the repo (Railway, Netlify, a fresh clone) has a version.json
 * pointing at /downloads/... with no file behind it. Without this check the
 * page renders a confident-looking button that 404s - the exact failure the
 * placeholder-URL guard above exists to prevent.
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

export default function DownloadButton() {
  const [info, setInfo] = useState<VersionInfo | null>(null);
  const [status, setStatus] = useState<Status>("loading");

  useEffect(() => {
    let cancelled = false;

    // no-store, because this file is the pointer to the current release.
    // A cached copy keeps sending people to whatever URL was current when
    // they last loaded the page - which is exactly how a stale placeholder
    // survived a rebuild and 404'd on click.
    fetch("/version.json", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
      .then(async (data: VersionInfo) => {
        if (cancelled) return;
        // A downloadUrl still pointing at the placeholder release host is
        // worse than no button: it looks live and 404s on click.
        const isReal = Boolean(data?.downloadUrl) && !data.downloadUrl.includes("your-org");
        setInfo(data);
        setStatus(isReal && (await assetExists(data.downloadUrl)) ? "ready" : "unavailable");
      })
      .catch(() => {
        if (!cancelled) setStatus("unavailable");
      });

    return () => {
      cancelled = true;
    };
  }, []);

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

  const size = formatSize(info.sizeBytes);

  return (
    <div className="download-cta">
      <a className="btn btn--primary btn--download" href={info.downloadUrl} download>
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M12 3v12" />
          <path d="M7 12l5 5 5-5" />
          <path d="M4 21h16" />
        </svg>
        {info.kind === "installer" ? "Download Installer" : "Download for Windows"}
      </a>
      <p className="download-card__version">
        Version {info.version}
        {size ? ` · ${size}` : ""} · Windows 10/11 (64-bit)
      </p>
      <p className="download-card__meta">Desktop app · Fighter database included</p>

      {info.releaseNotes && info.releaseNotes.length > 0 && (
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
      )}
      {info.sha256 && (
        <p className="download-card__hash">
          <span>SHA-256</span>
          <code>{info.sha256}</code>
        </p>
      )}
    </div>
  );
}
