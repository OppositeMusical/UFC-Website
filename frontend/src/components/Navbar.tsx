import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

const LINKS = [
  { to: "/#features", label: "Features" },
  { to: "/#how-it-works", label: "How It Works" },
  { to: "/download", label: "Download" },
  { to: "/about", label: "About" },
];

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const { pathname } = useLocation();

  // Solidify the bar once the page moves, so the hero reads full-bleed at
  // rest but text never scrolls under a transparent header.
  useEffect(() => {
    function onScroll() {
      setScrolled(window.scrollY > 12);
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Any navigation closes the mobile menu - otherwise it stays open over
  // the page you just moved to.
  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  return (
    <header className={`navbar ${scrolled ? "is-scrolled" : ""}`}>
      <div className="navbar__inner">
        <Link to="/" className="navbar__brand">
          <span className="navbar__brand-mark">🥊</span>
          UFC <span>Predictor</span>
        </Link>

        <button
          className={`navbar__burger ${menuOpen ? "is-open" : ""}`}
          onClick={() => setMenuOpen((open) => !open)}
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
        >
          <span />
          <span />
          <span />
        </button>

        <ul className={`navbar__links ${menuOpen ? "is-open" : ""}`}>
          {LINKS.map((link) => (
            <li key={link.to}>
              <Link to={link.to} className={pathname === link.to ? "is-active" : ""}>
                {link.label}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </header>
  );
}
