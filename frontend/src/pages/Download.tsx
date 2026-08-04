import DownloadButton from "../components/DownloadButton";
import Reveal from "../components/Reveal";

export default function Download() {
  return (
    <section className="section section--first">
      <div className="container">
        <Reveal className="section__heading">
          <h2>Download UFC Predictor</h2>
          <p>A standard Windows installer. Runs as a real desktop app - no browser tab, no terminal.</p>
        </Reveal>

        <Reveal delay={90} from="scale">
          <div className="download-card">
            <DownloadButton />
          </div>
        </Reveal>

        <Reveal delay={150}>
          <div className="download-card download-card--soon">
            <span className="btn btn--disabled" aria-disabled="true">
              <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M16.4 12.7c0-2.3 1.9-3.4 2-3.5-1.1-1.6-2.8-1.8-3.4-1.8-1.4-.1-2.8.9-3.5.9-.7 0-1.8-.9-3-.8-1.5 0-2.9.9-3.7 2.2-1.6 2.7-.4 6.8 1.1 9 .8 1.1 1.7 2.3 2.9 2.2 1.2 0 1.6-.7 3-.7s1.8.7 3 .7c1.3 0 2.1-1.1 2.8-2.2.9-1.3 1.3-2.5 1.3-2.6 0 0-2.5-1-2.5-3.4zM14.2 5.9c.6-.8 1-1.9.9-3-.9 0-2 .6-2.7 1.4-.6.7-1.1 1.8-.9 2.9 1 .1 2-.5 2.7-1.3z" />
              </svg>
              Download for macOS
            </span>
            <p className="download-card__version">
              <span className="soon-badge">Coming soon</span>
            </p>
            <p className="download-card__meta">
              A macOS build isn't available yet. Windows is the only supported platform today.
            </p>
          </div>
        </Reveal>

        <Reveal className="section__heading">
          <h2>Setup</h2>
        </Reveal>
        <ol className="steps">
          <Reveal as="li" from="left">
            <strong>Run the installer.</strong>
            It adds UFC Predictor to your Start menu and desktop. Everything it needs is bundled -
            no Python, no separate downloads, and the fighter database ships pre-loaded so there's
            nothing to sync before your first prediction.
          </Reveal>
          <Reveal as="li" from="left" delay={90}>
            <strong>Windows may warn you first.</strong>
            The installer isn't code-signed yet, so SmartScreen shows "Windows protected your PC".
            Choose <em>More info</em> then <em>Run anyway</em>. You can verify the download against
            the SHA-256 above if you'd rather check it yourself.
          </Reveal>
          <Reveal as="li" from="left" delay={180}>
            <strong>Pick your AI in Settings.</strong>
            Install <a href="https://ollama.com" target="_blank" rel="noreferrer">Ollama</a> and pull a
            model (e.g. <code>ollama pull llama3.1</code>) to stay fully offline, or paste in an API key
            for OpenAI, Gemini, Deepseek, or Claude. Keys are stored in your OS credential manager and
            never sent anywhere but the provider you chose.
          </Reveal>
          <Reveal as="li" from="left" delay={270}>
            <strong>Start predicting.</strong>
            Head to PrizePicks, DraftKings, or Kalshi, enter a prop, and get a stat-grounded call you can
            keep chatting about. Refresh the fighter database anytime from Settings.
          </Reveal>
        </ol>

        <div className="disclaimer-box">
          UFC Predictor is for informational and entertainment purposes only. It is not financial or gambling
          advice, and it does not place bets or wagers on your behalf. You are responsible for complying with the
          laws and platform terms that apply to you. UFC Predictor is not affiliated with the UFC, PrizePicks,
          DraftKings, or Kalshi.
        </div>
      </div>
    </section>
  );
}
