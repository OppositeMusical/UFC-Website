// Fills in the AI-provider status chip after page load. Kept out of the
// server-rendered response because resolving it means a live check (is the
// Ollama daemon answering? is an API key in the keyring?) and the dashboard
// should paint immediately rather than stall behind it.
document.addEventListener("DOMContentLoaded", () => {
  const chip = document.getElementById("provider-chip");
  const detail = document.getElementById("provider-detail");
  if (!chip) return;

  const textEl = chip.querySelector(".status-chip__text");

  function render(level, label, detailText) {
    chip.classList.remove("checking", "ok", "warn", "err");
    chip.classList.add(level);
    textEl.textContent = label;
    chip.title = detailText || label;
    if (detailText) {
      detail.textContent = detailText;
      detail.hidden = false;
    } else {
      detail.hidden = true;
    }
  }

  fetch("/api/status/provider")
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status))))
    .then((data) => render(data.level, data.label, data.detail))
    .catch(() => render("err", "Status check failed", "Could not reach the local app server."));
});

// Update banner. Only ever shown for an actual newer release - "couldn't
// check" stays silent, because a warning a user can't act on is noise.
//
// Two sources, deliberately not mixed. In the desktop app the updater in the
// main process is authoritative, because it is the thing that will actually
// perform the install; driving the banner off the website manifest as well
// would let the two disagree (a GitHub release exists, version.json has not
// caught up yet) and show a prompt the Settings page then contradicts.
document.addEventListener("DOMContentLoaded", () => {
  const banner = document.getElementById("update-banner");
  if (!banner) return;

  const titleEl = document.getElementById("update-banner-title");
  const detailEl = document.getElementById("update-banner-detail");
  const linkEl = document.getElementById("update-banner-link");
  const dismissEl = document.getElementById("update-banner-dismiss");

  const dismissKey = (version) => `ufcpredictor:update-dismissed:${version}`;

  // Dismissal is per-version, so the banner comes back for the next release
  // instead of being silenced forever by one click.
  function show(version, detail, { dismissible = true } = {}) {
    if (dismissible && localStorage.getItem(dismissKey(version))) return;
    titleEl.textContent = `Version ${version} is available`;
    detailEl.textContent = detail;
    banner.hidden = false;
    dismissEl.hidden = !dismissible;
    if (dismissible) {
      dismissEl.addEventListener(
        "click",
        () => {
          localStorage.setItem(dismissKey(version), "1");
          banner.hidden = true;
        },
        { once: true }
      );
    }
  }

  const desktopUpdates = window.mmaAssist && window.mmaAssist.updates;

  if (desktopUpdates) {
    // Same-origin route, so no safeExternalUrl dance and no new window -
    // the install flow lives on the Settings page.
    linkEl.href = "/settings/";
    linkEl.removeAttribute("target");
    linkEl.textContent = "Update";

    desktopUpdates.onState((state) => {
      if (state.status === "available") {
        show(state.version, "Download and install it from Settings.");
      } else if (state.status === "downloaded") {
        titleEl.textContent = `Version ${state.version} is ready to install`;
        detailEl.textContent = "Finish the update from Settings.";
        banner.hidden = false;
      } else if (state.status === "unsupported") {
        checkViaServer();
      }
    });
    desktopUpdates.state().then((state) => {
      if (state.status === "unsupported") checkViaServer();
    });
    desktopUpdates.check();
    return;
  }

  checkViaServer();

  function checkViaServer() {
    fetch("/api/updates/check")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status))))
      .then((data) => {
        if (data.status !== "available" && data.status !== "required") return;
        // Manifest-supplied, therefore untrusted - see safeExternalUrl.
        linkEl.href =
          safeExternalUrl(data.downloadPageUrl) || safeExternalUrl(data.downloadUrl) || "#";
        // A release flagged as required is not something to hide behind a
        // dismissal - the running version is known-bad.
        show(data.latestVersion, `You're on ${data.currentVersion}.`, {
          dismissible: data.status !== "required",
        });
      })
      .catch(() => {
        /* offline is normal for a local-first app - stay quiet */
      });
  }
});
