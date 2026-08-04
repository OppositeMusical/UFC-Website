import { useEffect, useState } from "react";

/**
 * Thin bar across the top tracking how far down the page you are.
 * Driven by scroll position rather than an animation, so it stays useful
 * (and honest) under prefers-reduced-motion.
 */
export default function ScrollProgress() {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    function update() {
      const scrollable = document.documentElement.scrollHeight - window.innerHeight;
      // A page shorter than the viewport has nothing to track - reporting
      // 100% there would show a full bar on a page you can't scroll.
      setProgress(scrollable > 0 ? (window.scrollY / scrollable) * 100 : 0);
    }

    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, []);

  return (
    <div className="scroll-progress" aria-hidden="true">
      <div className="scroll-progress__bar" style={{ transform: `scaleX(${progress / 100})` }} />
    </div>
  );
}
