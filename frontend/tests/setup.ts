import "@testing-library/jest-dom/vitest";

// jsdom implements no layout, so Element.prototype.scrollIntoView does not
// exist. common.js calls it while moving the autocomplete highlight, which
// surfaced as an unhandled TypeError on every run - harmless in itself, but
// Vitest's own warning is the point: an unhandled error in the run can mask
// a real one. Stub it rather than guarding the production code for a
// browser API that always exists in a browser.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function scrollIntoView() {};
}
