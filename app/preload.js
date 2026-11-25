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

  // Обновления: проверка, скачивание и установка — только с подтверждением.
  update: {
    check: () => ipcRenderer.invoke("update:check"),
    state: () => ipcRenderer.invoke("update:state"),
    download: () => ipcRenderer.invoke("update:download"),
    install: () => ipcRenderer.invoke("update:install"),
    openReleasePage: () => ipcRenderer.invoke("update:openReleasePage"),
    onChange: (handler) => {
      const fn = (_e, info) => handler(info);
      ipcRenderer.on("update:state", fn);
      return () => ipcRenderer.removeListener("update:state", fn);
    }
  },

  // Готовые ответы, которые идут с приложением (по файлу на дисциплину).
  builtin: {
    list: () => ipcRenderer.invoke("builtin:list"),
    parse: (code) => ipcRenderer.invoke("builtin:parse", code),
    answer: (code, num, index, short) =>
      ipcRenderer.invoke("builtin:answer", { code, num, index, short: !!short })
  },

  // Напоминания и запуск вместе с Windows.
  remind: {
    refresh: () => ipcRenderer.invoke("remind:refresh"),
    test: () => ipcRenderer.invoke("remind:test"),
    info: () => ipcRenderer.invoke("remind:info")
  },
  autostart: {
    set: (enable) => ipcRenderer.invoke("app:autostart", enable),
    state: () => ipcRenderer.invoke("app:autostartState")
  },
  onGo: (handler) => {
    const fn = (_e, view) => handler(view);
    ipcRenderer.on("app:go", fn);
    return () => ipcRenderer.removeListener("app:go", fn);
  },

  // Сведения о среде: интерфейсу полезно знать, Electron это или браузер.
  isElectron: true,
  platform: process.platform
};

contextBridge.exposeInMainWorld("api", api);
