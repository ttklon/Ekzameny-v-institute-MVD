/*
 * main.js — главный процесс приложения.
 *
 * Отвечает за окно, меню, приём файлов с диска, чтение и разбор документов,
 * сохранение библиотеки. Вся арифметика (парсер, подсчёт, планировщик) лежит
 * в src/core и работает и здесь, и в интерфейсе — поэтому результаты совпадают.
 */
"use strict";

const { app, BrowserWindow, ipcMain, dialog, shell, Menu, nativeTheme, nativeImage } = require("electron");
const fs = require("fs");
const path = require("path");

const { createStore } = require("./src/main/store");
const { createUpdater } = require("./src/main/update");
const { createReminder } = require("./src/main/remind");
const loader = require("./src/main/loader");
const builtin = require("./src/main/builtin");
const parser = require("./src/core/parser");
const planner = require("./src/core/planner");

const APP_TITLE = "Облачный планировщик экзаменов";
const RELEASE_PAGE = "https://github.com/ttklon/Ekzameny-v-institute-MVD/releases/tag/app-latest";
let mainWindow = null;
let store = null;
let updater = null;
let reminder = null;
let quitting = false; // закрытие по-настоящему, а не сворачивание в трей
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

  // Ошибки интерфейса не должны оставаться невидимыми: пишем их в консоль
  // и, если экран так и не ожил, показываем объяснение вместо пустого окна.
  mainWindow.webContents.on("console-message", (_e, level, message, line, sourceId) => {
    if (level >= 2) console.error("[renderer]", message, sourceId + ":" + line);
  });
  mainWindow.webContents.on("did-fail-load", (_e, code, desc, url) => {
    console.error("Не загрузился интерфейс:", code, desc, url);
  });
  mainWindow.webContents.on("render-process-gone", (_e, details) => {
    console.error("Процесс интерфейса завершился:", details && details.reason);
  });

  // Закрытие окна: по настройке — либо свернуть в трей (и напоминать), либо
  // выйти совсем. По умолчанию выходим: неожиданный «невидимый» процесс
  // пугает больше, чем помогает.
  mainWindow.on("close", (e) => {
    const settings = store ? store.load().state : null;
    const toTray = !!(settings && settings.settings && settings.settings.closeToTray);
    if (!quitting && toTray) {
      e.preventDefault();
      mainWindow.hide();
      if (reminder) reminder.refreshTray();
      return;
    }
    quitting = true;
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
  // --- Готовые ответы, которые идут вместе с приложением -------------------
  // Отдаём список дисциплин и полный текст одной из них. Текст остаётся в
  // файлах своего предмета и не попадает в библиотеку: разбираются только
  // заголовки и объёмы, а сам ответ читается при открытии вопроса.
  ipcMain.handle("builtin:list", async () => {
    try {
      return { ok: true, items: builtin.list() };
    } catch (e) {
      return { ok: false, error: String((e && e.message) || e), items: [] };
    }
  });

  ipcMain.handle("builtin:read", async (_e, code) => {
    try {
      const text = builtin.read(String(code || ""));
      if (!text) return { ok: false, error: "файл не найден" };
      return { ok: true, text: text };
    } catch (e) {
      return { ok: false, error: String((e && e.message) || e) };
    }
  });

  // Заголовки и объёмы без текста ответов: именно это кладётся в библиотеку.
  // Разбор файла комплекта — дорогая операция: подробный вариант по
  // административной деятельности весит четыре мегабайта, и разбирать его
  // заново при каждом открытии вопроса (и при каждом показе заголовков)
  // значит ждать полсекунды зря. Держим разобранное в памяти: файл внутри
  // приложения и за время работы не меняется.
  const builtinCache = new Map();
  function parsedBuiltin(code) {
    const text = builtin.read(code);
    if (!text) return null;
    const hit = builtinCache.get(code);
    if (hit && hit.text === text) return hit.parsed;
    const parsed = parser.parseDocument(text, { assumeAnswerWords: 0 });
    // Храним максимум три разобранных файла: больше незачем, память не резиновая.
    if (builtinCache.size > 3) builtinCache.delete(builtinCache.keys().next().value);
    builtinCache.set(code, { text: text, parsed: parsed });
    return parsed;
  }

  ipcMain.handle("builtin:parse", async (_e, code) => {
    try {
      const parsed = parsedBuiltin(String(code || ""));
      if (!parsed) return { ok: false, error: "файл не найден" };
      // Краткий вариант ответов (если он есть) — только объёмы: по ним
      // считается время на повторные чтения, когда человек читает кратко.
      const item = builtin.list().find((x) => x.code === String(code || ""));
      const altParsed = item && item.alt ? parsedBuiltin(item.alt) : null;
      const altByNum = {};
      if (altParsed) for (const aq of altParsed.questions) altByNum[aq.num] = aq;
      // Текст ответа не передаём: он большой и здесь не нужен.
      const questions = parsed.questions.map((q) => ({
        num: q.num,
        listNo: q.listNo,
        question: q.question,
        title: q.title,
        hasAnswer: q.aWords > 0 || (q.answer || "").length > 0,
        qWords: q.qWords,
        aWords: q.aWords,
        qChars: q.qChars,
        aChars: q.aChars,
        charsWithSpaces: q.charsWithSpaces,
        words: q.words,
        chars: q.chars,
        difficulty: q.difficulty,
        // Объём краткого ответа на тот же вопрос: повторное чтение короче.
        altWords: altByNum[q.num] ? altByNum[q.num].words : 0,
        altChars: altByNum[q.num] ? altByNum[q.num].chars : 0
      }));
      return {
        ok: true,
        questions: questions,
        strategy: parsed.strategy,
        count: questions.length,
        answeredCount: questions.filter((q) => q.hasAnswer).length,
        totalWords: parsed.totalWords,
        totalChars: parsed.totalChars,
        hasAlt: !!altParsed,
        altWords: altParsed ? altParsed.totalWords : 0
      };
    } catch (e) {
      return { ok: false, error: String((e && e.message) || e) };
    }
  });

  // Ответ на один вопрос: подгружается только при открытии вопроса.
  ipcMain.handle("builtin:answer", async (_e, payload) => {
    try {
      const code = String((payload && payload.code) || "");
      const num = Number(payload && payload.num);
      const parsed = parsedBuiltin(code);
      if (!parsed) return { ok: false, error: "файл не найден" };
      const q =
        parsed.questions.find((x) => x.num === num) || parsed.questions[Number(payload.index) || 0];
      if (!q) return { ok: false, error: "вопрос не найден" };
      // Второе чтение — кратко: у дисциплины может быть короткий вариант
      // ответа (по административной деятельности он есть). Просит его
      // интерфейс через payload.short, и только если человек уже прочитал
      // вопрос хотя бы раз.
      if (payload && payload.short) {
        const item = builtin.list().find((x) => x.code === code);
        const alt = item && item.alt ? parsedBuiltin(item.alt) : null;
        const aq = alt && (alt.questions.find((x) => x.num === q.num) || alt.questions[Number(payload.index) || 0]);
        if (aq && aq.answer) {
          return { ok: true, question: q.question, answer: aq.answer, variant: "short" };
        }
      }
      return { ok: true, question: q.question, answer: q.answer || "", variant: "full" };
    } catch (e) {
      return { ok: false, error: String((e && e.message) || e) };
    }
  });

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

  ipcMain.handle("app:info", async () => {
    // Номер сборки: версия + дата + короткий коммит. Без него две сборки
    // «1.0.0» неотличимы, и легко открыть старую.
    let build = "";
    try {
      // Штамп дописывает сборка (см. workflow). require работает и внутри asar.
      build = require("./package.json").buildStamp || "";
    } catch (e) {
      /* номер сборки не критичен */
    }
    return {
      version: app.getVersion(),
      build: build,
      platform: process.platform,
      electron: process.versions.electron,
      chrome: process.versions.chrome,
      dataDir: store.paths.baseDir
    };
  });

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

/** Номер сборки: «2026-11-24 / bd98dd1». Дописывается сборкой в package.json. */
function buildStamp() {
  try {
    return require("./package.json").buildStamp || "";
  } catch (e) {
    return "";
  }
}

/** Показать в окне, что нашлось обновление. */
function sendUpdate(info) {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  try {
    mainWindow.webContents.send("update:state", info);
  } catch (e) {
    /* окно могло закрыться */
  }
}

/** Что осталось на сегодня — для трея и напоминания. */
function todayInfo() {
  try {
    const st = store.load().state;
    if (!st) return { tasks: 0, minutes: 0 };
    const today = planner.todayStr();
    const plan = planner.computeAll({ settings: st.settings, disciplines: st.disciplines }, today);
    const items = plan.todayTasks || [];
    return { tasks: items.length, minutes: Math.round(plan.todayMinutes || 0) };
  } catch (e) {
    return { tasks: 0, minutes: 0 };
  }
}

/** Напоминания и значок в трее. */
function startReminder() {
  reminder = createReminder({
    getTodayInfo: todayInfo,
    iconPath: path.join(__dirname, "build", "icon.ico"),
    // В сборке файла build/icon.ico рядом с кодом нет — берём значок окна.
    pickAppIcon: () => {
      // Значок окна уже загружен приложением — используем его.
      try {
        const fromWindow = mainWindow && mainWindow.getIcon ? mainWindow.getIcon() : null;
        if (fromWindow && !fromWindow.isEmpty()) return fromWindow;
      } catch (e) {
        /* пойдём дальше */
      }
      const candidates = [
        path.join(process.resourcesPath || __dirname, "icon.ico"),
        path.join(__dirname, "build", "icon.ico"),
        path.join(__dirname, "build", "icon.png")
      ];
      for (const p of candidates) {
        try {
          const img = nativeImage.createFromPath(p);
          if (img && !img.isEmpty()) return img;
        } catch (e) {
          /* следующий */
        }
      }
      return null;
    },
    onOpen: () => {
      if (!mainWindow) return createWindow();
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    },
    onOpenToday: () => {
      if (!mainWindow) createWindow();
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
      try {
        mainWindow.webContents.send("app:go", "today");
      } catch (e) {
        /* окно ещё грузится */
      }
    },
    onQuit: () => {
      quitting = true;
      app.quit();
    }
  });
  reminder.configure((store.load().state || {}).settings || {});
  reminder.start();

  ipcMain.handle("remind:refresh", async () => {
    const st = store.load().state;
    reminder.configure((st && st.settings) || {});
    return { ok: true };
  });
  ipcMain.handle("remind:test", async () => {
    reminder.notify();
    return { ok: true };
  });
  ipcMain.handle("remind:info", async () => todayInfo());

  // Автозапуск при входе в Windows.
  ipcMain.handle("app:autostart", async (_e, enable) => {
    try {
      app.setLoginItemSettings({ openAtLogin: !!enable, args: [] });
      return { ok: true, enabled: app.getLoginItemSettings().openAtLogin };
    } catch (e) {
      return { ok: false, error: String((e && e.message) || e) };
    }
  });
  ipcMain.handle("app:autostartState", async () => {
    try {
      return { enabled: app.getLoginItemSettings().openAtLogin };
    } catch (e) {
      return { enabled: false };
    }
  });
}

/**
 * Автообновление: раз в минуту спрашиваем GitHub. Ничего не скачивается без
 * подтверждения — сначала в окне появляется вопрос.
 */
function startUpdater() {
  updater = createUpdater({
    currentVersion: app.getVersion(),
    currentBuild: buildStamp(),
    dataDir: store.paths.baseDir,
    log: (msg) => console.log("[обновление] " + msg)
  });
  updater.onEvent(sendUpdate);
  updater.start();

  // Напоминания и трей — удобство, а не условие работы. Если Windows не дала
  // создать значок или уведомления запрещены, окно всё равно должно открыться.
  try {
    startReminder();
  } catch (e) {
    console.error("напоминания не запустились:", e);
    reminder = null;
  }

  ipcMain.handle("update:check", async () => {
    await updater.checkOnce(true);
    return updater.state();
  });
  ipcMain.handle("update:state", async () => updater.state());
  ipcMain.handle("update:download", async () => {
    const r = await updater.downloadUpdate();
    return { ok: true, path: r.path, bytes: r.bytes };
  });

  // Установка. Если файл почему-то не найден — не молчим, а открываем
  // страницу загрузки, чтобы обновление можно было поставить руками.
  ipcMain.handle("update:install", async () => {
    const st = updater.state();
    try {
      updater.install(st.downloadedPath, () => app.quit());
      return { ok: true };
    } catch (e) {
      shell.openExternal(RELEASE_PAGE);
      return { ok: false, error: String((e && e.message) || e), openedPage: true };
    }
  });
  ipcMain.handle("update:openReleasePage", async () => {
    shell.openExternal(RELEASE_PAGE);
    return { ok: true };
  });
}

app.whenReady().then(() => {
  store = createStore(app.getPath("userData"));
  registerIpc();
  createWindow();
  startUpdater();

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
