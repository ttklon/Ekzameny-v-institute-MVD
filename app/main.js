/*
 * main.js — главный процесс приложения.
 *
 * Отвечает за окно, меню, приём файлов с диска, чтение и разбор документов,
 * сохранение библиотеки. Вся арифметика (парсер, подсчёт, планировщик) лежит
 * в src/core и работает и здесь, и в интерфейсе — поэтому результаты совпадают.
 */
"use strict";

const { app, BrowserWindow, ipcMain, dialog, shell, Menu, nativeTheme } = require("electron");
const fs = require("fs");
const path = require("path");

const { createStore } = require("./src/main/store");
const loader = require("./src/main/loader");
const parser = require("./src/core/parser");
const planner = require("./src/core/planner");

const APP_TITLE = "Облачный планировщик экзаменов";
let mainWindow = null;
let store = null;
let pendingFiles = []; // файлы, открытые через «Открыть с помощью» / перетаскиванием в ярлык

// Один экземпляр приложения: второй запуск открывает файл в уже работающем окне.
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", (_e, argv) => {
    const files = collectFilesFromArgv(argv);
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
      if (files.length) mainWindow.webContents.send("app:files-dropped", files);
    } else {
      pendingFiles.push(...files);
    }
  });
}

/** Достаёт пути к файлам из аргументов командной строки. */
function collectFilesFromArgv(argv) {
  const out = [];
  for (const a of argv || []) {
    if (!a || a.startsWith("-")) continue;
    if (a === process.execPath) continue;
    try {
      if (fs.existsSync(a) && fs.statSync(a).isFile()) out.push(path.resolve(a));
    } catch (e) {
      /* не файл */
    }
  }
  return out;
}

function createWindow() {
  nativeTheme.themeSource = "light";

  mainWindow = new BrowserWindow({
    width: 1440,
    height: 940,
    minWidth: 1024,
    minHeight: 700,
    backgroundColor: "#0e2a47",
    title: APP_TITLE,
    show: false,
    autoHideMenuBar: true,
    icon: path.join(__dirname, "build", "icon.png"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      spellcheck: false,
      backgroundThrottling: false
    }
  });

  mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"));

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  // Внешние ссылки — в браузере, не внутри приложения.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:/i.test(url)) shell.openExternal(url);
    return { action: "deny" };
  });
  mainWindow.webContents.on("will-navigate", (e, url) => {
    if (!url.startsWith("file://")) {
      e.preventDefault();
      if (/^https?:/i.test(url)) shell.openExternal(url);
    }
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  buildMenu();
}

function buildMenu() {
  const template = [
    {
      label: "Файл",
      submenu: [
        {
          label: "Добавить файлы…",
          accelerator: "CmdOrCtrl+O",
          click: () => mainWindow && mainWindow.webContents.send("menu:add-files")
        },
        {
          label: "Добавить папку…",
          accelerator: "CmdOrCtrl+Shift+O",
          click: () => mainWindow && mainWindow.webContents.send("menu:add-folder")
        },
        { type: "separator" },
        {
          label: "Сохранить копию библиотеки…",
          click: () => mainWindow && mainWindow.webContents.send("menu:backup")
        },
        { type: "separator" },
        { role: "quit", label: "Выход" }
      ]
    },
    {
      label: "Правка",
      submenu: [
        { role: "undo", label: "Отменить" },
        { role: "redo", label: "Повторить" },
        { type: "separator" },
        { role: "cut", label: "Вырезать" },
        { role: "copy", label: "Копировать" },
        { role: "paste", label: "Вставить" },
        { role: "selectAll", label: "Выделить всё" }
      ]
    },
    {
      label: "Вид",
      submenu: [
        { role: "reload", label: "Обновить" },
        { role: "toggleDevTools", label: "Инструменты разработчика" },
        { type: "separator" },
        { role: "resetZoom", label: "Обычный масштаб" },
        { role: "zoomIn", label: "Крупнее" },
        { role: "zoomOut", label: "Мельче" },
        { type: "separator" },
        { role: "togglefullscreen", label: "Во весь экран" }
      ]
    },
    {
      label: "Справка",
      submenu: [
        {
          label: "Как это работает",
          click: () => mainWindow && mainWindow.webContents.send("menu:help")
        },
        {
          label: "Папка с данными",
          click: () => {
            const dir = store ? store.paths.baseDir : app.getPath("userData");
            shell.openPath(dir);
          }
        },
        { type: "separator" },
        {
          label: "О программе",
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: "info",
              title: "О программе",
              message: APP_TITLE,
              detail:
                "Версия " + app.getVersion() + "\n\n" +
                "Планировщик подготовки к экзаменам по файлам «вопрос — ответ».\n" +
                "Считает объём и время чтения, распределяет работу по дням,\n" +
                "планирует повторения и пересчитывает план по отметкам.\n\n" +
                "Данные хранятся только на этом компьютере.",
              buttons: ["Закрыть"]
            });
          }
        }
      ]
    }
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// ---------- IPC ----------

