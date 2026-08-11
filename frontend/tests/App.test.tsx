import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "../src/App";

/**
 * Routes by URL: /version.json returns the manifest, anything else is the
 * HEAD probe DownloadButton makes to confirm the artifact exists.
 * `assetOk: false` simulates a deploy where the gitignored installer is
 * absent - which is the normal state on Railway.
 */
function mockVersionJson(body: unknown, ok = true, assetOk = true) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      String(url).includes("version.json")
        ? Promise.resolve({ ok, json: () => Promise.resolve(body) })
        : Promise.resolve({ ok: assetOk, json: () => Promise.resolve({}) })
    ) as unknown as typeof fetch
  );
}

beforeEach(() => {
  mockVersionJson({
    version: "0.1.0",
    downloadUrl: "/downloads/MMA-Assist-0.2.0-portable-win64.zip",
    fileName: "MMA-Assist-0.2.0-portable-win64.zip",
    kind: "portable",
    sizeBytes: 243864618,
    sha256: "01ef96c645ec4155342da68721fd5019ab1a29112ea12ac7df2a080f34672598",
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
    expect(screen.getByText("Assist")).toBeInTheDocument();
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

  it("names the developer and links to both profiles", () => {
    render(
      <MemoryRouter initialEntries={["/about"]}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByRole("heading", { name: /Christepher Irving/i })).toBeInTheDocument();

    const github = screen.getAllByRole("link", { name: /GitHub/i });
    expect(github.length).toBeGreaterThan(0);
    expect(github[0]).toHaveAttribute("href", "https://github.com/OppositeMusical");

    const linkedin = screen.getAllByRole("link", { name: /LinkedIn/i });
    expect(linkedin[0].getAttribute("href")).toContain("linkedin.com/in/christepher-irving");
  });

  it("no longer shows the coming-soon placeholder", () => {
    render(
      <MemoryRouter initialEntries={["/about"]}>
        <App />
      </MemoryRouter>
    );
    expect(screen.queryByText(/Coming soon/i)).not.toBeInTheDocument();
  });

  it("opens external profile links safely", () => {
    // rel=noreferrer matters on target=_blank: without it the opened tab
    // gets a handle on window.opener.
    render(
      <MemoryRouter initialEntries={["/about"]}>
        <App />
      </MemoryRouter>
    );
    for (const link of screen.getAllByRole("link", { name: /GitHub|LinkedIn/i })) {
      expect(link).toHaveAttribute("target", "_blank");
      expect(link.getAttribute("rel")).toContain("noreferrer");
    }
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

describe("DownloadButton - installer manifest (0.5.0+)", () => {
  const INSTALLER_MANIFEST = {
    version: "0.5.0",
    downloadUrl: "/downloads/MMA-Assist-0.5.0-setup-win64.exe",
    fileName: "MMA-Assist-0.5.0-setup-win64.exe",
    kind: "nsis",
    sizeBytes: 251658240,
    sha256: "a".repeat(64),
    platforms: {
      win: {
        downloadUrl: "/downloads/MMA-Assist-0.5.0-setup-win64.exe",
        kind: "nsis",
        sizeBytes: 251658240,
      },
      winPortable: {
        downloadUrl: "/downloads/MMA-Assist-0.5.0-portable-win64.zip",
        fileName: "MMA-Assist-0.5.0-portable-win64.zip",
        kind: "portable",
        sizeBytes: 243864618,
      },
    },
  };

  function renderDownload() {
    return render(
      <MemoryRouter initialEntries={["/download"]}>
        <App />
      </MemoryRouter>
    );
  }

  it("offers the installer as the primary download", async () => {
    mockVersionJson(INSTALLER_MANIFEST);
    renderDownload();

    const link = await screen.findByRole("link", { name: /Download for Windows/i });
    expect(link).toHaveAttribute("href", "/downloads/MMA-Assist-0.5.0-setup-win64.exe");
    expect(link).toHaveAttribute("download");
  });

  it("tells the user the installer self-updates", async () => {
    // The reason the installer is primary at all - if the page doesn't say
    // so, the portable build looks like the simpler choice and people end
    // up on the channel that cannot update itself.
    mockVersionJson(INSTALLER_MANIFEST);
    renderDownload();
    await screen.findByRole("link", { name: /Download for Windows/i });
    expect(screen.getByText(/Updates itself/i)).toBeInTheDocument();
  });

  it("keeps the portable zip available behind a disclosure", async () => {
    mockVersionJson(INSTALLER_MANIFEST);
    const { container } = renderDownload();
    await screen.findByRole("link", { name: /Download for Windows/i });

    const toggle = screen.getByRole("button", { name: /portable/i });
    expect(container.querySelector(".portable-option__body")).toBeNull();

    fireEvent.click(toggle);

    // jsdom has no showDirectoryPicker, so the zip renders as a plain link -
    // the same fallback Firefox and Safari users get.
    const zip = await screen.findByRole("link", { name: /Download portable zip/i });
    expect(zip).toHaveAttribute("href", "/downloads/MMA-Assist-0.5.0-portable-win64.zip");
  });

  it("still renders when no portable entry is published", async () => {
    const { platforms, ...installerOnly } = INSTALLER_MANIFEST;
    mockVersionJson({ ...installerOnly, platforms: { win: platforms.win } });
    renderDownload();

    await screen.findByRole("link", { name: /Download for Windows/i });
    expect(screen.queryByRole("button", { name: /portable/i })).not.toBeInTheDocument();
  });
});

describe("DownloadButton", () => {
  it("links to the portable zip and shows version, size and checksum", async () => {
    render(
      <MemoryRouter initialEntries={["/download"]}>
        <App />
      </MemoryRouter>
    );

    // jsdom has no showDirectoryPicker, so this exercises the fallback that
    // Firefox and Safari users get: a plain download link.
    const link = await screen.findByRole("link", { name: /Download for Windows/i });
    expect(link).toHaveAttribute("href", "/downloads/MMA-Assist-0.2.0-portable-win64.zip");
    expect(link).toHaveAttribute("download");
    expect(screen.getByText(/Version 0\.1\.0/)).toBeInTheDocument();
    expect(screen.getByText(/233 MB/)).toBeInTheDocument();
    // Full hash, not truncated - a partial checksum can't be verified.
    expect(
      screen.getByText("01ef96c645ec4155342da68721fd5019ab1a29112ea12ac7df2a080f34672598")
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
      downloadUrl: "/downloads/MMA-Assist-0.2.0-portable-win64.zip",
      kind: "portable",
      sizeBytes: 186904009,
    });

    render(
      <MemoryRouter initialEntries={["/download"]}>
        <App />
      </MemoryRouter>
    );
    await screen.findByRole("link", { name: /Download for Windows/i });
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

describe("artifact availability", () => {
  it("hides the button when version.json points at a file that isn't deployed", async () => {
    // frontend/public/downloads/ is gitignored, so a host that builds from
    // the repo has the manifest but not the 180MB installer.
    mockVersionJson(
      {
        version: "0.1.0",
        downloadUrl: "/downloads/MMA-Assist-0.2.0-portable-win64.zip",
        kind: "portable",
      },
      true,
      false
    );

    render(
      <MemoryRouter initialEntries={["/download"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText(/Build not available yet/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Download for Windows/i })).not.toBeInTheDocument();
  });

  it("trusts absolute URLs without probing them", async () => {
    // A release host will refuse a cross-origin HEAD; a CORS failure is not
    // evidence the file is missing, so absolute URLs are taken at face value.
    mockVersionJson(
      {
        version: "0.1.0",
        downloadUrl: "https://github.com/OppositeMusical/UFC-Website/releases/latest/download/x.exe",
        kind: "portable",
      },
      true,
      false
    );

    render(
      <MemoryRouter initialEntries={["/download"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByRole("link", { name: /Download for Windows/i })).toBeInTheDocument();
  });
});

describe("unavailable-build messaging", () => {
  it("shows a public-facing message off localhost, not the build script", async () => {
    // jsdom's default location is http://localhost/, so override it to look
    // like the deployed site. Telling visitors to run a Python script is a
    // leaked internal instruction.
    const original = window.location;
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...original, hostname: "ufc-website.up.railway.app" },
    });

    mockVersionJson(
      { version: "0.1.0", downloadUrl: "/downloads/MMA-Assist-0.2.0-portable-win64.zip", kind: "portable" },
      true,
      false
    );

    render(
      <MemoryRouter initialEntries={["/download"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText(/isn't published yet/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /releases page/i })).toBeInTheDocument();
    expect(screen.queryByText(/build_release\.py/)).not.toBeInTheDocument();

    Object.defineProperty(window, "location", { configurable: true, value: original });
  });

  it("keeps the build hint when running locally", async () => {
    mockVersionJson(
      { version: "0.1.0", downloadUrl: "/downloads/MMA-Assist-0.2.0-portable-win64.zip", kind: "portable" },
      true,
      false
    );

    render(
      <MemoryRouter initialEntries={["/download"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText(/build_release\.py/)).toBeInTheDocument();
  });
});

describe("folder picker", () => {
  it("offers a folder chooser when the browser supports it", async () => {
    // Chromium exposes showDirectoryPicker; jsdom does not, so stub it to
    // exercise the path Chrome/Edge users actually get.
    const picker = vi.fn(() => Promise.resolve({ name: "MyApps" }));
    Object.defineProperty(window, "showDirectoryPicker", { configurable: true, writable: true, value: picker });
    Object.defineProperty(window, "isSecureContext", { configurable: true, writable: true, value: true });

    render(
      <MemoryRouter initialEntries={["/download"]}>
        <App />
      </MemoryRouter>
    );

    // A <button>, not an <a>: the file is written by JS into the chosen
    // directory rather than handed to the browser's download manager.
    const btn = await screen.findByRole("button", { name: /Choose Folder & Download/i });
    expect(btn).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Download for Windows/i })).not.toBeInTheDocument();

    delete (window as unknown as Record<string, unknown>).showDirectoryPicker;
  });

  it("falls back to a plain download link without picker support", async () => {
    // Firefox and Safari. The end result is the same file; the browser's
    // own save dialog picks the destination.
    expect("showDirectoryPicker" in window).toBe(false);

    render(
      <MemoryRouter initialEntries={["/download"]}>
        <App />
      </MemoryRouter>
    );

    const link = await screen.findByRole("link", { name: /Download for Windows/i });
    expect(link).toHaveAttribute("download");
  });
});

describe("macOS download", () => {
  it("stays 'coming soon' while no mac artifact is published", async () => {
    // The default mock has only a Windows entry. The card must not advertise
    // a build that does not exist.
    render(
      <MemoryRouter initialEntries={["/download"]}>
        <App />
      </MemoryRouter>
    );
    expect(await screen.findByText(/Download for macOS/i)).toBeInTheDocument();
    expect(screen.getByText(/Coming soon/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Download for macOS/i })).not.toBeInTheDocument();
  });

  it("becomes a real download once version.json carries a mac artifact", async () => {
    mockVersionJson({
      version: "0.4.0",
      downloadUrl: "/downloads/MMA-Assist-0.4.0-portable-win64.zip",
      kind: "portable",
      platforms: {
        win: { downloadUrl: "/downloads/MMA-Assist-0.4.0-portable-win64.zip", kind: "portable" },
        mac: {
          downloadUrl: "https://example.test/MMA-Assist-0.4.0-macos.dmg",
          kind: "dmg",
          sizeBytes: 243867732,
        },
      },
    });

    render(
      <MemoryRouter initialEntries={["/download"]}>
        <App />
      </MemoryRouter>
    );

    const link = await screen.findByRole("link", { name: /Download for macOS/i });
    expect(link).toHaveAttribute("href", "https://example.test/MMA-Assist-0.4.0-macos.dmg");
    expect(screen.getByText(/macOS 11 or later/)).toBeInTheDocument();
    // Gatekeeper refuses unsigned downloads outright and calls them
    // "damaged" - saying so is what stops users deleting a working file.
    expect(screen.getByText(/damaged and can't be opened/i)).toBeInTheDocument();
  });
});
