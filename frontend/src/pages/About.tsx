import FeatureCard from "../components/FeatureCard";
import Reveal from "../components/Reveal";

const GITHUB_URL = "https://github.com/OppositeMusical";
const LINKEDIN_URL = "https://www.linkedin.com/in/christepher-irving-028437294/";

/**
 * About the Developer.
 *
 * Everything stated here is verifiable - from the public GitHub profile or
 * from this repository's own source. Nothing about employment, education or
 * location is asserted, because none of it could be read: LinkedIn returns
 * HTTP 999 to unauthenticated requests, so the profile was never accessible.
 *
 * TO PERSONALISE: the intro below describes the work rather than the person.
 * Replace it with your own background - where you're based, what you studied
 * or where you've worked, and what you're aiming at next. Everything else on
 * the page can stay as-is.
 */

const WHAT_I_BUILD = [
  {
    icon: "🧩",
    title: "Full-stack applications",
    description:
      "Python and Flask on the server, React and TypeScript on the front end, SQLAlchemy over SQLite for storage. MMA Assist is all three at once.",
  },
  {
    icon: "🖥️",
    title: "Desktop software",
    description:
      "Electron shells around real backends, packaged with electron-builder and PyInstaller - code-signed, with an installer that updates itself in place.",
  },
  {
    icon: "🤖",
    title: "AI-backed tooling",
    description:
      "Retrieval-augmented generation over a ChromaDB vector store, behind one provider abstraction that speaks to local Ollama models and the OpenAI, Gemini, Deepseek and Claude APIs alike.",
  },
  {
    icon: "🕸️",
    title: "Data collection",
    description:
      "A robots.txt-respecting scraper that built this app's fighter database from UFC's official site - resumable, rate-limited, and checkpointed so a long run survives interruption.",
  },
];

export default function About() {
  return (
    <section className="section section--first">
      <div className="container">
        <Reveal from="scale">
          <div className="dev-profile">
            <div className="dev-profile__mark" aria-hidden="true">
              MA
            </div>
            <div className="dev-profile__text">
              <h1>Christepher Irving</h1>
              <p className="dev-profile__role">Software developer &middot; builder of MMA Assist</p>
              <div className="dev-profile__links">
                <a href={GITHUB_URL} target="_blank" rel="noreferrer">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                    <path d="M12 .5a12 12 0 0 0-3.79 23.4c.6.1.82-.26.82-.58v-2c-3.34.73-4.04-1.61-4.04-1.61-.55-1.39-1.34-1.76-1.34-1.76-1.09-.75.08-.73.08-.73 1.2.08 1.84 1.24 1.84 1.24 1.07 1.83 2.81 1.3 3.5.99.1-.78.42-1.3.76-1.6-2.67-.3-5.47-1.33-5.47-5.93 0-1.31.47-2.38 1.24-3.22-.13-.3-.54-1.52.11-3.18 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 0 1 6.01 0c2.29-1.55 3.3-1.23 3.3-1.23.65 1.66.24 2.88.12 3.18.77.84 1.23 1.91 1.23 3.22 0 4.61-2.8 5.62-5.48 5.92.43.37.81 1.1.81 2.22v3.29c0 .32.22.69.83.57A12 12 0 0 0 12 .5z" />
                  </svg>
                  GitHub
                </a>
                <a href={LINKEDIN_URL} target="_blank" rel="noreferrer">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                    <path d="M20.45 20.45h-3.56v-5.57c0-1.33-.03-3.04-1.85-3.04-1.85 0-2.14 1.45-2.14 2.94v5.67H9.35V9h3.42v1.56h.05a3.75 3.75 0 0 1 3.37-1.85c3.6 0 4.27 2.37 4.27 5.46v6.28zM5.34 7.43a2.07 2.07 0 1 1 0-4.14 2.07 2.07 0 0 1 0 4.14zm1.78 13.02H3.55V9h3.57v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.72v20.56C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.72V1.72C24 .77 23.2 0 22.22 0z" />
                  </svg>
                  LinkedIn
                </a>
              </div>
            </div>
          </div>
        </Reveal>

        <Reveal delay={90}>
          <div className="dev-intro">
            <p>
              I build things end to end. MMA Assist started as a question — could a local language
              model make a genuinely stat-grounded call on a fight prop, without sending anything to
              the cloud? — and turned into a desktop app with a scraped database of{" "}
              <strong>6,746 fighters</strong>, a retrieval layer over their career stats, and support
              for five different AI providers.
            </p>
            <p>
              Most of what I find interesting sits in the unglamorous parts: making a scraper resume
              cleanly after a 55-hour run, getting an Electron app to replace its own binary while a
              Python server is still holding the file open, and working out why a signed installer
              refuses to verify on a machine that has never seen your certificate.
            </p>
          </div>
        </Reveal>

        <Reveal className="section__heading" delay={40}>
          <h2>What I Build</h2>
        </Reveal>
        <div className="feature-grid">
          {WHAT_I_BUILD.map((item, i) => (
            <Reveal key={item.title} delay={i * 90}>
              <FeatureCard {...item} />
            </Reveal>
          ))}
        </div>

        <Reveal className="section__heading">
          <h2>Elsewhere</h2>
          <p>
            MMA Assist is open source, and it's not the only thing on there — there are twenty public
            repositories, in Python, TypeScript and a few other things besides.
          </p>
        </Reveal>
        <Reveal from="scale" delay={80}>
          <div className="dev-cta">
            <a className="btn btn--primary" href={GITHUB_URL} target="_blank" rel="noreferrer">
              Browse the code on GitHub
            </a>
            <a className="btn btn--secondary" href={LINKEDIN_URL} target="_blank" rel="noreferrer">
              Connect on LinkedIn
            </a>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
