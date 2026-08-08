import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import Reveal from "../components/Reveal";
import { api } from "../api/client";

const PROVIDER_LABELS: Record<string, string> = {
  google: "Continue with Google",
  github: "Continue with GitHub",
};

export default function Login() {
  const [providers, setProviders] = useState<string[] | null>(null);
  const [params] = useSearchParams();

  // Where to land afterwards. Only a relative path is ever passed on, and the
  // server refuses anything off-site regardless - an auth endpoint that echoes
  // an arbitrary redirect is a phishing primitive.
  const rawNext = params.get("next") ?? "/account";
  const next = rawNext.startsWith("/") && !rawNext.startsWith("//") ? rawNext : "/account";
  const failed = params.get("error");

  useEffect(() => {
    api
      .providers()
      .then((response) => setProviders(response.providers))
      .catch(() => setProviders([]));
  }, []);

  return (
    <section className="section section--first">
      <div className="container container--narrow">
        <Reveal className="section__heading">
          <h2>Sign in</h2>
          <p>
            There is no password to create or forget — MMA Assist uses your existing Google or
            GitHub account.
          </p>
        </Reveal>

        {failed && (
          <div className="acct-alert">
            That sign-in didn't complete. Please try again.
          </div>
        )}

        <Reveal delay={80} from="scale">
          <div className="acct-card acct-card--centred">
            {providers === null && <p className="acct-muted">Loading…</p>}

            {providers?.length === 0 && (
              <p className="acct-muted">
                Sign-in isn't available right now. Please try again later.
              </p>
            )}

            {providers?.map((provider) => (
              <a key={provider} className="btn btn--primary acct-btn--block"
                 href={api.loginUrl(provider, next)}>
                {PROVIDER_LABELS[provider] ?? `Continue with ${provider}`}
              </a>
            ))}

            <p className="acct-fineprint">
              We store your email address, your plan, and which devices you've activated. We never
              see your predictions, your chats, or your AI provider keys — those stay on your
              machine.
            </p>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
