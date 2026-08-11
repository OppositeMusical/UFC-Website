/**
 * Ad creatives, kept in one file so swapping them is a content edit rather
 * than a component change.
 *
 * Two shapes are supported:
 *
 *   kind: "house"   - a creative we render ourselves (headline/body/CTA,
 *                     optional image). No third-party script, nothing to
 *                     block, works with an ad blocker installed.
 *   kind: "network" - raw markup from an ad network, injected as-is.
 *
 * The network path exists so a real tag can be dropped in without touching
 * AdModal, but read the warning on `html` before using it.
 */

/**
 * "navigation" fires on a page switch, on a rotation (see useAdRotation).
 * "download" fires when a download starts.
 */
export type AdPlacement = "navigation" | "download";

interface BaseCreative {
  /** Stable id. Used for the per-session frequency cap, so changing it re-shows the ad. */
  id: string;
  placement: AdPlacement;
}

export interface HouseCreative extends BaseCreative {
  kind: "house";
  headline: string;
  body: string;
  ctaLabel: string;
  ctaHref: string;
  /** Optional image URL. Must be same-origin or a permitted host. */
  imageSrc?: string;
  imageAlt?: string;
}

export interface NetworkCreative extends BaseCreative {
  kind: "network";
  /**
   * Raw ad markup, inserted with dangerouslySetInnerHTML.
   *
   * ONLY ever put a trusted network's own tag here. This is a deliberate
   * XSS hole for anything else - it is the one place in this codebase that
   * bypasses React's escaping. Note that React will not execute <script>
   * tags inserted this way; a network needing script execution has to be
   * loaded via its own loader in index.html instead.
   */
  html: string;
}

export type AdCreative = HouseCreative | NetworkCreative;

/**
 * Placeholder house ads. Replace the copy, links and images with real
 * creatives - or swap an entry for a `kind: "network"` one.
 *
 * Set to an empty array to turn all popups off without touching components.
 */
export const CREATIVES: AdCreative[] = [
  {
    id: "navigation-2026-08",
    placement: "navigation",
    kind: "house",
    headline: "Your ad here",
    body: "Shown on every other page switch. Swap the copy, link and image in src/ads/creatives.ts.",
    ctaLabel: "Learn more",
    ctaHref: "https://example.com",
  },
  {
    id: "download-2026-08",
    placement: "download",
    kind: "house",
    headline: "Your ad here",
    body: "Shown when a download starts. The download is already running behind this - closing it will not cancel anything.",
    ctaLabel: "Learn more",
    ctaHref: "https://example.com",
  },
];

export function creativeFor(placement: AdPlacement): AdCreative | null {
  return CREATIVES.find((c) => c.placement === placement) ?? null;
}
