import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Reveal from "../components/Reveal";
import { api } from "../api/client";

/**
 * The page Stripe returns to after a successful payment.
 *
 * It reports on the entitlement; it does not grant it. Only the webhook does
 * that, because this redirect is something the browser can simply lose — a
 * closed tab, a dead battery, an over-eager extension — and access that depends
 * on the customer's tab surviving is access that sometimes silently doesn't
 * happen.
 *
 * So this polls, and if the webhook has not landed within a few seconds it says
 * "payment received, still activating" rather than implying anything failed.
 */
const POLL_INTERVAL_MS = 1200;
const POLL_ATTEMPTS = 9; // roughly ten seconds

export default function CheckoutSuccess() {
  const [state, setState] = useState<"waiting" | "active" | "slow">("waiting");

  useEffect(() => {
    let cancelled = false;
    let attempts = 0;

    async function poll() {
      if (cancelled) return;
      try {
        const me = await api.me();
        if (cancelled) return;
        if (me.entitlement.tier === "pro") {
          setState("active");
          return;
        }
      } catch {
        // Keep polling: a transient failure here is not the customer's problem.
      }
      attempts += 1;
      if (attempts >= POLL_ATTEMPTS) {
        setState("slow");
        return;
      }
      window.setTimeout(poll, POLL_INTERVAL_MS);
    }

    void poll();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="section section--first">
      <div className="container container--narrow">
        <Reveal className="section__heading">
          {state === "active" ? (
            <>
              <h2>You're Pro</h2>
              <p>
                Everything is unlocked. Open the desktop app and sign in from Settings to
                activate this machine.
              </p>
            </>
          ) : state === "slow" ? (
            <>
              <h2>Payment received</h2>
              <p>
                Your payment went through and we're still finishing activation. This usually takes
                a few seconds — refresh your account page shortly. Nothing else is needed from you.
              </p>
            </>
          ) : (
            <>
              <h2>Activating…</h2>
              <p>Confirming your payment with our provider.</p>
            </>
          )}
        </Reveal>

        <div className="acct-actions acct-actions--centred">
          <Link className="btn btn--primary" to="/account">Go to your account</Link>
          <Link className="btn btn--ghost" to="/download">Download the app</Link>
        </div>
      </div>
    </section>
  );
}
