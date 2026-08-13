import { formatSize, useVersionJson } from "../lib/versionJson";

const RELEASES_URL = "https://github.com/OppositeMusical/UFC-Website/releases";

/**
 * macOS download, driven by version.json rather than hardcoded.
 *
 * Renders "coming soon" until a mac artifact is actually published, so the
 * page stops advertising a build that does not exist the moment one does -
 * and never advertises one that doesn't. Windows and macOS are built on
 * separate machines, so the two entries appear independently.
 */
export default function MacDownload() {
  const { data, checked } = useVersionJson();
  const artifact = data?.platforms?.mac ?? null;

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
        <p className="download-card__meta">Apple Silicon (M1 or later) · Fighter database included</p>

        <p className="transfer-note">
          Signed and notarized by Apple — it opens like any other app, and updates
          itself from Settings. Checksums are on the{" "}
          <a href={RELEASES_URL} target="_blank" rel="noreferrer">
            releases page
          </a>
          .
        </p>
      </div>
    </div>
  );
}
