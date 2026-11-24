/*
 * preload.js — мост между интерфейсом и главным процессом.
 *
 * Интерфейс не имеет прямого доступа к Node: он видит только этот набор
 * функций. Так безопаснее и понятнее: всё, что можно сделать с диском,
 * перечислено здесь.
 */
"use strict";

const { contextBridge, ipcRenderer, webUtils } = require("electron");

const api = {
  // Файлы.
  openFiles: () => ipcRenderer.invoke("dialog:openFiles"),
  openFolder: () => ipcRenderer.invoke("dialog:openFolder"),
  readFile: (filePath) => ipcRenderer.invoke("file:read", filePath),
  parseText: (text, assumeAnswerWords) =>
    ipcRenderer.invoke("text:parse", { text, assumeAnswerWords }),
  revealFile: (filePath) => ipcRenderer.invoke("file:reveal", filePath),
  // Настоящий путь перетащенного файла. В Electron 32+ File.path убран,
  // путь отдаёт webUtils.
  getPathForFile: (file) => {
    try {
      return webUtils.getPathForFile(file) || null;
    } catch (e) {
      return (file && file.path) || null;
    }
  },

  // Хранение.
  loadState: () => ipcRenderer.invoke("store:load"),
  saveState: (state) => ipcRenderer.invoke("store:save", state),
  saveText: (id, text) => ipcRenderer.invoke("store:saveText", { id, text }),
  loadText: (name) => ipcRenderer.invoke("store:loadText", name),
  removeText: (name) => ipcRenderer.invoke("store:removeText", name),
  storageStats: () => ipcRenderer.invoke("store:stats"),
  exportBackup: (state) => ipcRenderer.invoke("store:export", state),
  exportCsv: (csv) => ipcRenderer.invoke("plan:exportCsv", { csv }),

  // Приложение.
  info: () => ipcRenderer.invoke("app:info"),
  openDataDir: () => ipcRenderer.invoke("app:openDataDir"),
  openExternal: (url) => ipcRenderer.invoke("app:openExternal", url),
  takePendingFiles: () => ipcRenderer.invoke("app:takePendingFiles"),

  // События из меню и из второго запуска.
  onMenu: (handler) => {
    const listeners = {
      "menu:add-files": () => handler("add-files"),
      "menu:add-folder": () => handler("add-folder"),
      "menu:backup": () => handler("backup"),
      "menu:help": () => handler("help")
    };
    for (const [channel, fn] of Object.entries(listeners)) ipcRenderer.on(channel, fn);
    return () => {
      for (const [channel, fn] of Object.entries(listeners)) ipcRenderer.removeListener(channel, fn);
    };
  },
  onFilesDropped: (handler) => {
    const fn = (_e, files) => handler(files);
    ipcRenderer.on("app:files-dropped", fn);
    return () => ipcRenderer.removeListener("app:files-dropped", fn);
  },

  // Сведения о среде: интерфейсу полезно знать, Electron это или браузер.
  isElectron: true,
  platform: process.platform
};

contextBridge.exposeInMainWorld("api", api);