function registerIpc() {
  // Диалог выбора файлов.
  ipcMain.handle("dialog:openFiles", async () => {
    const res = await dialog.showOpenDialog(mainWindow, {
      title: "Выберите файлы с вопросами и ответами",
      properties: ["openFile", "multiSelections"],
      filters: [
        { name: "Тексты и документы", extensions: ["txt", "md", "docx", "doc", "odt", "rtf", "pdf", "html", "htm", "csv"] },
        { name: "Все файлы", extensions: ["*"] }
      ]
    });
    return res.canceled ? [] : res.filePaths;
  });

  // Диалог выбора папки и список подходящих файлов в ней.
  ipcMain.handle("dialog:openFolder", async () => {
    const res = await dialog.showOpenDialog(mainWindow, {
      title: "Выберите папку с файлами ответов",
      properties: ["openDirectory"]
    });
    if (res.canceled || !res.filePaths.length) return { dir: null, files: [] };
    const dir = res.filePaths[0];
    return { dir: dir, files: loader.listTextFiles(dir) };
  });

  // Чтение и разбор одного файла.
  ipcMain.handle("file:read", async (_e, filePath) => {
    const r = await loader.readFile(filePath);
    if (!r.ok) return r;
    // Разбор делаем сразу в главном процессе: для больших файлов это заметно
    // быстрее, а интерфейс получает готовый результат.
    try {
      const parsed = parser.parseDocument(r.text, { assumeAnswerWords: 250 });
      return {
        ok: true,
        name: r.name,
        path: r.path,
        kind: r.kind,
        bytes: r.bytes,
        encoding: r.encoding,
        pages: r.pages,
        text: r.text,
        warnings: r.warnings,
        parsed: {
          questions: parsed.questions,
          strategy: parsed.strategy,
          warnings: parsed.warnings,
          count: parsed.count,
          answeredCount: parsed.answeredCount,
          totalWords: parsed.totalWords,
          totalChars: parsed.totalChars,
          avgWords: parsed.avgWords
        }
      };
    } catch (err) {
      return { ok: false, error: "Ошибка разбора: " + (err.message || err) };
    }
  });

  // Повторный разбор уже загруженного текста с другими параметрами.
  ipcMain.handle("text:parse", async (_e, payload) => {
    try {
      const parsed = parser.parseDocument(payload.text || "", {
        assumeAnswerWords: payload.assumeAnswerWords || 250
      });
      return { ok: true, parsed: parsed };
    } catch (err) {
      return { ok: false, error: String(err.message || err) };
    }
  });

  ipcMain.handle("store:load", async () => {
    const r = store.load();
    return r;
  });

  ipcMain.handle("store:save", async (_e, state) => {
    return store.save(state);
  });

  ipcMain.handle("store:saveText", async (_e, payload) => {
    try {
      const name = store.saveText(payload.id, payload.text);
      return { ok: true, name: name };
    } catch (err) {
      return { ok: false, error: String(err.message || err) };
    }
  });

  ipcMain.handle("store:loadText", async (_e, name) => {
    const t = store.loadText(name);
    return t === null ? { ok: false } : { ok: true, text: t };
  });

  ipcMain.handle("store:removeText", async (_e, name) => {
    return { ok: store.removeText(name) };
  });

  ipcMain.handle("store:stats", async () => store.stats());

  ipcMain.handle("store:export", async (_e, state) => {
    const res = await dialog.showSaveDialog(mainWindow, {
      title: "Сохранить копию библиотеки",
      defaultPath: "библиотека-" + planner.todayStr() + ".json",
      filters: [{ name: "Библиотека (JSON)", extensions: ["json"] }]
    });
    if (res.canceled) return { ok: false, canceled: true };
    return store.exportTo(res.filePath, state);
  });

  // Экспорт плана в CSV — чтобы распечатать или открыть в Excel.
  ipcMain.handle("plan:exportCsv", async (_e, payload) => {
    const res = await dialog.showSaveDialog(mainWindow, {
      title: "Сохранить план в CSV",
      defaultPath: "план-" + planner.todayStr() + ".csv",
      filters: [{ name: "Таблица CSV", extensions: ["csv"] }]
    });
    if (res.canceled) return { ok: false, canceled: true };
    try {
      fs.writeFileSync(res.filePath, "\uFEFF" + payload.csv, "utf-8");
      return { ok: true, path: res.filePath };
    } catch (err) {
      return { ok: false, error: String(err.message || err) };
    }
  });

  // Открыть файл вопроса во внешней программе.
  ipcMain.handle("file:reveal", async (_e, filePath) => {
    if (filePath && fs.existsSync(filePath)) {
      shell.showItemInFolder(filePath);
      return { ok: true };
    }
    return { ok: false };
  });

  ipcMain.handle("app:info", async () => ({
    version: app.getVersion(),
    platform: process.platform,
    electron: process.versions.electron,
    chrome: process.versions.chrome,
    dataDir: store.paths.baseDir
  }));

  ipcMain.handle("app:openDataDir", async () => {
    shell.openPath(store.paths.baseDir);
    return { ok: true };
  });

  ipcMain.handle("app:openExternal", async (_e, url) => {
    if (/^https?:/i.test(url)) {
      shell.openExternal(url);
      return { ok: true };
    }
    return { ok: false };
  });

  ipcMain.handle("app:takePendingFiles", async () => {
    const files = pendingFiles.slice();
    pendingFiles = [];
    return files;
  });
}

// ---------- Запуск ----------

app.whenReady().then(() => {
  store = createStore(app.getPath("userData"));
  registerIpc();
  createWindow();

  const initial = collectFilesFromArgv(process.argv.slice(1));
  if (initial.length) pendingFiles.push(...initial);

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

// Безопасность: запрещаем переходы в неизвестные документы.
app.on("web-contents-created", (_e, contents) => {
  contents.on("will-attach-webview", (ev) => ev.preventDefault());
});
