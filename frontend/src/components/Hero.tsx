import { Link } from "react-router-dom";

const PLATFORMS = ["PrizePicks", "DraftKings", "Kalshi"];

export default function Hero() {
  return (
    <section className="hero">
      <div className="hero__grid" aria-hidden="true" />
      <div className="container">
        {/* A fixed stagger, not scroll-driven: the hero is already in view
            on load, so there is nothing to observe for. */}
        <span className="hero__eyebrow hero-in" style={{ animationDelay: "60ms" }}>
          Local-First MMA Analytics
        </span>
        <h1 className="hero-in" style={{ animationDelay: "140ms" }}>
          Fighter stats, not <span className="hero__accent">vibes</span>.
        </h1>
        <p className="lede hero-in" style={{ animationDelay: "220ms" }}>
          MMA Assist is a downloadable desktop app that runs your choice of AI - fully offline with Ollama,
          or your own OpenAI, Gemini, Deepseek, or Claude key - grounded in real, scraped UFC career stats for
          every prop you check.
        </p>
        <div className="hero__actions hero-in" style={{ animationDelay: "300ms" }}>
          <Link className="btn btn--primary" to="/download">
            Download the App
          </Link>
          <a className="btn btn--secondary" href="#how-it-works">
            See How It Works
          </a>
        </div>
        <div className="platform-strip">
          {PLATFORMS.map((name, i) => (
            <span
              key={name}
              className="platform-pill hero-in"
              style={{ animationDelay: `${380 + i * 70}ms` }}
            >
              {name}
            </span>
          ))}
        </div>
      </div>
      <div className="hero__fade" aria-hidden="true" />
    </section>
  );
}
