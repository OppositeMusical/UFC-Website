document.addEventListener("DOMContentLoaded", () => {
  const providerSelect = document.getElementById("provider-select");
  const apiKeyRow = document.getElementById("api-key-row");
  const ollamaRow = document.getElementById("ollama-row");
  const ollamaModelSelect = document.getElementById("ollama-model-select");
  const claudeRow = document.getElementById("claude-row");
  const claudeModelSelect = document.getElementById("claude-model-select");

  function refreshVisibility() {
    const provider = providerSelect.value;
    apiKeyRow.style.display = provider === "ollama" ? "none" : "block";
    ollamaRow.style.display = provider === "ollama" ? "block" : "none";
    claudeRow.style.display = provider === "claude" ? "block" : "none";
    if (provider === "ollama") loadOllamaModels();
    if (provider === "claude") loadClaudeModels();
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

  async function loadClaudeModels() {
    claudeModelSelect.innerHTML = "<option>Loading...</option>";
    try {
      // Backed by Anthropic's authenticated /v1/models endpoint, so the list
      // is exactly what the saved key can use - and it 400s with a readable
      // message when no key is saved yet or the key is rejected.
      const data = await apiFetch("/settings/claude/models");
      claudeModelSelect.innerHTML = "";
      data.models.forEach((m) => {
        const opt = document.createElement("option");
        opt.value = m;
        opt.textContent = m;
        if (m === data.active) opt.selected = true;
        claudeModelSelect.appendChild(opt);
      });
    } catch (e) {
      claudeModelSelect.innerHTML = "";
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = e.message;
      claudeModelSelect.appendChild(opt);
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
      if (provider === "claude" && claudeModelSelect.value) {
        payload.model = claudeModelSelect.value;
      }
    }
    saveStatus.textContent = "Saving...";
    try {
      await apiFetch("/settings/provider", { method: "POST", body: JSON.stringify(payload) });
      saveStatus.textContent = "Saved.";
      // A key may have just been saved for the first time (or replaced), so
      // the model list can go from an error message to a real lineup.
      if (provider === "claude") loadClaudeModels();
    } catch (e) {
      saveStatus.textContent = `Error: ${e.message}`;
    }
  });

  const testBtn = document.getElementById("test-connection-btn");
  const testStatus = document.getElementById("test-status");
  testBtn.addEventListener("click", async () => {
    testStatus.textContent = "Testing...";
    try {
      // For Claude, test the model showing in the dropdown - it may not be
      // saved yet, and testing a different model than the one on screen
      // would be misleading.
      const body = { provider: providerSelect.value };
      if (providerSelect.value === "claude" && claudeModelSelect.value) {
        body.model = claudeModelSelect.value;
      }
      const data = await apiFetch("/settings/test-connection", {
        method: "POST",
        body: JSON.stringify(body),
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

  // ---- Updates -------------------------------------------------------
  //
  // Two paths behind one card:
  //
  //   Desktop (NSIS build)  - window.mmaAssist.updates exists. The main
  //     process downloads and installs; this only renders state it is told
  //     about. Nothing here chooses a URL - see desktop/preload.js.
  //   Browser / portable    - falls back to the Flask endpoint and a link
  //     to the download page, which is exactly the pre-0.5.0 behaviour.
  //
  const checkBtn = document.getElementById("check-updates-btn");
  const updateStatus = document.getElementById("update-status");
  const notesEl = document.getElementById("release-notes");
  const downloadBtn = document.getElementById("update-download-btn");
  const fetchBtn = document.getElementById("update-fetch-btn");
  const installBtn = document.getElementById("update-install-btn");
  const hintEl = document.getElementById("update-hint");
  const progressEl = document.getElementById("update-progress");
  const progressFill = document.getElementById("update-progress-fill");
  const progressPct = document.getElementById("update-progress-pct");

  const desktopUpdates = window.mmaAssist && window.mmaAssist.updates;

  function resetUpdateUi() {
    notesEl.hidden = true;
    notesEl.innerHTML = "";
    downloadBtn.hidden = true;
    fetchBtn.hidden = true;
    installBtn.hidden = true;
    hintEl.hidden = true;
    hintEl.textContent = "";
    progressEl.hidden = true;
  }

  function renderNotes(notes) {
    if (!notes || !notes.length) return;
    notes.forEach((note) => {
      const li = document.createElement("li");
      li.textContent = note;
      notesEl.appendChild(li);
    });
    notesEl.hidden = false;
  }

  function formatMb(bytes) {
    return bytes ? `${(bytes / (1024 * 1024)).toFixed(0)} MB` : null;
  }

  // ---- Desktop path --------------------------------------------------

  function renderDesktopState(state) {
    resetUpdateUi();
    checkBtn.disabled = state.status === "checking" || state.status === "downloading";

    switch (state.status) {
      case "checking":
        updateStatus.textContent = "Checking for updates...";
        break;

      case "available": {
        const size = formatMb(state.sizeBytes);
        updateStatus.textContent =
          `Version ${state.version} is available.` + (size ? ` Download is ${size}.` : "");
        renderNotes(state.releaseNotes);
        fetchBtn.hidden = false;
        break;
      }

      case "downloading":
        updateStatus.textContent = `Downloading version ${state.version || ""}...`.trim();
        progressEl.hidden = false;
        progressFill.style.width = `${state.percent || 0}%`;
        progressPct.textContent = `${state.percent || 0}%`;
        break;

      case "downloaded":
        updateStatus.textContent = `Version ${state.version} is ready to install.`;
        progressEl.hidden = false;
        progressFill.style.width = "100%";
        progressPct.textContent = "100%";
        installBtn.hidden = false;
        hintEl.textContent =
          "MMA Assist will close, install the update, and reopen. Your fighter database, " +
          "chats and saved predictions are kept.";
        hintEl.hidden = false;
        break;

      case "installing":
        updateStatus.textContent = "Installing... the app will restart on its own.";
        break;

      case "not-available":
        updateStatus.textContent = "You're on the latest version.";
        break;

      case "unsupported":
        // Portable build or a dev run: fall back to the manifest check so
        // the card still tells the user a release exists.
        checkViaServer(false);
        return;

      case "error":
        updateStatus.textContent = state.message || "The update failed.";
        if (state.hint) {
          hintEl.textContent = state.hint;
          hintEl.hidden = false;
        }
        break;

      default:
        updateStatus.textContent = "Ready to check for updates.";
    }
  }

  // ---- Browser / portable path ---------------------------------------

  async function checkViaServer(force) {
    resetUpdateUi();
    updateStatus.textContent = "Checking...";
    checkBtn.disabled = true;
    try {
      renderServerStatus(await apiFetch(`/api/updates/check${force ? "?force=1" : ""}`));
    } catch (e) {
      updateStatus.textContent = `Could not check for updates: ${e.message}`;
    } finally {
      checkBtn.disabled = false;
    }
  }

  function renderServerStatus(data) {
    resetUpdateUi();
    if (data.status === "available" || data.status === "required") {
      updateStatus.textContent =
        data.status === "required"
          ? `Version ${data.latestVersion} is required. You're on ${data.currentVersion}.`
          : `Version ${data.latestVersion} is available. You're on ${data.currentVersion}.`;
      // The download page carries the SmartScreen warning and the
      // checksum, so send people there rather than starting a 240MB
      // binary download straight from a settings screen.
      // Manifest-supplied, therefore untrusted - see safeExternalUrl.
      downloadBtn.href =
        safeExternalUrl(data.downloadPageUrl) || safeExternalUrl(data.downloadUrl) || "#";
      downloadBtn.hidden = false;
      if (data.detail) {
        hintEl.textContent = data.detail;
        hintEl.hidden = false;
      }
      renderNotes(data.releaseNotes);
      return;
    }

    const messages = {
      current: `You're on the latest version (${data.currentVersion}).`,
      dev: data.detail,
      disabled: data.detail,
      unknown: data.detail || "Could not reach the update server.",
    };
    updateStatus.textContent = messages[data.status] || "Unknown update status.";
  }

  // ---- Wiring --------------------------------------------------------

  if (checkBtn && desktopUpdates) {
    desktopUpdates.onState(renderDesktopState);
    checkBtn.addEventListener("click", () => desktopUpdates.check());
    fetchBtn.addEventListener("click", () => desktopUpdates.download());
    installBtn.addEventListener("click", () => {
      installBtn.disabled = true;
      updateStatus.textContent = "Closing and installing...";
      desktopUpdates.install();
    });
    // Replay whatever the main process already knows - the check may have
    // run before this page loaded, or be in progress right now.
    desktopUpdates.state().then(renderDesktopState);
    desktopUpdates.check();
  } else if (checkBtn) {
    checkBtn.addEventListener("click", () => checkViaServer(true));
    checkViaServer(false);
  }
});
