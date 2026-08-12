import { useEffect, useState } from "react";

/**
 * The shape of /version.json, shared by every component that reads it.
 * Lived inside DownloadButton until 0.5.5, which forced MacDownload to
 * import its types from a sibling component and re-implement the fetch.
 */
export interface PlatformArtifact {
  downloadUrl: string;
  /**
   * "nsis" = Windows installer (the self-updating channel);
   * "portable" = Windows zip; "dmg" = macOS disk image.
   */
  kind?: string;
  fileName?: string;
  sizeBytes?: number;
  sha256?: string;
}

export interface VersionInfo extends PlatformArtifact {
  version: string;
  downloadUrl: string;
  releasedAt?: string;
  releaseNotes?: string[];
  /**
   * Per-platform artifacts. The Windows entry is ALSO duplicated at the top
   * level, because installed copies poll this same file for updates and read
   * downloadUrl/sha256 from the root - moving them would break every client
   * already shipped.
   */
  platforms?: Record<string, PlatformArtifact>;
}

export function formatSize(bytes?: number): string | null {
  if (!bytes) return null;
  return `${(bytes / (1024 * 1024)).toFixed(0)} MB`;
}

/**
 * Fetches /version.json once on mount.
 *
 * no-store, because this file is the pointer to the current release. A
 * cached copy keeps sending people to whatever URL was current when they
 * last loaded the page - which is exactly how a stale placeholder survived
 * a rebuild and 404'd on click.
 *
 * `checked` separates "still fetching" from "fetched, and there is no
 * usable manifest" - callers render those two states differently.
 */
export function useVersionJson(): { data: VersionInfo | null; checked: boolean } {
  const [data, setData] = useState<VersionInfo | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch("/version.json", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
      .then((json: VersionInfo) => {
        if (!cancelled) setData(json);
      })
      .catch(() => {
        /* checked=true with data=null is the "unavailable" signal */
      })
      .finally(() => {
        if (!cancelled) setChecked(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { data, checked };
}
