import type { MouseEvent } from "react";

interface FeatureCardProps {
  icon: string;
  title: string;
  description: string;
}

export default function FeatureCard({ icon, title, description }: FeatureCardProps) {
  // Feed the cursor position into CSS custom properties so the card's
  // highlight follows the pointer. Deliberately not React state: this fires
  // on every mousemove, and re-rendering at that rate costs far more than
  // letting the compositor repaint a gradient.
  function handleMouseMove(event: MouseEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    event.currentTarget.style.setProperty("--mx", `${event.clientX - rect.left}px`);
    event.currentTarget.style.setProperty("--my", `${event.clientY - rect.top}px`);
  }

  return (
    <div className="feature-card" onMouseMove={handleMouseMove}>
      <span className="feature-card__glow" aria-hidden="true" />
      <div className="feature-card__icon">{icon}</div>
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
  );
}
