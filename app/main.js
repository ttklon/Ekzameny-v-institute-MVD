/*
 * main.js — главный процесс Electron.
 * Отвечает за окно, чтение/декодирование файлов, хранение состояния.
 */
const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const fs = require("fs");
const path = require("path");
const iconv = require("iconv-lite");
const docx = require("./src/docx");

const STORE_FILE = "store.json";

function storePath() {
  return path.join(app.getPath("userData"), STORE_FILE);
}

// Автоматическое определение кодировки и декодирование в UTF-8.
function decodeBuffer(buf) {
  if (!buf || buf.length === 0) return "";
  // BOM UTF-16
  if (buf.length >= 2 && buf[0] === 0xff && buf[1] === 0xfe) return iconv.decode(buf, "utf-16le");
  if (buf.length >= 2 && buf[0] === 0xfe && buf[1] === 0xff) return iconv.decode(buf, "utf-16be");
  // Пробуем UTF-8 (строго).
  try {
    const td = new TextDecoder("utf-8", { fatal: true });
    td.decode(buf.subarray(0, Math.min(buf.length, 20000)));
    return iconv.decode(buf, "utf-8");
  } catch (e) {
    /* не UTF-8 */
  }
  // Иначе предполагаем Windows-1251 (типично для русских файлов из Word/интернета).
  return iconv.decode(buf, "win1251");
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 1024,
    minHeight: 720,
    backgroundColor: "#0b1f3a",
    title: "Облачный планировщик экзаменов",
    frame: true,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  win.loadFile(path.join(__dirname, "renderer", "index.html"));

  win.once("ready-to-show", () => win.show());

  // Лёгкая анимация появления.
  win.once("ready-to-show", () => {
    win.setOpacity(0);
    let op = 0;
    const t = setInterval(() => {
      op += 0.08;
      if (op >= 1) {
        op = 1;
        clearInterval(t);
      }
      try {
        win.setOpacity(op);
      } catch (e) {}
    }, 16);
  });
}

app.whenReady().then(() => {
  createWindow();

  ipcMain.handle("dialog:openFiles", async () => {
    const result = await dialog.showOpenDialog({
      title: "Выберите файлы с вопросами и ответами",
      properties: ["openFile", "multiSelections"],
      filters: [
        { name: "Текст / Word", extensions: ["txt", "md", "docx"] },
        { name: "Все файлы", extensions: ["*"] }
      ]
    });
    if (result.canceled) return [];
    return result.filePaths;
  });

  ipcMain.handle("fs:readFile", async (_e, filePath) => {
    try {
      const buf = fs.readFileSync(filePath);
      const lower = filePath.toLowerCase();
      let text;
      if (lower.endsWith(".docx")) {
        text = await docx.extractDocxText(buf);
      } else {
        text = decodeBuffer(buf);
      }
      return {
        ok: true,
        name: path.basename(filePath),
        path: filePath,
        size: buf.length,
        text
      };
    } catch (err) {
      return { ok: false, error: String(err && err.message ? err.message : err) };
    }
  });

  ipcMain.handle("store:load", async () => {
    try {
      const p = storePath();
      if (!fs.existsSync(p)) return null;
      const raw = fs.readFileSync(p, "utf-8");
      return JSON.parse(raw);
    } catch (e) {
      return null;
    }
  });

  ipcMain.handle("store:save", async (_e, state) => {
    try {
      const p = storePath();
      fs.writeFileSync(p, JSON.stringify(state, null, 2), "utf-8");
      return { ok: true };
    } catch (err) {
      return { ok: false, error: String(err && err.message ? err.message : err) };
    }
  });

  ipcMain.handle("app:version", () => app.getVersion());

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
