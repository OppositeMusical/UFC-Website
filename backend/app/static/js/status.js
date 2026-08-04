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
