import DownloadButton from "../components/DownloadButton";
import Reveal from "../components/Reveal";

export default function Download() {
  return (
    <section className="section section--first">
      <div className="container">
        <Reveal className="section__heading">
          <h2>Download UFC Predictor</h2>
          <p>A single Windows package - unzip it, run it, and you're in.</p>
        </Reveal>

        <Reveal delay={90} from="scale">
          <div className="download-card">
            <DownloadButton />
          </div>
        </Reveal>

        <Reveal className="section__heading">
          <h2>Setup</h2>
        </Reveal>
        <ol className="steps">
          <Reveal as="li" from="left">
            <strong>Unzip and run UFCPredictor.exe.</strong>
            The app starts a small local server and opens it in your default browser automatically.
          </Reveal>
          <Reveal as="li" from="left" delay={90}>
            <strong>(Optional) Install Ollama for fully local AI.</strong>
            If you'd rather not use a cloud API key, install{" "}
            <a href="https://ollama.com" target="_blank" rel="noreferrer">Ollama</a> and pull a model
            (e.g. <code>ollama pull llama3.1</code>) before opening Settings in the app.
          </Reveal>
          <Reveal as="li" from="left" delay={180}>
            <strong>Or add a cloud API key.</strong>
            In the app's Settings page, pick OpenAI, Gemini, Deepseek, or Claude and paste in your own API key.
            Keys are stored locally via your OS's credential manager, never sent anywhere but the provider you chose.
          </Reveal>
          <Reveal as="li" from="left" delay={270}>
            <strong>Sync the fighter database.</strong>
            Still in Settings, click "Sync Now" to pull real UFC fighter stats before making predictions.
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
