import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it, beforeEach, vi } from "vitest";

/**
 * Tests backend/app/static/js/common.js, which is a plain <script> served by
 * Flask rather than a module. It lives in this suite because vitest+jsdom is
 * the only JS harness in the repo, and the alternative - no coverage at all -
 * is how a regression shipped that silently broke every prediction.
 */
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const COMMON_JS = readFileSync(
  path.resolve(__dirname, "../../backend/app/static/js/common.js"),
  "utf-8"
);

const FIGHTERS = [
  { id: 3047, name: "Jon Jones", weight_class: "Heavyweight" },
  { id: 207, name: "Alex Pereira", weight_class: "Heavyweight" },
];

function setup() {
  document.body.innerHTML = `
    <form id="bet-form">
      <div class="autocomplete">
        <input type="text" id="fighter-a-input" />
        <input type="hidden" id="fighter-a-id" />
        <div class="autocomplete__results" id="fighter-a-results"></div>
      </div>
    </form>`;

  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(FIGHTERS) }))
  );

  // Indirect eval so the file's top-level function declarations land on
  // globalThis, the same way they do as a browser <script>.
  (0, eval)(COMMON_JS);

  const input = document.getElementById("fighter-a-input") as HTMLInputElement;
  const hidden = document.getElementById("fighter-a-id") as HTMLInputElement;
  const results = document.getElementById("fighter-a-results") as HTMLDivElement;

  (globalThis as unknown as { attachAutocomplete: Function }).attachAutocomplete(input, results, hidden);
  return { input, hidden, results };
}

/** Types a query and waits out the 200ms debounce plus the fetch. */
async function type(input: HTMLInputElement, value: string) {
  input.value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  await new Promise((r) => setTimeout(r, 260));
}

describe("fighter autocomplete", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("keeps the hidden id after picking a result with the mouse", async () => {
    // Regression: select() dispatched a native "input" event to notify the
    // page, but the autocomplete's own input handler clears the hidden id on
    // every input. The id was wiped microseconds after being set, so every
    // submit failed with "Pick both fighters from the autocomplete dropdown"
    // even though a fighter had just been picked.
    const { input, hidden, results } = setup();

    await type(input, "jon");
    const option = results.querySelector(".autocomplete__result") as HTMLElement;
    expect(option).toBeTruthy();

    option.click();

    expect(input.value).toBe("Jon Jones");
    expect(hidden.value).toBe("3047");
  });

  it("keeps the hidden id after picking with the keyboard", async () => {
    const { input, hidden } = setup();

    await type(input, "jon");
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));

    expect(hidden.value).toBe("3047");
  });

  it("notifies the page with a custom event, not a native input event", async () => {
    // The distinction is load-bearing: a native "input" event re-enters the
    // handler that clears the id.
    const { input, results } = setup();
    const onSelect = vi.fn();
    document.getElementById("bet-form")!.addEventListener("autocomplete:select", onSelect);

    await type(input, "jon");
    (results.querySelector(".autocomplete__result") as HTMLElement).click();

    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("clears the hidden id when the user edits the text after choosing", async () => {
    // The clearing behaviour itself is correct and must survive the fix:
    // a stale id with edited text would submit the wrong fighter.
    const { input, hidden, results } = setup();

    await type(input, "jon");
    (results.querySelector(".autocomplete__result") as HTMLElement).click();
    expect(hidden.value).toBe("3047");

    await type(input, "jon jo");
    expect(hidden.value).toBe("");
  });

  it("does not reopen the dropdown straight after choosing", async () => {
    // The same stray "input" event also restarted the debounced fetch, so
    // the list popped back open ~200ms after every selection.
    const { input, results } = setup();

    await type(input, "jon");
    (results.querySelector(".autocomplete__result") as HTMLElement).click();
    expect(results.classList.contains("open")).toBe(false);

    await new Promise((r) => setTimeout(r, 300));
    expect(results.classList.contains("open")).toBe(false);
  });
});
