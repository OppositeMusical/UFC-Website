"use strict";

const { contextBridge } = require("electron");

/**
 * Deliberately minimal. The renderer is the existing Flask UI, which talks
 * to the backend over HTTP and needs nothing from Node - so it gets no IPC
 * surface, only a flag for the small styling differences that make the
 * page feel native (see static/css/theme.css .is-electron).
 */
contextBridge.exposeInMainWorld("ufcPredictor", {
  isDesktop: true,
  platform: process.platform,
});
