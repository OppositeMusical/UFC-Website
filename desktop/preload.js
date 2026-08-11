"use strict";

const { contextBridge, ipcRenderer } = require("electron");

/**
 * The renderer's entire privileged surface. Keep it this small.
 *
 * The page loaded here is the Flask UI, and the chat screen renders text a
 * language model produced. Treat the renderer as potentially hostile: if
 * XSS ever lands there, everything exposed on this bridge is reachable by
 * the attacker.
 *
 * Hence the shape of the update methods - none of them takes an argument.
 * The renderer can ask the main process to check, download, or install,
 * but it cannot say *what* to download. The feed is pinned at build time
 * (the `publish` block in package.json, baked into app-update.yml) and the
 * downloaded installer's Authenticode signature is verified against
 * `win.publisherName` before it is ever executed. An IPC method that
 * accepted a URL would collapse that into "any XSS is remote code
 * execution"; one that accepts nothing does not.
 */
contextBridge.exposeInMainWorld("mmaAssist", {
  isDesktop: true,
  platform: process.platform,

  updates: {
    /** Current updater state, for a window that opened mid-operation. */
    state: () => ipcRenderer.invoke("updates:state"),
    check: () => ipcRenderer.invoke("updates:check"),
    download: () => ipcRenderer.invoke("updates:download"),
    install: () => ipcRenderer.invoke("updates:install"),

    /**
     * Subscribe to state changes. Returns an unsubscribe function.
     *
     * The listener is wrapped rather than handed to ipcRenderer directly so
     * the renderer never receives the IpcRendererEvent - that object exposes
     * `sender`, which is a way back into the main process.
     */
    onState: (callback) => {
      const listener = (_event, next) => callback(next);
      ipcRenderer.on("updates:state", listener);
      return () => ipcRenderer.removeListener("updates:state", listener);
    },
  },
});
