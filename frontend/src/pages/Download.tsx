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
            An installer that keeps itself current - once it's on your machine, every release after this
            one arrives from inside the app. The fighter database ships with it, so there's nothing to
            sync before your first prediction.
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
            <strong>Run the installer.</strong>
            It installs for your account only, so Windows won't ask for an administrator, and you can
            put it somewhere other than the default folder if you'd rather. Everything is bundled - no
            Python, no separate downloads - and the fighter database is already loaded.
          </Reveal>
          <Reveal as="li" from="left" delay={90}>
            <strong>Windows may warn you first.</strong>
            The build <em>is</em> signed, but with our own certificate rather than one Windows already
            recognises, so SmartScreen shows "Windows protected your PC". Choose <em>More info</em>{" "}
            then <em>Run anyway</em>. You can check the download against the SHA-256 above if you'd
            rather verify it yourself.
          </Reveal>
          <Reveal as="li" from="left" delay={135}>
            <strong>Pick your AI in Settings.</strong>
            Install <a href="https://ollama.com" target="_blank" rel="noreferrer">Ollama</a> and pull a
            model (e.g. <code>ollama pull llama3.1</code>) to stay fully offline, or paste in an API key
            for OpenAI, Gemini, Deepseek, or Claude. Keys are stored in your OS credential manager and
            never sent anywhere but the provider you chose.
          </Reveal>
          <Reveal as="li" from="left" delay={180}>
            <strong>Start predicting.</strong>
            Head to PrizePicks, DraftKings, or Kalshi, enter a prop, and get a stat-grounded call you can
            keep chatting about. Refresh the fighter database anytime from Settings.
          </Reveal>
        </ol>

        <Reveal className="section__heading section__heading--spaced">
          <h2>Updates and your data</h2>
          <p>
            New releases install from <strong>Settings &rarr; Check for Updates</strong>: the app
            downloads the update, closes, installs it and reopens on its own. Your fighter database,
            chats and saved predictions come with you, because they live in your user profile rather
            than in the install folder - which also means uninstalling leaves them where they are.
          </p>
          <p>
            The <strong>portable zip</strong> works the other way round. Extract it anywhere and it
            keeps everything in a <code>data</code> folder beside the exe, so the whole thing moves
            with you to another drive or a USB stick, and deleting the folder leaves nothing behind.
            It does not update itself - you download and replace it by hand. Switch from portable to
            the installer later and the app offers to bring your existing chats and predictions
            across the first time it starts.
          </p>
        </Reveal>

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
