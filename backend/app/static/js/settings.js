document.addEventListener("DOMContentLoaded", () => {
  const providerSelect = document.getElementById("provider-select");
  const apiKeyRow = document.getElementById("api-key-row");
  const ollamaRow = document.getElementById("ollama-row");
  const ollamaModelSelect = document.getElementById("ollama-model-select");

  function refreshVisibility() {
    const provider = providerSelect.value;
    apiKeyRow.style.display = provider === "ollama" ? "none" : "block";
    ollamaRow.style.display = provider === "ollama" ? "block" : "none";
    if (provider === "ollama") loadOllamaModels();
  }
  providerSelect.addEventListener("change", refreshVisibility);
  refreshVisibility();

  async function loadOllamaModels() {
    ollamaModelSelect.innerHTML = "<option>Loading...</option>";
    try {
      const data = await apiFetch("/settings/ollama/models");
      ollamaModelSelect.innerHTML = "";
      if (data.models.length === 0) {
        ollamaModelSelect.innerHTML = "<option value=''>No local models found - is Ollama running?</option>";
        return;
      }
      data.models.forEach((m) => {
        const opt = document.createElement("option");
        opt.value = m;
        opt.textContent = m;
        ollamaModelSelect.appendChild(opt);
      });
    } catch (e) {
      ollamaModelSelect.innerHTML = `<option value="">Could not reach Ollama</option>`;
    }
  }

  const saveForm = document.getElementById("provider-form");
  const saveStatus = document.getElementById("save-status");
  saveForm.addEventListener("submit", async (evt) => {
    evt.preventDefault();
    const provider = providerSelect.value;
    const payload = { provider };
    if (provider === "ollama") {
      payload.model = ollamaModelSelect.value;
    } else {
      const key = document.getElementById("api-key-input").value.trim();
      if (key) payload.api_key = key;
    }
    saveStatus.textContent = "Saving...";
    try {
      await apiFetch("/settings/provider", { method: "POST", body: JSON.stringify(payload) });
      saveStatus.textContent = "Saved.";
    } catch (e) {
      saveStatus.textContent = `Error: ${e.message}`;
    }
  });

  const testBtn = document.getElementById("test-connection-btn");
  const testStatus = document.getElementById("test-status");
  testBtn.addEventListener("click", async () => {
    testStatus.textContent = "Testing...";
    try {
      const data = await apiFetch("/settings/test-connection", {
        method: "POST",
        body: JSON.stringify({ provider: providerSelect.value }),
      });
      testStatus.textContent = data.ok ? `OK: ${data.reply}` : `Failed: ${data.error}`;
    } catch (e) {
      testStatus.textContent = `Failed: ${e.message}`;
    }
  });

  const syncBtn = document.getElementById("sync-fighters-btn");
  const syncStatus = document.getElementById("sync-status");
  const syncProgress = document.getElementById("sync-progress");
  const syncFill = document.getElementById("sync-progress-fill");
  const syncPct = document.getElementById("sync-progress-pct");
  let pollTimer = null;

  syncBtn.addEventListener("click", async () => {
    try {
      await apiFetch("/settings/sync-fighters", { method: "POST" });
      syncBtn.disabled = true;
      syncBtn.innerHTML = '<span class="btn__spinner"></span> Syncing';
      syncProgress.hidden = false;
      pollTimer = setInterval(pollSyncStatus, 2000);
    } catch (e) {
      syncStatus.textContent = `Error: ${e.message}`;
    }
  });

  function endSync(message) {
    clearInterval(pollTimer);
    syncBtn.disabled = false;
    syncBtn.textContent = "Sync Now";
    syncStatus.textContent = message;
  }

  async function pollSyncStatus() {
    const data = await apiFetch("/settings/sync-fighters/status");
    if (data.running) {
      // Roster discovery runs before any fighter is counted, so total is 0
      // for the first stretch - don't render a misleading 0% bar then.
      const pct = data.total ? Math.round((data.done / data.total) * 100) : 0;
      syncFill.style.width = `${pct}%`;
      syncPct.textContent = data.total ? `${pct}%` : "...";
      syncStatus.textContent = data.total
        ? `Syncing ${data.done.toLocaleString()} / ${data.total.toLocaleString()} fighters`
        : "Discovering the roster from ufc.com...";
      return;
    }

    syncFill.style.width = "100%";
    syncPct.textContent = "100%";
    endSync(
      data.last_error
        ? `Error: ${data.last_error}`
        : "Done. Refresh the page to see the updated stats."
    );
  }
});
