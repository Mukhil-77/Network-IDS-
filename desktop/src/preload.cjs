/**
 * SOC Platform - preload script.
 *
 * Exposes a tiny, read-only bridge to the renderer. The dashboard is a
 * normal web app (React) served over http by the local engine, so it has
 * no Node access; this just surfaces environment facts for diagnostics.
 */

"use strict";

const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("socPlatform", {
  version: process.env.npm_package_version || "0.1.0",
  packaged: process.resourcesPath.endsWith("resources"),
  engineUrl: "http://127.0.0.1:8000",
  platform: process.platform,
});