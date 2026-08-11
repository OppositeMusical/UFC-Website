"""Guards the `hidden` attribute, which every script in static/js/ relies on
to show and hide update UI.

Regression (fixed in 0.5.3): `[hidden] { display: none }` is a *user-agent*
rule, and any author rule beats a user-agent rule outright - specificity is
never consulted. `.update-banner { display: flex }` therefore defeated
`<div class="update-banner" hidden>`, so the dashboard showed a permanent
"Update available" banner to users already on the latest version, and the
Settings page showed all three mutually exclusive update buttons plus a 0%
progress bar at once. No JavaScript was involved: the markup shipped visible.
"""
from __future__ import annotations

import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
THEME_CSS = APP_DIR / "static" / "css" / "theme.css"
TEMPLATES = APP_DIR / "templates"

# `display` declarations carrying !important, as (line number, value).
_IMPORTANT_DISPLAY = re.compile(r"display\s*:\s*([^;}]*?)\s*!\s*important", re.I)


def _theme() -> str:
    return THEME_CSS.read_text(encoding="utf-8")


def test_hidden_attribute_overrides_component_display_rules():
    """theme.css must restate [hidden] itself, because the UA rule loses."""
    css = re.sub(r"/\*.*?\*/", "", _theme(), flags=re.S)
    match = re.search(r"\[hidden\]\s*\{([^}]*)\}", css)
    assert match, "theme.css defines no [hidden] rule - the UA rule alone is not enough"
    assert _IMPORTANT_DISPLAY.search(match.group(1)), (
        "the [hidden] rule must use `display: none !important`. Without it the "
        "rule sits at specificity (0,1,0), the same as any class selector, so "
        "every later `.foo { display: ... }` in this file silently wins."
    )


def test_no_other_important_display_rule_can_outrank_the_hidden_guard():
    """The guard wins on !important alone - as long as it stays the only one.

    A second `display: ... !important` at specificity >= (0,1,0) appearing
    later in the file would beat it and quietly resurrect the bug, so any new
    one has to be justified here rather than discovered in the UI.
    """
    found = [
        (i, line.strip())
        for i, line in enumerate(_theme().splitlines(), 1)
        if _IMPORTANT_DISPLAY.search(line)
    ]
    assert len(found) == 1, f"expected only the [hidden] guard, got: {found}"
    assert found[0][1].startswith("display: none"), found[0]


def test_no_template_hardcodes_an_update_claim():
    """Placeholders that the UI fills in later must not assert anything.

    The dashboard banner is built hidden and populated by status.js. When it
    leaked, the literal text in the template was what users read - so the
    placeholder stays empty and a leak degrades to an empty bar, not a lie.
    """
    # Capture only up to the next "<", so the element's own closing tag isn't
    # mistaken for content.
    placeholder = re.compile(r"id=\"update-banner-(?:title|detail)\"[^>]*>([^<]*)<")
    offenders = [
        (path.relative_to(TEMPLATES).as_posix(), text)
        for path in TEMPLATES.rglob("*.html")
        for text in placeholder.findall(path.read_text(encoding="utf-8"))
        if text.strip()
    ]
    assert not offenders, f"update banner placeholders must ship empty: {offenders}"
