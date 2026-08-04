# UFC Predictor - Electron shell

Wraps the existing Flask app in a real desktop window instead of opening a
browser tab. The backend is unchanged: Electron spawns it as a child
process, waits for `/health`, and points a `BrowserWindow` at it.

Nothing about the UI was rewritten - the Jinja templates, routes, RAG
pipeline and tests are the same code that runs standalone.

## Run it (development)

```powershell
cd desktop
npm install          # first time only
npm start
```

That spawns `backend/.venv/Scripts/python.exe run.py` with a free port and
`--no-browser`. The backend must have its virtualenv set up already
(`pip install -r requirements.txt` in `backend/`).

### If `npm start` fails with `Cannot read properties of undefined (reading 'requestSingleInstanceLock')`

Your shell has `ELECTRON_RUN_AS_NODE=1` set - **VS Code's integrated
terminal sets this**. It makes the Electron binary behave as plain Node, so
`require("electron")` returns a path string instead of the API and every
`app.*` call fails. Launch from a normal terminal, or clear it first:

```powershell
Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
npm start
```

## Build an installer

> **Rebuild the PyInstaller bundle first, every time `backend/` changes.**
> electron-builder copies `backend/dist/UFCPredictor` in as-is; it has no
> idea the Python source moved on. Skipping this ships a stale backend and
> the failure is confusing rather than obvious - a backend built before
> `--port` existed ignores the flag, binds 8765 instead of the port
> Electron assigned, and the app dies on a health-check timeout while a
> perfectly healthy server sits on the wrong port.

The packaged app ships the PyInstaller build as an extra resource, so build
that first:

```powershell
cd backend
.venv\Scripts\Activate.ps1
pyinstaller pyinstaller/app.spec        # -> backend/dist/UFCPredictor

cd ..\desktop
npm run dist                            # -> desktop/release/*.exe (NSIS installer)
npm run dist:dir                        # unpacked, faster, for testing
```

The installer is large (~380MB: Electron runtime + the Python bundle +
the 28MB seeded fighter database). That is the cost of shipping a Python
app to machines with no Python.

## How it fits together

| File | Role |
| --- | --- |
| `main.js` | Window lifecycle, menu, single-instance lock, external-link handling |
| `backend.js` | Picks a free port, spawns the backend, polls `/health`, kills the process tree on quit |
| `preload.js` | Exposes only `window.ufcPredictor.isDesktop` - the UI needs nothing else |
| `splash.html` | Shown while the backend boots (first launch loads the ONNX embedder + Chroma index) |

### Decisions worth knowing

- **A free port is chosen per launch**, not the fixed 8765. A hard-coded
  port collides with a second copy, an unrelated dev server, or a leftover
  process from a crash - and the symptom is a window that never loads.
- **The child is killed with `taskkill /T`** on Windows. The PyInstaller exe
  is a process tree (bootloader -> real app) and `child.kill()` only signals
  the parent, leaving an orphaned server holding the SQLite file and a port.
- **Startup failures show the backend's own output** in the error dialog. A
  Python traceback is almost always the real answer and is otherwise
  invisible in a packaged app with no console.
- **Off-site links open in the real browser** via `setWindowOpenHandler` and
  `will-navigate`. A chrome-less Electron window is a bad place to land on
  an external site, and worse for anything asking for credentials.
- `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true`.

## Standalone mode still works

`python run.py` behaves exactly as before - binds the default port and opens
your browser. Electron only changes things by passing `--port N
--no-browser`.
