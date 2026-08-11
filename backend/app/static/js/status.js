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

  // Which version a dismissal click would silence. Set by show(), read by the
  // one click handler below - previously show() attached a fresh listener per
  // call, which meant a state sequence that reached the banner without going
  // through show() left the button inert.
  let dismissVersion = null;

  dismissEl.addEventListener("click", () => {
    // Dismissal is per-version, so the banner comes back for the next release
    // instead of being silenced forever by one click.
    if (dismissVersion) localStorage.setItem(dismissKey(dismissVersion), "1");
    hide();
  });

  function hide() {
    banner.hidden = true;
  }

  function show({ version, title, detail, dismissible = true }) {
    if (dismissible && localStorage.getItem(dismissKey(version))) return hide();
    titleEl.textContent = title;
    detailEl.textContent = detail;
    dismissVersion = dismissible ? version : null;
    dismissEl.hidden = !dismissible;
    banner.hidden = false;
  }

  const desktopUpdates = window.mmaAssist && window.mmaAssist.updates;

  if (desktopUpdates) {
    // Same-origin route, so no safeExternalUrl dance and no new window -
    // the install flow lives on the Settings page.
    linkEl.href = "/settings/";
    linkEl.removeAttribute("target");
    linkEl.textContent = "Update";

    desktopUpdates.onState(renderBanner);
    desktopUpdates.state().then(renderBanner);
    desktopUpdates.check();

    function renderBanner(state) {
      switch (state.status) {
        case "available":
          return show({
            version: state.version,
            title: `Version ${state.version} is available`,
            detail: "Download and install it from Settings.",
          });
        case "downloaded":
          return show({
            version: state.version,
            title: `Version ${state.version} is ready to install`,
            detail: "Finish the update from Settings.",
          });
        case "unsupported":
          // Portable build or a dev run - the main process can't update
          // itself, so fall back to the manifest check.
          return checkViaServer();
        default:
          // idle, checking, downloading, installing, not-available, error.
          // None of these is a newer release the user can act on from here,
          // and the banner must retract rather than keep asserting whatever
          // it last said. "Couldn't check" stays silent on purpose.
          return hide();
      }
    }
    return;
  }

  checkViaServer();

  function checkViaServer() {
    fetch("/api/updates/check")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status))))
      .then((data) => {
        // "current", "dev", "disabled", "unknown": nothing to announce.
        if (data.status !== "available" && data.status !== "required") return hide();
        // Manifest-supplied, therefore untrusted - see safeExternalUrl.
        linkEl.href =
          safeExternalUrl(data.downloadPageUrl) || safeExternalUrl(data.downloadUrl) || "#";
        show({
          version: data.latestVersion,
          title: `Version ${data.latestVersion} is available`,
          detail: `You're on ${data.currentVersion}.`,
          // A release flagged as required is not something to hide behind a
          // dismissal - the running version is known-bad.
          dismissible: data.status !== "required",
        });
      })
      .catch(() => {
        /* offline is normal for a local-first app - stay quiet */
        hide();
      });
  }
});
