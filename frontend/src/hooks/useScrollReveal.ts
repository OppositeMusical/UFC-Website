import { useEffect, useRef, useState } from "react";

interface Options {
  /** Fraction of the element that must be visible before it reveals. */
  threshold?: number;
  /** Shrinks the viewport so elements reveal slightly before the true edge. */
  rootMargin?: string;
}

/**
 * Reveals an element once it scrolls into view, then stops observing.
 *
 * Degrades to "immediately visible" wherever IntersectionObserver is
 * missing (jsdom under test, older browsers) or the user asked for reduced
 * motion - content must never depend on an animation having run to be
 * readable.
 */
export function useScrollReveal<T extends HTMLElement>({
  threshold = 0.15,
  rootMargin = "0px 0px -60px 0px",
}: Options = {}) {
  const ref = useRef<T | null>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    const prefersReducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    if (!node || typeof IntersectionObserver === "undefined" || prefersReducedMotion) {
      setIsVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setIsVisible(true);
            // One-shot: re-animating on every scroll past is noise, not polish.
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold, rootMargin }
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [threshold, rootMargin]);

  return { ref, isVisible };
}
