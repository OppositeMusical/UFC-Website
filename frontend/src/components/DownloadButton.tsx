import { useEffect, useState } from "react";

interface VersionInfo {
  version: string;
  downloadUrl: string;
  sizeBytes?: number;
  sha256?: string;
  releasedAt?: string;
}

type Status = "loading" | "ready" | "unavailable";

function formatSize(bytes?: number): string | null {
  if (!bytes) return null;
  return `${(bytes / (1024 * 1024)).toFixed(0)} MB`;
}

export default function DownloadButton() {
  const [info, setInfo] = useState<VersionInfo | null>(null);
  const [status, setStatus] = useState<Status>("loading");

  useEffect(() => {
    let cancelled = false;

    fetch("/version.json")
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
      .then((data: VersionInfo) => {
        if (cancelled) return;
        // A downloadUrl still pointing at the placeholder release host is
        // worse than no button: it looks live and 404s on click.
        const isReal = Boolean(data?.downloadUrl) && !data.downloadUrl.includes("your-org");
        setInfo(data);
        setStatus(isReal ? "ready" : "unavailable");
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
        <p className="download-card__version">
          No packaged build is published here yet. Build one locally with{" "}
          <code>python scripts/build_release.py</code> from <code>backend/</code>.
        </p>
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
        Download for Windows
      </a>
      <p className="download-card__version">
        Version {info.version}
        {size ? ` · ${size}` : ""} · Windows 10/11 (64-bit)
      </p>
      {info.sha256 && (
        <p className="download-card__hash">
          <span>SHA-256</span>
          <code>{info.sha256}</code>
        </p>
      )}
    </div>
  );
}
