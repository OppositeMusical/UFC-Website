import Hero from "../components/Hero";
import FeatureCard from "../components/FeatureCard";
import Reveal from "../components/Reveal";

const FEATURES = [
  {
    icon: "🧠",
    title: "Local AI, Your Choice",
    description:
      "Run everything through Ollama with zero cloud calls, or bring your own OpenAI, Gemini, Deepseek, or Claude API key.",
  },
  {
    icon: "📊",
    title: "Real Fighter Stats",
    description:
      "Every prediction is grounded in career stats pulled from UFC's own official fighter database - striking, takedowns, defense, and more.",
  },
  {
    icon: "🎯",
    title: "Prop-Specific Predictions",
    description:
      "Purpose-built pages for PrizePicks, DraftKings, and Kalshi - pick two fighters, a stat category, and a line, and get a calibrated over/under call.",
  },
  {
    icon: "💬",
    title: "Continued Conversation",
    description:
      "Every prediction becomes a chat thread. Ask follow-up questions and keep digging with the same AI, same context.",
  },
];

export default function Home() {
  return (
    <>
      <Hero />

      <section className="section" id="features">
        <div className="container">
          <Reveal className="section__heading">
            <h2>Built for Bettors Who Read Stats</h2>
            <p>No black-box vibes. Every call is backed by real, scraped fighter data and shows its reasoning.</p>
          </Reveal>
          <div className="feature-grid">
            {FEATURES.map((f, i) => (
              <Reveal key={f.title} delay={i * 90}>
                <FeatureCard {...f} />
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="section" id="how-it-works">
        <div className="container">
          <Reveal className="section__heading">
            <h2>How It Works</h2>
            <p>Three steps from download to your first prediction.</p>
          </Reveal>
          {/* as="li" keeps each step a real list item, so the CSS counter
              that draws the numbered badges still increments. */}
          <ol className="steps">
            <Reveal as="li" from="left">
              <strong>Download and run the app.</strong>
              It's a local web app - a small server runs on your machine and opens in your browser. No account, no
              cloud dependency required.
            </Reveal>
            <Reveal as="li" from="left" delay={110}>
              <strong>Choose your AI.</strong>
              Point it at a local Ollama install for fully offline use, or paste in an API key for OpenAI, Gemini,
              Deepseek, or Claude from the Settings page.
            </Reveal>
            <Reveal as="li" from="left" delay={220}>
              <strong>Sync the fighter database, then predict.</strong>
              One click pulls real UFC fighter stats. Then head to PrizePicks, DraftKings, or Kalshi, enter a prop,
              and get a stat-grounded call you can keep chatting about.
            </Reveal>
          </ol>
        </div>
      </section>
    </>
  );
}
