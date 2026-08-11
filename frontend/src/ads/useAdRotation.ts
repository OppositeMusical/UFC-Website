import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

/** Show the ad on every Nth page switch. 2 = every other switch. */
export const SHOW_EVERY_N_SWITCHES = 2;

const STORAGE_KEY = "mma-assist:ad-switch-count";

// sessionStorage throws in some privacy modes and when storage is full.
// A broken ad counter must never take the page down with it.
function readCount(): number {
  try {
    return Number(window.sessionStorage.getItem(STORAGE_KEY)) || 0;
  } catch {
    return 0;
  }
}

function writeCount(value: number): void {
  try {
    window.sessionStorage.setItem(STORAGE_KEY, String(value));
  } catch {
    /* counter just restarts next navigation - not worth failing over */
  }
}

/**
 * True when the current page switch should show an ad.
 *
 * Counts *switches*, not renders:
 *
 *  - The first render is the landing, not a switch, so it never triggers.
 *    Arriving on the site is not "switching pages", and an ad thrown up
 *    before anyone has seen the page is the version search engines
 *    penalise as an intrusive interstitial.
 *  - Only `pathname` is compared. The navbar links to `/#features` and
 *    `/#how-it-works`, which are anchors on the page you are already on -
 *    counting those would fire an ad for scrolling.
 *
 * The count lives in sessionStorage so a reload continues the rhythm
 * instead of restarting it, which would let someone dodge every ad by
 * refreshing.
 */
export function useAdRotation(showEveryN: number = SHOW_EVERY_N_SWITCHES): {
  shouldShow: boolean;
  dismiss: () => void;
} {
  const { pathname } = useLocation();
  const [shouldShow, setShouldShow] = useState(false);
  const lastPathname = useRef<string | null>(null);

  useEffect(() => {
    if (lastPathname.current === null) {
      lastPathname.current = pathname; // landing
      return;
    }
    if (lastPathname.current === pathname) return; // hash/search only
    lastPathname.current = pathname;

    const count = readCount() + 1;
    writeCount(count);

    // Fires on the 1st switch, then every Nth after it: 1, 3, 5... for N=2.
    if ((count - 1) % showEveryN === 0) setShouldShow(true);
  }, [pathname, showEveryN]);

  return { shouldShow, dismiss: () => setShouldShow(false) };
}
