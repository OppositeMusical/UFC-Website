import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "../src/App";

/**
 * Ad popup behaviour.
 *
 * The rotation rule is the fiddly part: "every other page switch" has to
 * count switches rather than renders, ignore the landing, and ignore
 * same-page anchor links - the navbar has two of those.
 */

function mockVersionJson(body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      String(url).includes("version.json")
        ? Promise.resolve({ ok: true, json: () => Promise.resolve(body) })
        : Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
    ) as unknown as typeof fetch
  );
}

beforeEach(() => {
  // The switch counter lives in sessionStorage; without this the rhythm
  // leaks between tests and they pass or fail depending on order.
  window.sessionStorage.clear();
  mockVersionJson({
    version: "0.5.2",
    downloadUrl: "/downloads/MMA-Assist-0.5.2-portable-win64.zip",
    fileName: "MMA-Assist-0.5.2-portable-win64.zip",
    kind: "portable",
    sizeBytes: 244388340,
    sha256: "a".repeat(64),
  });
});

function renderApp(at = "/") {
  return render(
    <MemoryRouter initialEntries={[at]}>
      <App />
    </MemoryRouter>
  );
}

/** Navbar links only - the pages contain their own "Download" links. */
function navLink(name: RegExp) {
  const header = document.querySelector("header");
  if (!header) throw new Error("navbar not rendered");
  return within(header as HTMLElement).getByRole("link", { name });
}

const adDialog = () => screen.queryByRole("dialog");

describe("navigation ad rotation", () => {
  it("does not fire on the landing page", () => {
    // Arriving is not "switching pages", and an interstitial before anyone
    // has seen the content is what search engines penalise.
    renderApp();
    expect(adDialog()).not.toBeInTheDocument();
  });

  it("fires on the first page switch", () => {
    renderApp();
    fireEvent.click(navLink(/^Download$/));
    expect(adDialog()).toBeInTheDocument();
  });

  it("skips the second switch and fires again on the third", () => {
    renderApp();

    fireEvent.click(navLink(/^Download$/)); // switch 1 -> ad
    expect(adDialog()).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /close advertisement/i }));
    expect(adDialog()).not.toBeInTheDocument();

    fireEvent.click(navLink(/^About$/)); // switch 2 -> quiet
    expect(adDialog()).not.toBeInTheDocument();

    fireEvent.click(navLink(/^Download$/)); // switch 3 -> ad
    expect(adDialog()).toBeInTheDocument();
  });

  it("ignores same-page anchor links", () => {
    // "Features" and "How It Works" are /#anchors on the page you are
    // already on. Counting them would fire an ad for scrolling.
    renderApp();
    fireEvent.click(navLink(/Features/));
    expect(adDialog()).not.toBeInTheDocument();
    fireEvent.click(navLink(/How It Works/));
    expect(adDialog()).not.toBeInTheDocument();
  });

  it("continues the rhythm across a reload rather than restarting it", () => {
    // Otherwise refreshing is a one-click way to never see an ad.
    const first = renderApp();
    fireEvent.click(navLink(/^Download$/)); // switch 1 -> ad
    expect(adDialog()).toBeInTheDocument();
    first.unmount();

    renderApp(); // "reload"
    fireEvent.click(navLink(/^About$/)); // switch 2 -> still quiet
    expect(adDialog()).not.toBeInTheDocument();
  });
});

describe("ad modal", () => {
  function openAd() {
    renderApp();
    fireEvent.click(navLink(/^Download$/));
    return screen.getByRole("dialog");
  }

  it("is labelled as advertising", () => {
    openAd();
    expect(screen.getByText(/^Advertisement$/i)).toBeInTheDocument();
  });

  it("is a real modal dialog for assistive tech", () => {
    const dialog = openAd();
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("aria-labelledby");
  });

  it("closes on Escape", () => {
    openAd();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(adDialog()).not.toBeInTheDocument();
  });

  it("closes on a backdrop click but not a click inside the card", () => {
    const dialog = openAd();
    fireEvent.click(dialog);
    expect(adDialog()).toBeInTheDocument();

    fireEvent.click(document.querySelector(".ad-backdrop") as HTMLElement);
    expect(adDialog()).not.toBeInTheDocument();
  });

  it("releases the page scroll lock when dismissed", () => {
    openAd();
    expect(document.body.style.overflow).toBe("hidden");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(document.body.style.overflow).not.toBe("hidden");
  });

  it("marks the outbound link sponsored and opener-safe", () => {
    openAd();
    const cta = within(screen.getByRole("dialog")).getByRole("link");
    expect(cta).toHaveAttribute("target", "_blank");
    expect(cta.getAttribute("rel")).toContain("noopener");
    expect(cta.getAttribute("rel")).toContain("sponsored");
  });
});

describe("download ad", () => {
  it("fires when a download starts", async () => {
    renderApp("/download");
    const link = await screen.findByRole("link", { name: /Download for Windows/i });
    fireEvent.click(link);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("does not gate the download itself", async () => {
    // The href has to stay intact and the click must not be prevented -
    // an ad that swallows the download is the failure mode worth guarding.
    renderApp("/download");
    const link = await screen.findByRole("link", { name: /Download for Windows/i });
    expect(link).toHaveAttribute("href", "/downloads/MMA-Assist-0.5.2-portable-win64.zip");
    expect(link).toHaveAttribute("download");

    const clickEvent = new MouseEvent("click", { bubbles: true, cancelable: true });
    link.dispatchEvent(clickEvent);
    expect(clickEvent.defaultPrevented).toBe(false);
  });

  it("says the download is already running", async () => {
    renderApp("/download");
    fireEvent.click(await screen.findByRole("link", { name: /Download for Windows/i }));
    expect(await screen.findByText(/already started/i)).toBeInTheDocument();
  });
});
