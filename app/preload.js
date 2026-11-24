/*
 * preload.js — безопасный мост между renderer и главным процессом.
 */
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("api", {
  openFiles: () => ipcRenderer.invoke("dialog:openFiles"),
  readFile: (filePath) => ipcRenderer.invoke("fs:readFile", filePath),
  loadState: () => ipcRenderer.invoke("store:load"),
  saveState: (state) => ipcRenderer.invoke("store:save", state),
  getVersion: () => ipcRenderer.invoke("app:version")
});
