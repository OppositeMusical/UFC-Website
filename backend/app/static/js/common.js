/**
 * Returns `value` only if it is an http(s) URL, otherwise null.
 *
 * Use this for any URL that came from off-machine before putting it in an
 * href. The update manifest is fetched from a remote host, so its
 * downloadUrl/downloadPageUrl fields are untrusted: assigning one directly
 * to .href would let a "javascript:..." value execute in the app's own
 * origin as soon as the user clicked the button, with access to everything
 * same-origin - including the settings endpoints.
 */
function safeExternalUrl(value) {
  if (!value) return null;
  try {
    const parsed = new URL(value, window.location.href);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.href : null;
  } catch {
    return null;
  }
}

// Sidebar collapse. The initial class is applied by an inline script in
// base.html <head> to avoid a flash; this only handles toggling + persisting.
document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("sidebar-toggle");
  if (!toggle) return;

  function sync() {
    const collapsed = document.documentElement.classList.contains("sidebar-collapsed");
    const action = collapsed ? "Expand sidebar" : "Collapse sidebar";
    toggle.title = action;
    toggle.setAttribute("aria-label", action);
    toggle.setAttribute("aria-expanded", String(!collapsed));
  }

  toggle.addEventListener("click", () => {
    const collapsed = document.documentElement.classList.toggle("sidebar-collapsed");
    localStorage.setItem("ufcpredictor:sidebar", collapsed ? "collapsed" : "expanded");
    sync();
  });

  sync();
});

// Counts any [data-count-to] element up from zero on load. Big numbers
// (6,746 fighters) land better as something that arrives than as static
// text, and it doubles as a signal the page has live data behind it.
document.addEventListener("DOMContentLoaded", () => {
  const targets = document.querySelectorAll("[data-count-to]");
  if (!targets.length) return;

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const DURATION_MS = 900;

  targets.forEach((el) => {
    const target = Number(el.dataset.countTo || 0);
    if (reduced || target === 0) {
      el.textContent = target.toLocaleString();
      return;
    }
    const start = performance.now();
    function tick(now) {
      const t = Math.min((now - start) / DURATION_MS, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      el.textContent = Math.round(target * eased).toLocaleString();
      if (t < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  });
});

async function apiFetch(url, options = {}) {
  const resp = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(data.error || `Request failed (${resp.status})`);
  }
  return data;
}

function attachAutocomplete(inputEl, resultsEl, hiddenIdEl) {
  let debounceTimer = null;
  let currentResults = [];
  let highlightIndex = -1;

  inputEl.addEventListener("input", () => {
    hiddenIdEl.value = "";
    const query = inputEl.value.trim();
    clearTimeout(debounceTimer);
    if (query.length < 2) {
      close();
      return;
    }
    debounceTimer = setTimeout(async () => {
      try {
        currentResults = await apiFetch(`/api/fighters/autocomplete?q=${encodeURIComponent(query)}`);
      } catch (e) {
        currentResults = [];
      }
      renderResults();
    }, 200);
  });

  // Arrow keys / Enter / Escape. Picking from the dropdown is the only way
  // to set the hidden id the form submits, so it has to be reachable
  // without taking a hand off the keyboard.
  inputEl.addEventListener("keydown", (evt) => {
    if (!resultsEl.classList.contains("open") || currentResults.length === 0) return;
    if (evt.key === "ArrowDown") {
      evt.preventDefault();
      moveHighlight(1);
    } else if (evt.key === "ArrowUp") {
      evt.preventDefault();
      moveHighlight(-1);
    } else if (evt.key === "Enter" && highlightIndex >= 0) {
      evt.preventDefault();
      select(currentResults[highlightIndex]);
    } else if (evt.key === "Escape") {
      close();
    }
  });

  function moveHighlight(delta) {
    highlightIndex = (highlightIndex + delta + currentResults.length) % currentResults.length;
    const nodes = resultsEl.querySelectorAll(".autocomplete__result");
    nodes.forEach((node, i) => node.classList.toggle("highlighted", i === highlightIndex));
    nodes[highlightIndex]?.scrollIntoView({ block: "nearest" });
  }

  function select(fighter) {
    inputEl.value = fighter.name;
    hiddenIdEl.value = fighter.id;
    close();

    // A CUSTOM event, never a native "input" one. The handler above clears
    // hiddenIdEl on every input - correct, since typing after choosing must
    // invalidate the choice - so dispatching "input" here wiped the id
    // microseconds after setting it and every submit failed with "pick both
    // fighters from the dropdown" even though one had just been picked.
    inputEl.dispatchEvent(new CustomEvent("autocomplete:select", { bubbles: true, detail: fighter }));
  }

  function close() {
    resultsEl.classList.remove("open");
    highlightIndex = -1;
  }

  function renderResults() {
    resultsEl.innerHTML = "";
    highlightIndex = -1;

    if (currentResults.length === 0) {
      const empty = document.createElement("div");
      empty.className = "autocomplete__empty";
      empty.textContent = "No fighters match that name.";
      resultsEl.appendChild(empty);
      resultsEl.classList.add("open");
      return;
    }

    currentResults.forEach((fighter) => {
      const div = document.createElement("div");
      div.className = "autocomplete__result";
      div.textContent = fighter.name;
      if (fighter.weight_class) {
        const small = document.createElement("small");
        small.textContent = fighter.weight_class;
        div.appendChild(small);
      }
      div.addEventListener("click", () => select(fighter));
      resultsEl.appendChild(div);
    });
    resultsEl.classList.add("open");
  }

  document.addEventListener("click", (evt) => {
    if (!inputEl.contains(evt.target) && !resultsEl.contains(evt.target)) {
      close();
    }
  });
}
