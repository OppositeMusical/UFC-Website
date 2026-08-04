import Reveal from "../components/Reveal";

/**
 * Placeholder by request - the page exists and is routed/navigable, but
 * carries no biography content yet.
 */
export default function About() {
  return (
    <section className="section section--first">
      <div className="container">
        <div className="coming-soon">
          <Reveal from="scale">
            <span className="coming-soon__badge">🥊</span>
          </Reveal>
          <Reveal delay={80}>
            <h1 className="coming-soon__title">About the Developer</h1>
          </Reveal>
          <Reveal delay={160}>
            <p className="coming-soon__label">
              Coming soon
              <span className="coming-soon__dots" aria-hidden="true">
                <span />
                <span />
                <span />
              </span>
            </p>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
