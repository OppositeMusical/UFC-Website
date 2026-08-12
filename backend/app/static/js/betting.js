document.addEventListener("DOMContentLoaded", () => {
  const formEl = document.getElementById("bet-form");
  if (!formEl) return;
  const platform = formEl.dataset.platform;
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const fighterAId = document.getElementById("fighter-a-id");
  const fighterBId = document.getElementById("fighter-b-id");
  // The matchup lives in its own card above the forms and is shared by all
  // of them, so listeners bind to that card rather than to any one form.
  const matchupCard = document.getElementById("matchup-card");
  const vsRow = matchupCard.querySelector(".vs-row");

  attachAutocomplete(document.getElementById("fighter-a-input"), document.getElementById("fighter-a-results"), fighterAId);
  attachAutocomplete(document.getElementById("fighter-b-input"), document.getElementById("fighter-b-results"), fighterBId);

  // Light up the VS marker once both corners are actually selected. The
  // hidden id fields are only set by picking from the dropdown, so this
  // also signals "typed text alone isn't a selection".
  function refreshReadyState() {
    vsRow.classList.toggle("is-ready", Boolean(fighterAId.value && fighterBId.value));
  }
  matchupCard.addEventListener("input", refreshReadyState);
  // Picking from the dropdown emits a custom event rather than a native
  // "input" one - see the note in common.js::select().
  matchupCard.addEventListener("autocomplete:select", refreshReadyState);

  function bothFightersPicked() {
    return Boolean(fighterAId.value && fighterBId.value);
  }

  const resultEl = document.getElementById("prediction-result");
  const loadingEl = document.getElementById("prediction-loading");
  const errorEl = document.getElementById("error-banner");
  const submitBtn = document.getElementById("submit-btn");

  formEl.addEventListener("submit", async (evt) => {
    evt.preventDefault();
    errorEl.classList.remove("visible");
    resultEl.classList.remove("visible");

    const statCategory = document.getElementById("stat-category").value;
    const lineValue = document.getElementById("line-value").value;

    if (!bothFightersPicked()) {
      showError("Pick both fighters from the autocomplete dropdown.");
      return;
    }
    if (!lineValue) {
      showError("Enter a line value.");
      return;
    }

    setLoading(true);
    try {
      const data = await apiFetch(`/betting/${platform}/predict`, {
        method: "POST",
        body: JSON.stringify({
          fighter_a_id: Number(fighterAId.value),
          fighter_b_id: Number(fighterBId.value),
          stat_category: statCategory,
          line_value: Number(lineValue),
        }),
      });
      renderPrediction(data);
    } catch (e) {
      showError(e.message);
    } finally {
      setLoading(false);
    }
  });

  function setLoading(loading) {
    submitBtn.disabled = loading;
    loadingEl.classList.toggle("visible", loading);
    submitBtn.innerHTML = loading
      ? '<span class="btn__spinner"></span> Analyzing...'
      : "Get Prediction";
  }

  function showError(message) {
    errorEl.textContent = message;
    // Restart the shake even if the banner was already visible.
    errorEl.classList.remove("visible");
    void errorEl.offsetWidth;
    errorEl.classList.add("visible");
  }

  function renderPrediction(data) {
    const { direction, confidence_pct: confidence, reasoning } = data.prediction;

    const directionEl = document.getElementById("prediction-direction");
    directionEl.textContent = direction.toUpperCase();
    directionEl.className = `prediction-call__direction ${direction}`;

    document.getElementById("prediction-reasoning").textContent = reasoning;
    document.getElementById("continue-in-chat").href = `/chat/${data.conversation_id}`;
    resultEl.classList.add("visible");

    animateConfidence(confidence, direction);
  }

  function animateConfidence(pct, direction) {
    const arc = document.getElementById("confidence-arc");
    arc.classList.toggle("over", direction === "over");
    animateRing(arc, document.getElementById("prediction-confidence"), pct);
  }

  // Shared by the stat-prop confidence ring and the Kalshi probability ring.
  function animateRing(arc, valueEl, pct) {
    const circumference = 2 * Math.PI * 33;
    arc.style.strokeDasharray = `${circumference}`;

    if (prefersReducedMotion) {
      arc.style.strokeDashoffset = `${circumference * (1 - pct / 100)}`;
      valueEl.textContent = `${pct}%`;
      return;
    }

    // Start empty, then let the CSS transition draw the arc on the next
    // frame - setting both values in one frame would skip the animation.
    arc.style.strokeDashoffset = `${circumference}`;
    valueEl.textContent = "0%";
    requestAnimationFrame(() => {
      arc.style.strokeDashoffset = `${circumference * (1 - pct / 100)}`;
    });

    const DURATION_MS = 1100;
    const start = performance.now();
    function tick(now) {
      const t = Math.min((now - start) / DURATION_MS, 1);
      // easeOutCubic, matched to the ring's --ease-out so the number and
      // the arc stay visually in step.
      const eased = 1 - Math.pow(1 - t, 3);
      valueEl.textContent = `${Math.round(pct * eased)}%`;
      if (t < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  // ---- Priced fight markets (DraftKings) --------------------------------
  //
  // Every card is wired the same way and differs only in which fields the
  // server rendered into it, so this reads the fields present rather than
  // knowing anything about the three market types.
  document.querySelectorAll(".market-card").forEach((card) => {
    const marketType = card.dataset.marketType;
    const form = card.querySelector(".market-form");
    const pick = (role) => card.querySelector(`[data-role="${role}"]`);
    const field = (name) => card.querySelector(`[data-field="${name}"]`);

    const btn = pick("submit");
    const errorBox = pick("error");
    const loading = pick("loading");
    const result = pick("result");

    form.addEventListener("submit", async (evt) => {
      evt.preventDefault();
      errorBox.classList.remove("visible");
      result.classList.remove("visible");

      if (!bothFightersPicked()) {
        showCardError("Pick both fighters at the top of the page first.");
        return;
      }
      const moneyline = field("moneyline").value.trim();
      if (!moneyline) {
        showCardError("Enter the moneyline the sportsbook is offering.");
        return;
      }

      const body = {
        fighter_a_id: Number(fighterAId.value),
        fighter_b_id: Number(fighterBId.value),
        market_type: marketType,
        moneyline,
      };
      if (field("method")) body.method = field("method").value;
      if (field("round")) body.round_number = Number(field("round").value);

      setCardLoading(true);
      try {
        renderMarketOdds(await apiFetch(`/betting/${platform}/market`, {
          method: "POST",
          body: JSON.stringify(body),
        }));
      } catch (e) {
        showCardError(e.message);
      } finally {
        setCardLoading(false);
      }
    });

    function setCardLoading(on) {
      btn.disabled = on;
      loading.classList.toggle("visible", on);
      btn.innerHTML = on ? '<span class="btn__spinner"></span> Pricing...' : "Price This Market";
    }

    function showCardError(message) {
      errorBox.textContent = message;
      errorBox.classList.remove("visible");
      void errorBox.offsetWidth;
      errorBox.classList.add("visible");
    }

    function renderMarketOdds(data) {
      pick("question").textContent = data.question;
      pick("model-pct").textContent = `${data.modelProbabilityPct}%`;
      pick("implied-pct").textContent = `${data.impliedProbabilityPct}%`;

      // Always signed: the sign is the entire message, and "+4.0" versus
      // "4.0" is the difference between an edge and an unreadable number.
      const edge = pick("edge");
      edge.textContent = `${data.edgePct > 0 ? "+" : ""}${data.edgePct.toFixed(1)}`;
      edge.className = `odds-figure__value ${data.verdict}`;

      const verdict = pick("verdict");
      verdict.textContent = data.verdictLabel;
      verdict.className = `odds-verdict ${data.verdict}`;

      const ev = data.expectedValuePer100;
      pick("ev").textContent =
        data.verdict === "implausible"
          // Suppress the expected-value figure entirely here. A gap this
          // wide almost always means the estimate is wrong, and rendering
          // "+180 expected" beside it would be the single most misleading
          // thing on the page.
          ? `The model and the ${data.moneyline_display} price disagree by ${Math.abs(data.edgePct).toFixed(1)} points. ` +
            "A liquid market is rarely wrong by that much, so treat this as the model mis-estimating " +
            "rather than as an opportunity — a stronger AI provider usually narrows it."
          : `At ${data.moneyline_display}, a 100 stake returns ${data.profitPer100.toFixed(2)} profit if it lands. ` +
            `Against the model's ${data.modelProbabilityPct}% that is ${ev >= 0 ? "+" : ""}${ev.toFixed(2)} expected — ` +
            "only as good as the estimate behind it.";

      pick("reasoning").textContent = data.reasoning;
      pick("continue").href = `/chat/${data.conversation_id}`;
      result.classList.add("visible");
    }
  });

  // ---- Kalshi free-text market question (only rendered on that page) ----
  const marketForm = document.getElementById("market-form");
  if (!marketForm) return;

  const questionEl = document.getElementById("market-question");
  const counterEl = document.getElementById("market-counter");
  const marketBtn = document.getElementById("market-submit-btn");
  const marketError = document.getElementById("market-error");
  const marketLoading = document.getElementById("market-loading");
  const marketResult = document.getElementById("market-result");
  const MAX_CHARS = 500;

  questionEl.addEventListener("input", () => {
    const used = questionEl.value.length;
    counterEl.textContent = `${used} / ${MAX_CHARS}`;
    counterEl.classList.toggle("near-limit", used > MAX_CHARS * 0.9);
  });

  questionEl.addEventListener("keydown", (evt) => {
    if ((evt.ctrlKey || evt.metaKey) && evt.key === "Enter") {
      evt.preventDefault();
      marketForm.requestSubmit();
    }
  });

  marketForm.addEventListener("submit", async (evt) => {
    evt.preventDefault();
    marketError.classList.remove("visible");
    marketResult.classList.remove("visible");

    const question = questionEl.value.trim();
    if (!question) {
      showMarketError("Describe the market you want a probability for.");
      return;
    }

    setMarketLoading(true);
    try {
      const data = await apiFetch(`/betting/${platform}/market-probability`, {
        method: "POST",
        body: JSON.stringify({ question }),
      });
      renderMarket(data);
    } catch (e) {
      showMarketError(e.message);
    } finally {
      setMarketLoading(false);
    }
  });

  function setMarketLoading(loading) {
    marketBtn.disabled = loading;
    marketLoading.classList.toggle("visible", loading);
    marketBtn.innerHTML = loading
      ? '<span class="btn__spinner"></span> Estimating...'
      : "Estimate Probability";
  }

  function showMarketError(message) {
    marketError.textContent = message;
    marketError.classList.remove("visible");
    void marketError.offsetWidth;
    marketError.classList.add("visible");
  }

  function renderMarket(data) {
    const pct = data.probability_pct;

    const leanEl = document.getElementById("market-lean");
    // 45-55 is inside the noise of an LLM estimate; calling that a lean
    // either way would read as more signal than there is.
    let lean = "Toss-up";
    let leanClass = "toss-up";
    if (pct >= 55) {
      lean = "Leans Yes";
      leanClass = "leans-yes";
    } else if (pct <= 45) {
      lean = "Leans No";
      leanClass = "leans-no";
    }
    leanEl.textContent = lean;
    leanEl.className = `market-verdict__lean ${leanClass}`;

    const matchedEl = document.getElementById("market-matched");
    const matched = data.matched_fighters || [];
    matchedEl.textContent = matched.length
      ? `Grounded in stats for ${matched.join(", ")}`
      : "No fighter matched - not stat-grounded";
    matchedEl.classList.toggle("unmatched", matched.length === 0);

    document.getElementById("market-reasoning").textContent = data.reasoning;
    document.getElementById("market-continue").href = `/chat/${data.conversation_id}`;
    marketResult.classList.add("visible");

    animateRing(document.getElementById("market-arc"), document.getElementById("market-probability"), pct);
  }
});
