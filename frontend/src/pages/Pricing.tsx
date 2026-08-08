import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Reveal from "../components/Reveal";
import { ApiError, api, formatPrice, type Plan } from "../api/client";

const FEATURE_LABELS: Record<string, string> = {
  cloud_providers: "All cloud AI providers",
  all_platforms: "PrizePicks, DraftKings and Kalshi",
  kalshi_market: "Kalshi market questions",
  unlimited_history: "Unlimited prediction history",
};

export default function Pricing() {
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyPlan, setBusyPlan] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api
      .plans()
      .then((response) => setPlans(response.plans))
      .catch(() => setError("Couldn't load pricing. Please try again shortly."));
  }, []);

  async function buy(planId: string) {
    setBusyPlan(planId);
    setError(null);
    try {
      const { checkoutUrl } = await api.startCheckout(planId);
      // Stripe's own domain. Card details never touch this site.
      window.location.href = checkoutUrl;
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthenticated) {
        navigate("/login?next=/pricing");
        return;
      }
      setError(err instanceof ApiError ? err.message : "Couldn't start checkout.");
      setBusyPlan(null);
    }
  }

  return (
    <section className="section section--first">
      <div className="container">
        <Reveal className="section__heading">
          <h2>Pricing</h2>
          <p>
            MMA Assist is free to download and free to use with a local model. Pro unlocks the
            cloud providers, every prediction platform, and unlimited history.
          </p>
        </Reveal>

        {error && <div className="acct-alert">{error}</div>}

        {!plans && !error && <p className="acct-muted">Loading plans…</p>}

        <div className="acct-plans">
          {plans?.map((plan, index) => (
            <Reveal key={plan.id} delay={index * 80} from="scale">
              <div className={`acct-plan ${plan.kind === "one_time" ? "acct-plan--feature" : ""}`}>
                <h3>{plan.displayName}</h3>
                <p className="acct-plan__price">
                  {formatPrice(plan.amountMinor, plan.currency)}
                  {plan.interval && <span>/{plan.interval}</span>}
                </p>
                {plan.description && <p className="acct-plan__blurb">{plan.description}</p>}

                <ul className="acct-plan__features">
                  {Object.entries(plan.features)
                    .filter(([, enabled]) => enabled)
                    .map(([key]) => (
                      <li key={key}>{FEATURE_LABELS[key] ?? key}</li>
                    ))}
                </ul>

                <button
                  className="btn btn--primary"
                  onClick={() => buy(plan.id)}
                  disabled={busyPlan !== null}
                >
                  {busyPlan === plan.id ? "Starting checkout…" : "Get " + plan.displayName}
                </button>
              </div>
            </Reveal>
          ))}
        </div>

        <div className="disclaimer-box">
          Payments are handled by Stripe. Card details are entered on Stripe's own pages and never
          reach this site or our servers. Cancel a subscription at any time from your account page.
        </div>
      </div>
    </section>
  );
}
