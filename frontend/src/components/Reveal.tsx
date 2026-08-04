import type { ElementType, ReactNode } from "react";
import { useScrollReveal } from "../hooks/useScrollReveal";

interface RevealProps {
  children: ReactNode;
  /** Stagger within a group, in ms. */
  delay?: number;
  /** Direction the element travels from. */
  from?: "up" | "left" | "right" | "scale";
  as?: ElementType;
  className?: string;
}

/**
 * Wraps content so it fades/slides in the first time it scrolls into view.
 * The travel distance and easing live in CSS (.reveal); this only decides
 * when the `is-visible` class lands.
 */
export default function Reveal({
  children,
  delay = 0,
  from = "up",
  as: Tag = "div",
  className = "",
}: RevealProps) {
  const { ref, isVisible } = useScrollReveal<HTMLDivElement>();

  return (
    <Tag
      ref={ref}
      className={`reveal reveal--${from} ${isVisible ? "is-visible" : ""} ${className}`.trim()}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </Tag>
  );
}
