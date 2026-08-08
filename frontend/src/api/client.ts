/**
 * Client for the accounts service.
 *
 * Two things worth knowing before changing anything here:
 *
 * - Every request sends `credentials: "include"`. The session lives in an
 *   HttpOnly cookie, so there is no token in JavaScript for an XSS to steal —
 *   and equally no token this module could attach by hand.
 * - Errors arrive as RFC 9457 `application/problem+json` carrying a stable
 *   `code`. Branch on the code, never on the prose, which is copy that changes.
 */

const API_BASE = (
  (import.meta.env.VITE_ACCOUNTS_API_URL as string | undefined) ?? "http://localhost:8080"
).replace(/\/$/, "");

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }

  /** True when signing in would plausibly fix this. */
  get isUnauthenticated(): boolean {
    return this.status === 401;
  }
}

export interface Plan {
  id: string;
  displayName: string;
  description: string | null;
  kind: "subscription" | "one_time";
  interval: "month" | "year" | null;
  amountMinor: number;
  currency: string;
  features: Record<string, boolean>;
}

export interface Entitlement {
  tier: "free" | "pro";
  source: "subscription" | "lifetime" | "grant" | null;
  features: Record<string, boolean>;
  validUntil: string | null;
}

export interface Device {
  id: string;
  name: string | null;
  appVersion: string | null;
  lastSeenAt: string;
}

export interface Me {
  account: { id: string; email: string; displayName: string | null; avatarUrl: string | null };
  entitlement: Entitlement;
  linkedProviders: string[];
  devices: Device[];
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      credentials: "include",
      headers: init.body ? { "Content-Type": "application/json" } : undefined,
      ...init,
    });
  } catch {
    // A network failure and a 500 are the same to a caller, but the message
    // should not claim the server said something when it never answered.
    throw new ApiError("Could not reach the server.", "network_error", 0);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    const code = (body && (body.code as string)) || "unknown";
    const detail = (body && (body.detail as string)) || "Something went wrong.";
    throw new ApiError(detail, code, response.status);
  }

  return body as T;
}

export const api = {
  /** Where to send the browser to start sign-in. A full page navigation, not fetch. */
  loginUrl(provider: string, returnPath = "/account"): string {
    return `${API_BASE}/v1/auth/${provider}/start?redirect=${encodeURIComponent(returnPath)}`;
  },

  providers(): Promise<{ providers: string[] }> {
    return request("/v1/auth/providers");
  },

  plans(): Promise<{ plans: Plan[] }> {
    return request("/v1/plans");
  },

  me(): Promise<Me> {
    return request("/v1/me");
  },

  /** The body names a plan, never a price — the amount is decided server-side. */
  startCheckout(planId: string): Promise<{ checkoutUrl: string }> {
    return request("/v1/checkout", { method: "POST", body: JSON.stringify({ planId }) });
  },

  portal(): Promise<{ portalUrl: string }> {
    return request("/v1/portal", { method: "POST" });
  },

  logout(): Promise<void> {
    return request("/v1/auth/logout", { method: "POST" });
  },

  revokeDevice(deviceId: string): Promise<void> {
    return request(`/v1/devices/${deviceId}`, { method: "DELETE" });
  },

  closeAccount(): Promise<{ status: string; retained: string }> {
    return request("/v1/me", { method: "DELETE" });
  },
};

export function formatPrice(amountMinor: number, currency: string): string {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: currency.toUpperCase(),
    // Whole-dollar prices read better without the trailing zeros; anything
    // with cents still shows them.
    minimumFractionDigits: amountMinor % 100 === 0 ? 0 : 2,
  }).format(amountMinor / 100);
}
