import { useEffect, useRef } from "react";
import type { AdCreative } from "../ads/creatives";

interface Props {
  creative: AdCreative;
  onClose: () => void;
  /** Extra line under the ad, e.g. reassurance that a download is unaffected. */
  footnote?: string;
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])';

/**
 * Modal ad overlay.
 *
 * Not a real pop-up window: `window.open` is blocked on page load by every
 * modern browser and heavily restricted even behind a click, so an in-page
 * overlay is the only thing that reliably renders.
 *
 * Deliberately dismissible three ways - close button, Escape, backdrop
 * click. An ad the user cannot escape is a trap, and on mobile it is the
 * kind of thing that gets a site delisted rather than merely disliked.
 */
export default function AdModal({ creative, onClose, footnote }: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  // Whatever had focus before the ad opened, so it can be handed back.
  const previouslyFocused = useRef<HTMLElement | null>(null);

  useEffect(() => {
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();

    // Stop the page scrolling underneath. Restored on unmount, including
    // when the component is removed by something other than onClose.
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;

      // Focus trap. Without it, tabbing walks into the page behind the
      // overlay - invisible to a sighted user, completely disorienting to
      // a screen-reader one.
      const nodes = dialogRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE);
      if (!nodes || nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      previouslyFocused.current?.focus?.();
    };
  }, [onClose]);

  return (
    <div
      className="ad-backdrop"
      // Backdrop only - a click inside the dialog must not close it, hence
      // the target check rather than a handler on the whole subtree.
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className="ad-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ad-modal-heading"
        ref={dialogRef}
      >
        {/* Labelled as advertising. Standard disclosure practice, and the
            thing regulators look for when ads resemble site content. */}
        <span className="ad-modal__tag">Advertisement</span>

        <button
          type="button"
          className="ad-modal__close"
          onClick={onClose}
          aria-label="Close advertisement"
          ref={closeRef}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>

        {creative.kind === "network" ? (
          <div
            className="ad-modal__network"
            id="ad-modal-heading"
            aria-label="Advertisement"
            dangerouslySetInnerHTML={{ __html: creative.html }}
          />
        ) : (
          <div className="ad-modal__body">
            {creative.imageSrc && (
              <img className="ad-modal__image" src={creative.imageSrc} alt={creative.imageAlt ?? ""} />
            )}
            <h2 id="ad-modal-heading">{creative.headline}</h2>
            <p>{creative.body}</p>
            <a
              className="btn btn--primary"
              href={creative.ctaHref}
              target="_blank"
              // noopener: the ad target must not get a handle on window.opener.
              // sponsored: tells crawlers this is paid, per Google's link rules.
              rel="noopener noreferrer sponsored"
              onClick={onClose}
            >
              {creative.ctaLabel}
            </a>
          </div>
        )}

        {footnote && <p className="ad-modal__footnote">{footnote}</p>}
      </div>
    </div>
  );
}
