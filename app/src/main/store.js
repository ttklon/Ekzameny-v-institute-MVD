/*
 * store.js — хранение данных пользователя.
 *
 * Данные лежат в папке профиля Windows (AppData\Roaming\<приложение>):
 *   library.json    — дисциплины, планы, отметки о прочтении, настройки;
 *   library.bak.json — предыдущая версия (на случай сбоя записи);
 *   texts\<id>.txt  — тексты загруженных файлов.
 *
 * Запись атомарная: сначала во временный файл, потом переименование. Так при
 * выключении компьютера посреди записи не теряется вся библиотека.
 */
"use strict";

const fs = require("fs");
const path = require("path");

function createStore(baseDir) {
  const textsDir = path.join(baseDir, "texts");
  const mainFile = path.join(baseDir, "library.json");
  const backupFile = path.join(baseDir, "library.bak.json");
  const tmpFile = path.join(baseDir, "library.tmp.json");

  function ensureDirs() {
    fs.mkdirSync(baseDir, { recursive: true });
    fs.mkdirSync(textsDir, { recursive: true });
  }

  function readJson(file) {
    try {
      const raw = fs.readFileSync(file, "utf-8");
      return JSON.parse(raw);
    } catch (e) {
      return null;
    }
  }

  /** Читает библиотеку; при повреждении основного файла берёт резервную копию. */
  function load() {
    ensureDirs();
    const main = readJson(mainFile);
    if (main && typeof main === "object") return { state: main, recovered: false };
    const bak = readJson(backupFile);
    if (bak && typeof bak === "object") return { state: bak, recovered: true };
    return { state: null, recovered: false };
  }

  /** Атомарная запись с резервной копией предыдущей версии. */
  function save(state) {
    ensureDirs();
    const json = JSON.stringify(state);
    try {
      fs.writeFileSync(tmpFile, json, "utf-8");
      if (fs.existsSync(mainFile)) {
        try {
          fs.copyFileSync(mainFile, backupFile);
        } catch (e) {
          /* копия не критична */
        }
      }
      fs.renameSync(tmpFile, mainFile);
      return { ok: true, bytes: json.length };
    } catch (err) {
      return { ok: false, error: String(err && err.message ? err.message : err) };
    }
  }

  /** Сохраняет текст загруженного файла, возвращает имя файла в папке texts. */
  function saveText(id, text) {
    ensureDirs();
    const name = String(id).replace(/[^\w-]/g, "_") + ".txt";
    const file = path.join(textsDir, name);
    fs.writeFileSync(file, text, "utf-8");
    return name;
  }

  function loadText(name) {
    try {
      return fs.readFileSync(path.join(textsDir, name), "utf-8");
    } catch (e) {
      return null;
    }
  }

  function removeText(name) {
    try {
      fs.unlinkSync(path.join(textsDir, name));
      return true;
    } catch (e) {
      return false;
    }
  }

  function stats() {
    ensureDirs();
    let bytes = 0;
    try {
      for (const f of fs.readdirSync(textsDir)) {
        try {
          bytes += fs.statSync(path.join(textsDir, f)).size;
        } catch (e) {
          /* пропускаем */
        }
      }
    } catch (e) {
      /* папки нет */
    }
    let libBytes = 0;
    try {
      libBytes = fs.statSync(mainFile).size;
    } catch (e) {
      /* ещё нет файла */
    }
    return { textsBytes: bytes, libraryBytes: libBytes, dir: baseDir };
  }

  /** Резервная копия всей библиотеки в выбранный пользователем файл. */
  function exportTo(targetPath, state) {
    try {
      fs.writeFileSync(targetPath, JSON.stringify(state, null, 2), "utf-8");
      return { ok: true, path: targetPath };
    } catch (err) {
      return { ok: false, error: String(err && err.message ? err.message : err) };
    }
  }

  return {
    load,
    save,
    saveText,
    loadText,
    removeText,
    stats,
    exportTo,
    paths: { baseDir, textsDir, mainFile, backupFile }
  };
}

module.exports = { createStore };
