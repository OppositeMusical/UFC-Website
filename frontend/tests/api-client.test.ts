import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, formatPrice } from "../src/api/client";

function respond(status: number, body: unknown, ok = status < 400) {
  return {
    ok,
    status,
    json: async () => body,
  } as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("sends credentials so the session cookie travels", async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond(200, { plans: [] }));
    vi.stubGlobal("fetch", fetchMock);

    await api.plans();

    const [, init] = fetchMock.mock.calls[0];
    expect(init.credentials).toBe("include");
  });

  it("surfaces the problem+json code rather than the prose", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        respond(403, { code: "device_limit_exceeded", detail: "Too many devices." }, false),
      ),
    );

    await expect(api.me()).rejects.toMatchObject({
      code: "device_limit_exceeded",
      status: 403,
    });
  });

  it("marks a 401 as recoverable by signing in", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(respond(401, { code: "unauthenticated", detail: "Sign in." }, false)),
    );

    const error = await api.me().catch((err) => err);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.isUnauthenticated).toBe(true);
  });

  it("does not claim the server answered when the network failed", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    const error = await api.plans().catch((err) => err);

    expect(error.code).toBe("network_error");
    expect(error.status).toBe(0);
  });

  it("copes with an error response that is not JSON at all", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 502,
        json: async () => {
          throw new Error("not json");
        },
      } as unknown as Response),
    );

    const error = await api.me().catch((err) => err);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(502);
  });

  it("names a plan when starting checkout, never a price", async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond(200, { checkoutUrl: "https://stripe.test/c" }));
    vi.stubGlobal("fetch", fetchMock);

    await api.startCheckout("lifetime");

    const [, init] = fetchMock.mock.calls[0];
    const body = JSON.parse(init.body);
    expect(body).toEqual({ planId: "lifetime" });
    expect(Object.keys(body)).not.toContain("amountMinor");
  });

  it("builds a login URL with an encoded return path", () => {
    expect(api.loginUrl("google", "/checkout/success?session_id=cs_1")).toContain(
      "redirect=%2Fcheckout%2Fsuccess%3Fsession_id%3Dcs_1",
    );
  });
});

describe("formatPrice", () => {
  it("drops the decimals on whole amounts and keeps them otherwise", () => {
    expect(formatPrice(7900, "usd")).toBe("$79");
    expect(formatPrice(499, "usd")).toBe("$4.99");
  });
});
