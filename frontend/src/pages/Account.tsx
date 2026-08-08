import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Reveal from "../components/Reveal";
import { ApiError, api, type Me } from "../api/client";

export default function Account() {
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    try {
      setMe(await api.me());
    } catch (err) {
      if (err instanceof ApiError && err.isUnauthenticated) {
        navigate("/login?next=/account");
        return;
      }
      setError("Couldn't load your account.");
    }
  }, [navigate]);

  useEffect(() => {
    void load();
  }, [load]);

  async function openPortal() {
    setBusy(true);
    setError(null);
    try {
      const { portalUrl } = await api.portal();
      window.location.href = portalUrl;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't open billing.");
      setBusy(false);
    }
  }

  async function signOut() {
    await api.logout().catch(() => undefined);
    navigate("/");
  }

  async function revoke(deviceId: string) {
    try {
      await api.revokeDevice(deviceId);
      await load();
    } catch {
      setError("Couldn't remove that device.");
    }
  }

  async function closeAccount() {
    // Irreversible and it cancels a live subscription, so it gets a
    // confirmation rather than a single stray click.
    if (!window.confirm(
      "Delete your account? This cancels any active subscription immediately and cannot be undone."
    )) {
      return;
    }
    try {
      await api.closeAccount();
      navigate("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't delete the account.");
    }
  }

  if (!me) {
    return (
      <section className="section section--first">
        <div className="container">
          {error ? <div className="acct-alert">{error}</div> : <p className="acct-muted">Loading…</p>}
        </div>
      </section>
    );
  }

  const { account, entitlement, devices, linkedProviders } = me;
  const renewal = entitlement.validUntil
    ? new Date(entitlement.validUntil).toLocaleDateString()
    : null;

  return (
    <section className="section section--first">
      <div className="container">
        <Reveal className="section__heading">
          <h2>Your account</h2>
          <p>{account.email}</p>
        </Reveal>

        {error && <div className="acct-alert">{error}</div>}

        <div className="acct-card">
          <h3>Plan</h3>
          <p className="acct-plan__price">
            {entitlement.tier === "pro" ? "Pro" : "Free"}
            {entitlement.source === "lifetime" && <span> · lifetime</span>}
          </p>
          {renewal && (
            <p className="acct-muted">
              {entitlement.source === "subscription" ? "Renews or ends" : "Valid until"} {renewal}
            </p>
          )}
          {entitlement.source === "lifetime" && (
            <p className="acct-muted">Yours for good, including future versions.</p>
          )}

          <div className="acct-actions">
            {entitlement.tier === "pro" ? (
              <button className="btn btn--primary" onClick={openPortal} disabled={busy}>
                {busy ? "Opening…" : "Manage billing"}
              </button>
            ) : (
              <Link className="btn btn--primary" to="/pricing">See plans</Link>
            )}
          </div>
          {entitlement.tier === "pro" && (
            <p className="acct-fineprint">
              Cancelling, changing your card and downloading invoices all happen on Stripe's
              billing portal.
            </p>
          )}
        </div>

        <div className="acct-card">
          <h3>Devices</h3>
          {devices.length === 0 ? (
            <p className="acct-muted">
              No devices activated yet. Sign in from the desktop app to activate one.
            </p>
          ) : (
            <ul className="acct-devices">
              {devices.map((device) => (
                <li key={device.id}>
                  <div>
                    <strong>{device.name ?? "Unnamed device"}</strong>
                    <span className="acct-muted">
                      {device.appVersion ? ` · v${device.appVersion}` : ""}
                      {` · last seen ${new Date(device.lastSeenAt).toLocaleDateString()}`}
                    </span>
                  </div>
                  <button className="btn btn--ghost" onClick={() => revoke(device.id)}>
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="acct-card">
          <h3>Sign-in</h3>
          <p className="acct-muted">
            Linked to {linkedProviders.join(" and ")}. There is no password on this account.
          </p>
          <div className="acct-actions">
            <button className="btn btn--ghost" onClick={signOut}>Sign out</button>
            <button className="btn btn--danger" onClick={closeAccount}>Delete account</button>
          </div>
          <p className="acct-fineprint">
            Deleting removes your profile, sign-in links and devices. Payment records are kept
            because tax and anti-fraud rules require it.
          </p>
        </div>
      </div>
    </section>
  );
}
