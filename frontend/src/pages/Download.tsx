import DownloadButton from "../components/DownloadButton";
import MacDownload from "../components/MacDownload";
import Reveal from "../components/Reveal";

export default function Download() {
  return (
    <section className="section section--first">
      <div className="container">
        <Reveal className="section__heading">
          <h2>Download MMA Assist</h2>
          <p>
            Portable - nothing is installed. Pick a folder, and the app and its fighter database live there
            together. Delete the folder and it's gone, with nothing left behind.
          </p>
        </Reveal>

        <Reveal delay={90} from="scale">
          <div className="download-card">
            <DownloadButton />
          </div>
        </Reveal>

        <Reveal delay={150}>
          <MacDownload />
        </Reveal>

        <Reveal className="section__heading">
          <h2>Setup</h2>
        </Reveal>
        <ol className="steps">
          <Reveal as="li" from="left">
            <strong>Extract the zip into the folder you chose.</strong>
            Everything is bundled - no Python, no separate downloads - and the fighter database ships
            pre-loaded, so there's nothing to sync before your first prediction.
          </Reveal>
          <Reveal as="li" from="left" delay={90}>
            <strong>Run <code>MMA Assist.exe</code>.</strong>
            On first launch it creates a <code>data</code> folder next to itself holding the fighter
            database and your chat history. Move the whole folder anywhere - another drive, a USB
            stick - and it keeps working, because the app finds its data by looking beside itself.
          </Reveal>
          <Reveal as="li" from="left" delay={135}>
            <strong>Windows may warn you first.</strong>
            The build isn't signed by a certificate authority Windows recognises, so SmartScreen shows
            "Windows protected your PC". Choose <em>More info</em> then <em>Run anyway</em>. You can
            check the download against the SHA-256 above if you'd rather verify it yourself.
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
          MMA Assist is for informational and entertainment purposes only. It is not financial or gambling
          advice, and it does not place bets or wagers on your behalf. You are responsible for complying with the
          laws and platform terms that apply to you. MMA Assist is not affiliated with the UFC, PrizePicks,
          DraftKings, or Kalshi.
        </div>
      </div>
    </section>
  );
}
