import "@testing-library/jest-dom/vitest";

// jsdom implements no layout, so Element.prototype.scrollIntoView does not
// exist. The fighter autocomplete calls it when the highlight moves with the
// arrow keys, which threw an unhandled TypeError from an event listener.
//
// Vitest counted the tests as passing and still exited non-zero, so `npm test`
// has been failing at the exit-code level while printing "34 passed" - invisible
// until CI, which reads the exit code rather than the summary.
//
// A no-op is the right shim: scrolling a highlighted option into view is
// behaviour with no observable result in a headless DOM, and asserting on it
// would be asserting on jsdom rather than on the app.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function scrollIntoView() {};
}
