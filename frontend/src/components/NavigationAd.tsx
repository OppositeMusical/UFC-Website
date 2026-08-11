import AdModal from "./AdModal";
import { creativeFor } from "../ads/creatives";
import { useAdRotation } from "../ads/useAdRotation";

/**
 * The page-switch ad. Mounted once in App, inside the router, so it sees
 * every route change regardless of which page is on screen.
 *
 * Renders nothing at all when no "navigation" creative is configured, so
 * emptying CREATIVES turns the popups off without touching components.
 */
export default function NavigationAd() {
  const { shouldShow, dismiss } = useAdRotation();
  const creative = creativeFor("navigation");

  if (!shouldShow || !creative) return null;
  return <AdModal creative={creative} onClose={dismiss} />;
}
