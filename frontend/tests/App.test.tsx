import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "../src/App";

function mockVersionJson(body: unknown, ok = true) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve({ ok, json: () => Promise.resolve(body) })) as unknown as typeof fetch
  );
}

beforeEach(() => {
  mockVersionJson({
    version: "0.1.0",
    downloadUrl: "/downloads/UFCPredictor-0.1.0-windows.zip",
    sizeBytes: 107027534,
    sha256: "1c1710234bc6ec664a68484953588125f4e380c35a6880cb67c7dd871959d781",
  });
});

describe("App", () => {
  it("renders the nav brand and every top-level nav link", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByText("Predictor")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Features" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "How It Works" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download" })).toBeInTheDocument();
  });

  it("shows the download CTA on the home page", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByRole("link", { name: "Download the App" })).toBeInTheDocument();
  });

  it("renders the download page with a download button", async () => {
    render(
      <MemoryRouter initialEntries={["/download"]}>
        <App />
      </MemoryRouter>
    );
    expect(await screen.findByRole("link", { name: /Download for Windows/i })).toBeInTheDocument();
    expect(screen.getByText(/informational and entertainment purposes only/i)).toBeInTheDocument();
  });
});

describe("About the Developer page", () => {
  it("is reachable from the navbar", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByRole("link", { name: "About" })).toBeInTheDocument();
  });

  it("renders a coming-soon placeholder with no biography content yet", () => {
    render(
      <MemoryRouter initialEntries={["/about"]}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByRole("heading", { name: /About the Developer/i })).toBeInTheDocument();
    expect(screen.getByText(/Coming soon/i)).toBeInTheDocument();
  });
});

describe("scroll reveal", () => {
  it("falls back to visible when IntersectionObserver is unavailable", () => {
    // jsdom has no IntersectionObserver. Content must still render and be
    // readable - a reveal that never fires would leave it at opacity 0.
    expect(typeof IntersectionObserver).toBe("undefined");

    const { container } = render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );
    const reveals = container.querySelectorAll(".reveal");
    expect(reveals.length).toBeGreaterThan(0);
    reveals.forEach((el) => expect(el).toHaveClass("is-visible"));
  });
});

describe("DownloadButton", () => {
  it("links to the real artifact and shows version, size and checksum", async () => {
    render(
      <MemoryRouter initialEntries={["/download"]}>
        <App />
      </MemoryRouter>
    );

    const link = await screen.findByRole("link", { name: /Download for Windows/i });
    expect(link).toHaveAttribute("href", "/downloads/UFCPredictor-0.1.0-windows.zip");
    expect(link).toHaveAttribute("download");
    expect(screen.getByText(/Version 0\.1\.0/)).toBeInTheDocument();
    expect(screen.getByText(/102 MB/)).toBeInTheDocument();
    // Full hash, not truncated - a partial checksum can't be verified.
    expect(
      screen.getByText("1c1710234bc6ec664a68484953588125f4e380c35a6880cb67c7dd871959d781")
    ).toBeInTheDocument();
  });

  it("refuses to render a live-looking button for the placeholder release URL", async () => {
    // The committed default points at a github.com/your-org/... URL that
    // 404s. A button that looks ready and then fails is worse than none.
    mockVersionJson({
      version: "0.1.0",
      downloadUrl: "https://github.com/your-org/ufc-predictor/releases/latest/download/UFCPredictor-windows.zip",
    });

    render(
      <MemoryRouter initialEntries={["/download"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText(/Build not available yet/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Download for Windows/i })).not.toBeInTheDocument();
  });

  it("degrades gracefully when version.json is missing", async () => {
    mockVersionJson({}, false);

    render(
      <MemoryRouter initialEntries={["/download"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText(/Build not available yet/i)).toBeInTheDocument();
  });
});
