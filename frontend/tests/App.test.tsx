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
    downloadUrl: "/downloads/UFC-Predictor-Setup-0.1.0.exe",
    fileName: "UFC-Predictor-Setup-0.1.0.exe",
    kind: "installer",
    sizeBytes: 186904009,
    sha256: "b6a08e69d90c9cd519e1fb90777b181a23296c6b93bceaa7d80d37e2e46d96cf",
    releasedAt: "2026-08-04",
    releaseNotes: ["Runs as a real desktop app", "Kalshi market questions"],
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
    expect(await screen.findByRole("link", { name: /Download Installer/i })).toBeInTheDocument();
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
  it("links to the Electron installer and shows version, size and checksum", async () => {
    render(
      <MemoryRouter initialEntries={["/download"]}>
        <App />
      </MemoryRouter>
    );

    // "installer" kind changes the label - a .exe installer and a raw zip
    // are not the same promise to the user.
    const link = await screen.findByRole("link", { name: /Download Installer/i });
    expect(link).toHaveAttribute("href", "/downloads/UFC-Predictor-Setup-0.1.0.exe");
    expect(link).toHaveAttribute("download");
    expect(screen.getByText(/Version 0\.1\.0/)).toBeInTheDocument();
    expect(screen.getByText(/178 MB/)).toBeInTheDocument();
    // Full hash, not truncated - a partial checksum can't be verified.
    expect(
      screen.getByText("b6a08e69d90c9cd519e1fb90777b181a23296c6b93bceaa7d80d37e2e46d96cf")
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
    expect(screen.queryByRole("link", { name: /Download Installer/i })).not.toBeInTheDocument();
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

describe("release notes", () => {
  it("shows what's new for the published version", async () => {
    render(
      <MemoryRouter initialEntries={["/download"]}>
        <App />
      </MemoryRouter>
    );
    expect(await screen.findByText(/What's new in 0\.1\.0/)).toBeInTheDocument();
    expect(screen.getByText("Runs as a real desktop app")).toBeInTheDocument();
    expect(screen.getByText("Kalshi market questions")).toBeInTheDocument();
  });

  it("omits the section entirely when a release has no notes", async () => {
    mockVersionJson({
      version: "0.1.0",
      downloadUrl: "/downloads/UFC-Predictor-Setup-0.1.0.exe",
      kind: "installer",
      sizeBytes: 186904009,
    });

    render(
      <MemoryRouter initialEntries={["/download"]}>
        <App />
      </MemoryRouter>
    );
    await screen.findByRole("link", { name: /Download Installer/i });
    expect(screen.queryByText(/What's new/i)).not.toBeInTheDocument();
  });
});

describe("macOS download", () => {
  it("is shown as coming soon and is not clickable", async () => {
    render(
      <MemoryRouter initialEntries={["/download"]}>
        <App />
      </MemoryRouter>
    );

    const mac = await screen.findByText(/Download for macOS/i);
    expect(mac).toBeInTheDocument();
    expect(screen.getByText(/Coming soon/i)).toBeInTheDocument();

    // Deliberately not a link: there is nothing to download, and a dead
    // href would look available and fail on click.
    expect(screen.queryByRole("link", { name: /Download for macOS/i })).not.toBeInTheDocument();
    expect(mac.closest("[aria-disabled]")).toHaveAttribute("aria-disabled", "true");
  });

  it("still appears when the Windows build is unavailable", async () => {
    mockVersionJson({}, false);

    render(
      <MemoryRouter initialEntries={["/download"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText(/Build not available yet/i)).toBeInTheDocument();
    expect(screen.getByText(/Download for macOS/i)).toBeInTheDocument();
  });
});
