#!/usr/bin/env bash
#
# Builds the macOS app. MUST be run on a Mac - see macos/README.md for why
# this cannot be cross-compiled from Windows.
#
#   ./macos/build.sh              # build only
#   ./macos/build.sh --publish    # also stage it for the download page
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$REPO_ROOT/backend"
DESKTOP="$REPO_ROOT/desktop"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This must run on macOS. PyInstaller freezes the interpreter and native"
  echo "extensions of the machine it runs on - it cannot produce a Mac binary"
  echo "from Windows or Linux. See macos/README.md."
  exit 1
fi

echo "==> 1/4  Python bundle (PyInstaller)"
cd "$BACKEND"
if [[ ! -d .venv ]]; then
  echo "No virtualenv at backend/.venv - create it first:"
  echo "  python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi
source .venv/bin/activate
pyinstaller pyinstaller/app.spec --noconfirm --distpath dist --workpath build

# The Electron shell launches this by name; catching a rename here beats a
# window that never appears.
if [[ ! -x "dist/UFCPredictor/UFCPredictor" ]]; then
  echo "Expected dist/UFCPredictor/UFCPredictor - PyInstaller produced something else."
  exit 1
fi

echo "==> 2/4  Freshness check"
# Same guard as the Windows signing script: electron-builder copies dist/ in
# verbatim and cannot tell the Python source moved on. A stale bundle ships
# old templates/JS and the failure is silent.
if [[ -n "$(find app run.py -newer dist/UFCPredictor/UFCPredictor \
      \( -name '*.py' -o -name '*.js' -o -name '*.css' -o -name '*.html' \) \
      -not -path '*/__pycache__/*' -print -quit)" ]]; then
  echo "Backend sources are newer than the bundle - rerun step 1."
  exit 1
fi

echo "==> 3/4  Electron app (electron-builder)"
cd "$DESKTOP"
[[ -d node_modules ]] || npm ci
# Signing and notarization are opt-in: without an Apple Developer identity
# this still produces a working .app, it just trips Gatekeeper on other
# machines. CSC_IDENTITY_AUTO_DISCOVERY=false stops electron-builder failing
# the build when it cannot find a certificate.
if [[ -z "${APPLE_TEAM_ID:-}" ]]; then
  echo "    (no APPLE_TEAM_ID - building unsigned; see macos/README.md)"
  export CSC_IDENTITY_AUTO_DISCOVERY=false
fi
npx electron-builder --mac

echo "==> 4/4  Artifacts"
ls -lh "$DESKTOP/release"/*.dmg "$DESKTOP/release"/*.zip 2>/dev/null || true

if [[ "${1:-}" == "--publish" ]]; then
  echo "==> Staging for the download page"
  cd "$BACKEND"
  python scripts/build_release.py --platform mac
fi

echo
echo "Done. Unsigned builds are quarantined by Gatekeeper on any machine that"
echo "downloads them - see macos/README.md before sharing this."
