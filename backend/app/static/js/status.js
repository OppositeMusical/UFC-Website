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
document.addEventListener("DOMContentLoaded", () => {
  const banner = document.getElementById("update-banner");
  if (!banner) return;

  const dismissKey = (version) => `ufcpredictor:update-dismissed:${version}`;

  fetch("/api/updates/check")
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.status))))
    .then((data) => {
      if (data.status !== "available") return;
      // Dismissal is per-version, so the banner comes back for the next
      // release instead of being silenced forever by one click.
      if (localStorage.getItem(dismissKey(data.latestVersion))) return;

      document.getElementById("update-banner-title").textContent =
        `Version ${data.latestVersion} is available`;
      document.getElementById("update-banner-detail").textContent =
        `You're on ${data.currentVersion}.`;
      document.getElementById("update-banner-link").href =
        data.downloadPageUrl || data.downloadUrl || "#";
      banner.hidden = false;

      document.getElementById("update-banner-dismiss").addEventListener("click", () => {
        localStorage.setItem(dismissKey(data.latestVersion), "1");
        banner.hidden = true;
      });
    })
    .catch(() => {
      /* offline is normal for a local-first app - stay quiet */
    });
});
