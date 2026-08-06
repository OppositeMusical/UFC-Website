import { useEffect, useState } from "react";
import type { PlatformArtifact } from "./DownloadButton";

const RELEASES_URL = "https://github.com/OppositeMusical/UFC-Website/releases";

function formatSize(bytes?: number): string | null {
  if (!bytes) return null;
  return `${(bytes / (1024 * 1024)).toFixed(0)} MB`;
}

/**
 * macOS download, driven by version.json rather than hardcoded.
 *
 * Renders "coming soon" until a mac artifact is actually published, so the
 * page stops advertising a build that does not exist the moment one does -
 * and never advertises one that doesn't. Windows and macOS are built on
 * separate machines, so the two entries appear independently.
 */
export default function MacDownload() {
  const [artifact, setArtifact] = useState<PlatformArtifact | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch("/version.json", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
      .then((data) => {
        if (cancelled) return;
        setArtifact(data?.platforms?.mac ?? null);
        setChecked(true);
      })
      .catch(() => {
        if (!cancelled) setChecked(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const appleIcon = (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M16.4 12.7c0-2.3 1.9-3.4 2-3.5-1.1-1.6-2.8-1.8-3.4-1.8-1.4-.1-2.8.9-3.5.9-.7 0-1.8-.9-3-.8-1.5 0-2.9.9-3.7 2.2-1.6 2.7-.4 6.8 1.1 9 .8 1.1 1.7 2.3 2.9 2.2 1.2 0 1.6-.7 3-.7s1.8.7 3 .7c1.3 0 2.1-1.1 2.8-2.2.9-1.3 1.3-2.5 1.3-2.6 0 0-2.5-1-2.5-3.4zM14.2 5.9c.6-.8 1-1.9.9-3-.9 0-2 .6-2.7 1.4-.6.7-1.1 1.8-.9 2.9 1 .1 2-.5 2.7-1.3z" />
    </svg>
  );

  if (!checked || !artifact) {
    return (
      <div className="download-card download-card--soon">
        <span className="btn btn--disabled" aria-disabled="true">
          {appleIcon}
          Download for macOS
        </span>
        <p className="download-card__version">
          <span className="soon-badge">Coming soon</span>
        </p>
        <p className="download-card__meta">
          A macOS build isn't published yet. Windows is the only supported platform today.
        </p>
      </div>
    );
  }

  const size = formatSize(artifact.sizeBytes);

  return (
    <div className="download-card">
      <div className="download-cta">
        <a className="btn btn--primary btn--download" href={artifact.downloadUrl} download>
          {appleIcon}
          Download for macOS
        </a>
        <p className="download-card__version">
          {size ? `${size} · ` : ""}macOS 11 or later
        </p>
        <p className="download-card__meta">Apple Silicon &amp; Intel · Fighter database included</p>

        {/* Gatekeeper refuses unsigned downloads outright rather than warning,
            and the message it shows says "damaged", which reads as a corrupt
            file. Saying so here is the difference between a user retrying and
            a user deleting it. */}
        <p className="transfer-note transfer-note--err">
          This build isn't notarized by Apple yet, so macOS may say it's{" "}
          <em>damaged and can't be opened</em>. It isn't — that's Gatekeeper refusing an
          unsigned download. Remove the quarantine flag to run it:
          <br />
          <code>xattr -dr com.apple.quarantine "/Applications/MMA Assist.app"</code>
          <br />
          Only do that if you trust the source. You can check the download against the
          SHA-256 on the{" "}
          <a href={RELEASES_URL} target="_blank" rel="noreferrer">
            releases page
          </a>{" "}
          first.
        </p>
      </div>
    </div>
  );
}
