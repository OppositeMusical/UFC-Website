document.addEventListener("DOMContentLoaded", () => {
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const page = document.querySelector(".chat-page");
  const mainEl = document.getElementById("chat-main");
  const form = document.getElementById("chat-input-form");
  const messagesEl = document.getElementById("chat-messages");
  const threadEl = messagesEl.querySelector(".chat-thread");
  const inputEl = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send-btn");
  const scrollBtn = document.getElementById("scroll-bottom-btn");
  const railToggle = document.getElementById("chat-sidebar-toggle");
  const conversationsEl = page.querySelector(".chat-conversations");

  // Set once a conversation exists - either rendered by the server or
  // created lazily on the first send from the hero screen.
  let conversationId = form.dataset.conversationId || null;

  // ---- Conversation rail -------------------------------------------
  const RAIL_KEY = "ufcpredictor:chat-rail";
  if (localStorage.getItem(RAIL_KEY) === "hidden") {
    page.classList.add("rail-hidden");
  }
  function syncRailButton() {
    const hidden = page.classList.contains("rail-hidden");
    const action = hidden ? "Show conversations" : "Hide conversations";
    railToggle.title = action;
    railToggle.setAttribute("aria-label", action);
  }
  railToggle.addEventListener("click", () => {
    const hidden = page.classList.toggle("rail-hidden");
    localStorage.setItem(RAIL_KEY, hidden ? "hidden" : "shown");
    syncRailButton();
  });
  syncRailButton();

  // ---- New chat -----------------------------------------------------
  async function startNewChat() {
    const data = await apiFetch("/chat/new", { method: "POST" });
    window.location.href = `/chat/${data.conversation_id}`;
  }
  document.getElementById("new-chat-btn")?.addEventListener("click", startNewChat);
  document.getElementById("compose-new-btn")?.addEventListener("click", () => {
    // Already on a blank hero screen - just clear the box rather than
    // spending a round trip to land somewhere identical.
    if (!conversationId) {
      inputEl.value = "";
      autoResize(inputEl);
      updateSendState();
      inputEl.focus();
      return;
    }
    startNewChat();
  });

  document.querySelectorAll(".chat-suggestion").forEach((btn) => {
    btn.addEventListener("click", () => {
      inputEl.value = btn.dataset.text || "";
      autoResize(inputEl);
      updateSendState();
      form.requestSubmit();
    });
  });

  // ---- Composer -----------------------------------------------------
  function autoResize(el) {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 180) + "px";
  }

  function updateSendState() {
    sendBtn.disabled = inputEl.value.trim().length === 0 || sendBtn.classList.contains("is-sending");
  }

  inputEl.addEventListener("input", () => {
    autoResize(inputEl);
    updateSendState();
  });

  inputEl.addEventListener("keydown", (evt) => {
    if (evt.key === "Enter" && !evt.shiftKey) {
      evt.preventDefault();
      if (!sendBtn.disabled) form.requestSubmit();
    }
  });

  // ---- Scrolling ----------------------------------------------------
  // Stick to the bottom only while already near it: if the user scrolled up
  // to re-read something, a streaming reply must not drag them back down.
  const STICK_THRESHOLD_PX = 120;

  function isNearBottom() {
    return messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < STICK_THRESHOLD_PX;
  }

  function scrollToBottom(force = false) {
    if (force || isNearBottom()) {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }
  }

  messagesEl.addEventListener("scroll", () => {
    const show = !isNearBottom() && !mainEl.classList.contains("chat-main--hero");
    scrollBtn.classList.toggle("visible", show);
  });

  scrollBtn.addEventListener("click", () => {
    messagesEl.scrollTop = messagesEl.scrollHeight;
    scrollBtn.classList.remove("visible");
  });

  // ---- Rendering ----------------------------------------------------
  function exitHeroMode() {
    mainEl.classList.remove("chat-main--hero");
  }

  function createAvatar() {
    const div = document.createElement("div");
    div.className = "msg-avatar";
    div.textContent = "🥊";
    return div;
  }

  function attachActions(bubbleEl) {
    const actions = document.createElement("div");
    actions.className = "msg-actions";

    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.className = "msg-action-btn";
    copyBtn.textContent = "Copy";
    copyBtn.addEventListener("click", async () => {
      // The actions row lives inside the bubble, so copy the stashed text
      // rather than textContent - otherwise "Copy" ends up on the clipboard.
      await navigator.clipboard.writeText(bubbleEl.dataset.raw || "");
      copyBtn.textContent = "Copied";
      copyBtn.classList.add("copied");
      setTimeout(() => {
        copyBtn.textContent = "Copy";
        copyBtn.classList.remove("copied");
      }, 1200);
    });

    actions.appendChild(copyBtn);
    bubbleEl.appendChild(actions);
  }

  function appendMessage(role, content) {
    exitHeroMode();
    const row = document.createElement("div");
    row.className = `msg-row msg-row--${role} msg-row--enter`;
    if (role === "assistant") row.appendChild(createAvatar());

    const bubble = document.createElement("div");
    bubble.className = `msg-bubble msg-bubble--${role}`;
    bubble.textContent = content;
    bubble.dataset.raw = content;
    row.appendChild(bubble);

    threadEl.appendChild(row);
    scrollToBottom(true);
    return bubble;
  }

  function appendTypingIndicator() {
    exitHeroMode();
    const row = document.createElement("div");
    row.className = "msg-row msg-row--assistant msg-row--enter";
    row.id = "typing-indicator";
    row.appendChild(createAvatar());
    const bubble = document.createElement("div");
    bubble.className = "msg-bubble msg-bubble--assistant";
    bubble.innerHTML = '<span class="typing-dots"><span></span><span></span><span></span></span>';
    row.appendChild(bubble);
    threadEl.appendChild(row);
    scrollToBottom(true);
  }

  function removeTypingIndicator() {
    document.getElementById("typing-indicator")?.remove();
  }

  // Reveals the reply progressively so it reads as a live answer rather than
  // a block appearing at once. Driven by rAF against a token budget, so the
  // pace holds regardless of reply length.
  function revealText(bubbleEl, text) {
    bubbleEl.dataset.raw = text;
    if (prefersReducedMotion) {
      bubbleEl.textContent = text;
      scrollToBottom();
      return Promise.resolve();
    }

    const tokens = text.split(/(\s+)/);
    const perFrame = Math.max(1, Math.ceil(tokens.length / 220));
    bubbleEl.classList.add("is-streaming");

    return new Promise((resolve) => {
      let i = 0;
      function step() {
        i = Math.min(i + perFrame, tokens.length);
        bubbleEl.textContent = tokens.slice(0, i).join("");
        scrollToBottom();
        if (i < tokens.length) {
          requestAnimationFrame(step);
        } else {
          bubbleEl.classList.remove("is-streaming");
          resolve();
        }
      }
      requestAnimationFrame(step);
    });
  }

  function setSending(sending) {
    sendBtn.classList.toggle("is-sending", sending);
    inputEl.disabled = sending;
    updateSendState();
  }

  // A conversation created mid-session isn't in the server-rendered rail;
  // add it so the thread doesn't look like it vanished.
  function addRailEntry(id, title) {
    conversationsEl.querySelector(".chat-conversations__empty")?.remove();
    const link = document.createElement("a");
    link.className = "chat-conversation-item active";
    link.href = `/chat/${id}`;
    link.innerHTML =
      '<svg class="chat-conversation-item__icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>';
    const span = document.createElement("span");
    span.className = "chat-conversation-item__title";
    span.textContent = title;
    link.appendChild(span);
    conversationsEl.prepend(link);
  }

  form.addEventListener("submit", async (evt) => {
    evt.preventDefault();
    const content = inputEl.value.trim();
    if (!content) return;

    inputEl.value = "";
    autoResize(inputEl);
    setSending(true);

    try {
      // First message from the hero screen has no conversation yet. Create
      // one and swap the URL in place so a reload lands on this thread,
      // without a navigation that would throw away what was typed.
      if (!conversationId) {
        const created = await apiFetch("/chat/new", { method: "POST" });
        conversationId = created.conversation_id;
        form.dataset.conversationId = conversationId;
        history.replaceState(null, "", `/chat/${conversationId}`);
        addRailEntry(conversationId, content.slice(0, 40));
      }

      appendMessage("user", content);
      appendTypingIndicator();

      const data = await apiFetch(`/chat/${conversationId}/message`, {
        method: "POST",
        body: JSON.stringify({ content }),
      });
      removeTypingIndicator();
      const bubble = appendMessage("assistant", "");
      await revealText(bubble, data.reply);
      attachActions(bubble);
    } catch (e) {
      removeTypingIndicator();
      const bubble = appendMessage("assistant", `Something went wrong: ${e.message}`);
      bubble.classList.add("msg-bubble--error");
    } finally {
      setSending(false);
      inputEl.focus();
    }
  });

  // Server-rendered assistant messages get the same hover actions.
  threadEl.querySelectorAll(".msg-row--assistant .msg-bubble").forEach((bubble) => {
    bubble.dataset.raw = bubble.textContent;
    attachActions(bubble);
  });

  updateSendState();
  scrollToBottom(true);
  inputEl.focus();
});
