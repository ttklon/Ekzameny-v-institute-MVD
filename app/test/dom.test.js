/*
 * test/dom.test.js — проверка интерфейса без запуска окна.
 *
 * Поднимает renderer в jsdom: подключает скрипты в том же порядке, что и
 * index.html, подменяет window.api заглушкой и проходит по всем экранам.
 * Так видно настоящие ошибки отрисовки, а не только синтаксис.
 */
"use strict";

const fs = require("fs");
const path = require("path");
const { JSDOM } = require("jsdom");

const ROOT = path.join(__dirname, "..");
const SANDBOX = path.join(__dirname, "fixtures");

let failures = 0;
let passed = 0;
const errors = [];

function check(name, fn) {
  try {
    fn();
    passed++;
    console.log("  ✓ " + name);
  } catch (err) {
    failures++;
    errors.push({ name, err });
    console.log("  ✗ " + name + "\n      " + (err && err.message ? err.message : err));
  }
}

function makeDom() {
  const html = fs.readFileSync(path.join(ROOT, "renderer", "index.html"), "utf-8");
  // Скрипты подключаем сами — jsdom не должен ходить по file:// путям.
  const stripped = html.replace(/<script[\s\S]*?<\/script>/g, "");
  const dom = new JSDOM(stripped, {
    url: "http://localhost/",
    pretendToBeVisual: true,
    runScripts: "outside-only"
  });
  const win = dom.window;

  // Что обычно даёт Electron/браузер, а в jsdom нет.
  win.requestAnimationFrame = (cb) => setTimeout(() => cb(win.performance.now()), 8);
  win.cancelAnimationFrame = (id) => clearTimeout(id);
  if (!win.matchMedia) {
    win.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
  }
  win.HTMLCanvasElement.prototype.getContext = function () {
    // Заглушка 2D-контекста: небо не рисуем, но коду нужно, чтобы вызовы не падали.
    const noop = () => {};
    return {
      setTransform: noop, clearRect: noop, fillRect: noop, beginPath: noop, arc: noop,
      fill: noop, stroke: noop, save: noop, restore: noop, translate: noop, moveTo: noop,
      lineTo: noop, quadraticCurveTo: noop, createLinearGradient: () => ({ addColorStop: noop }),
      createRadialGradient: () => ({ addColorStop: noop }), fillText: noop,
      globalAlpha: 1, fillStyle: "", strokeStyle: "", lineWidth: 1, lineCap: "", font: "",
      canvas: this
    };
  };
  win.AudioContext = function () {
    return {
      state: "running",
      currentTime: 0,
      sampleRate: 44100,
      destination: {},
      resume: () => {},
      createGain: () => ({ gain: { value: 0, setValueAtTime() {}, exponentialRampToValueAtTime() {} }, connect() {}, disconnect() {} }),
      createOscillator: () => ({ type: "", frequency: { setValueAtTime() {}, exponentialRampToValueAtTime() {} }, connect() {}, disconnect() {}, start() {}, stop() {}, onended: null }),
      createBiquadFilter: () => ({ type: "", frequency: { value: 0 }, Q: { value: 0 }, connect() {}, disconnect() {} }),
      createBuffer: (ch, len) => ({ getChannelData: () => new Float32Array(len) }),
      createBufferSource: () => ({ buffer: null, connect() {}, disconnect() {}, start() {}, stop() {} })
    };
  };

  // Заглушка API Electron.
  const texts = new Map();
  let saved = null;
  win.api = {
    openFiles: async () => [],
    openFolder: async () => ({ dir: null, files: [] }),
    readFile: async (p) => {
      const name = path.basename(p);
      const text = fs.readFileSync(p, "utf-8");
      const parser = require(path.join(ROOT, "src", "core", "parser.js"));
      const parsed = parser.parseDocument(text, { assumeAnswerWords: 250 });
      return {
        ok: true, name, path: p, kind: "text", bytes: text.length, encoding: "utf-8",
        text, warnings: [], pages: 0,
        parsed: {
          questions: parsed.questions, strategy: parsed.strategy, warnings: parsed.warnings,
          count: parsed.count, answeredCount: parsed.answeredCount,
          totalWords: parsed.totalWords, totalChars: parsed.totalChars, avgWords: parsed.avgWords
        }
      };
    },
    parseText: async (text, assume) => {
      const parser = require(path.join(ROOT, "src", "core", "parser.js"));
      return { ok: true, parsed: parser.parseDocument(text, { assumeAnswerWords: assume }) };
    },
    revealFile: async () => ({ ok: true }),
    loadState: async () => ({ state: null, recovered: false }),
    saveState: async (state) => {
      saved = JSON.parse(JSON.stringify(state));
      return { ok: true };
    },
    saveText: async (id, text) => {
      texts.set(id, text);
      return { ok: true, name: id + ".txt" };
    },
    loadText: async (name) => {
      const id = name.replace(/\.txt$/, "");
      return texts.has(id) ? { ok: true, text: texts.get(id) } : { ok: false };
    },
    removeText: async () => ({ ok: true }),
    storageStats: async () => ({ textsBytes: 1234, libraryBytes: 4321, dir: "/tmp" }),
    exportBackup: async () => ({ ok: true, path: "/tmp/backup.json" }),
    exportCsv: async () => ({ ok: true, path: "/tmp/plan.csv" }),
    info: async () => ({ version: "1.0.0", platform: "win32", electron: "33.4.11", chrome: "130", dataDir: "/tmp" }),
    openDataDir: async () => ({ ok: true }),
    openExternal: async () => ({ ok: true }),
    takePendingFiles: async () => [],
    onMenu: () => () => {},
    onFilesDropped: () => () => {},
    isElectron: true,
    platform: "win32"
  };

  return { dom, win, getSaved: () => saved };
}

function readFixture(name) {
  return fs.readFileSync(path.join(SANDBOX, name), "utf-8");
}

function loadScripts(win) {
  const files = [
    "src/core/text.js",
    "src/core/parser.js",
    "src/core/planner.js",
    "renderer/js/sky.js",
    "renderer/js/sound.js",
    "renderer/js/store.js",
    "renderer/js/ui.js",
    "renderer/js/views.js",
    "renderer/js/app.js"
  ];
  for (const f of files) {
    const code = fs.readFileSync(path.join(ROOT, f), "utf-8");
    win.eval(code);
  }
}

/** Небольшая пауза: даём отработать промисам и requestAnimationFrame. */
function tick(ms) {
  return new Promise((r) => setTimeout(r, ms || 30));
}

async function run() {
  console.log("Проверка интерфейса (jsdom)\n");

  const { win, getSaved } = makeDom();
  loadScripts(win);

  // Запуск приложения.
  win.document.dispatchEvent(new win.Event("DOMContentLoaded"));
  await tick(120);

  check("приложение запустилось и нарисовало обзор", () => {
    const view = win.document.getElementById("view");
    if (!view || !view.children.length) throw new Error("экран пуст");
    if (!view.textContent.includes("Пока пусто")) throw new Error("нет приглашения добавить файл: " + view.textContent.slice(0, 120));
  });

  check("навигация построена", () => {
    const nav = win.document.getElementById("nav");
    if (nav.children.length < 6) throw new Error("пунктов меню: " + nav.children.length);
  });

  // Импорт одного файла через API и добавление дисциплины.
  const samplePath = path.join(SANDBOX, "sample-all-answers.txt");

  // Добавим две дисциплины с разными сроками — проверим планировщик и экраны.
  await win.api.readFile(samplePath).then((r) => {
    win.Store.addDiscipline({
      name: "Административная деятельность полиции",
      fileName: r.name,
      questions: r.parsed.questions,
      parsing: { strategy: r.parsed.strategy, count: r.parsed.count }
    });
  });
  await win.api.readFile(path.join(SANDBOX, "sample-single-question.txt")).then((r) => {
    win.Store.addDiscipline({
      name: "Уголовное право",
      fileName: r.name,
      questions: r.parsed.questions,
      parsing: { strategy: r.parsed.strategy, count: r.parsed.count }
    });
  });
  await tick(80);

  check("дисциплины добавились", () => {
    const n = win.Store.activeDisciplines().length;
    if (n !== 2) throw new Error("дисциплин: " + n);
  });

  check("план посчитан и есть задачи", () => {
    const p = win.Views.plan();
    if (!p.totals.questions) throw new Error("нет вопросов в плане");
    if (!Object.keys(p.combined).length) throw new Error("календарь пуст");
  });

  // Проходим по всем экранам.
  const screens = ["dashboard", "today", "disciplines", "calendar", "stats", "tips", "settings"];
  for (const screen of screens) {
    win.App.go(screen);
    await tick(40);
    check("экран «" + screen + "» отрисован", () => {
      const view = win.document.getElementById("view");
      if (!view.children.length) throw new Error("экран пуст");
      const text = view.textContent.trim();
      if (text.length < 20) throw new Error("слишком мало текста: " + text);
      if (/Не удалось показать экран/.test(text)) throw new Error("экран упал: " + text.slice(0, 300));
    });
  }

  // Экран дисциплины со всеми вкладками.
  const disc = win.Store.activeDisciplines()[0];
  win.App.go("discipline", { id: disc.id });
  await tick(50);
  check("экран дисциплины отрисован", () => {
    const view = win.document.getElementById("view");
    if (!view.textContent.includes(disc.name)) throw new Error("нет названия дисциплины");
    if (/Не удалось показать/.test(view.textContent)) throw new Error(view.textContent.slice(0, 300));
  });

  for (const tab of ["questions", "schedule", "settings", "plan"]) {
    win.Views.setDiscTab(tab);
    win.App.refresh();
    await tick(35);
    check("вкладка дисциплины «" + tab + "»", () => {
      const view = win.document.getElementById("view");
      if (/Не удалось показать/.test(view.textContent)) throw new Error(view.textContent.slice(0, 300));
      if (view.textContent.trim().length < 30) throw new Error("пусто");
    });
  }

  // Отметка прочтения и пересчёт.
  check("отметка прочтения сохраняется и план пересчитывается", () => {
    const today = win.ExamCore.planner.todayStr();
    const before = win.Views.plan().perDisc[disc.id].stats.minutesLeft;
    win.Store.setRead(disc.id, 0, today, true);
    const after = win.Views.plan().perDisc[disc.id].stats.minutesLeft;
    if (!(after < before)) throw new Error("остаток не уменьшился: " + before + " → " + after);
    const reads = disc.reads["0"];
    if (!reads || reads.indexOf(today) === -1) throw new Error("отметка не записалась");
    win.Store.setRead(disc.id, 0, today, false);
    const back = win.Views.plan().perDisc[disc.id].stats.minutesLeft;
    if (Math.abs(back - before) > 0.01) throw new Error("при снятии отметки остаток не вернулся: " + before + " vs " + back);
  });

  // Оценка объёма для вопросов без ответов: пересчёт меняет время, но не отметки.
  check("оценка объёма пересчитывается и план обновляется", () => {
    const r = require(path.join(ROOT, "src", "core", "parser.js")).parseDocument(
      readFixture("sample-question-list.txt"),
      { assumeAnswerWords: 250 }
    );
    win.Store.addDiscipline({ id: "est", name: "Перечень", questions: r.questions, assumeAnswerWords: 250 });
    const before = win.Views.plan().perDisc["est"].stats.minutesTotal;
    const disc2 = win.Store.getDiscipline("est");
    // Ставим оценку 500 слов — время должно вырасти примерно вдвое.
    disc2.assumeAnswerWords = 500;
    const t = win.ExamCore.text;
    for (const q of disc2.questions) {
      if (!q.estimated) continue;
      const sample = new Array(501).join("слово ");
      const aStat = t.analyze(sample.trim(), "wpm", 1);
      q.aWords = aStat.words;
      q.aChars = aStat.chars;
      q.words = q.qWords + aStat.words;
      q.chars = q.qChars + aStat.chars;
    }
    const after = win.Views.plan().perDisc["est"].stats.minutesTotal;
    if (!(after > before * 1.6)) throw new Error("время не выросло: " + before + " → " + after);
    win.Store.removeDiscipline("est");
  });

  // Экран дня с задачами.
  win.App.go("today");
  await tick(40);
  check("на экране дня есть чек-лист", () => {
    const view = win.document.getElementById("view");
    const tasks = view.querySelectorAll(".task");
    if (!tasks.length) throw new Error("нет ни одной задачи");
    if (!view.querySelector(".task-check")) throw new Error("нет чекбоксов");
  });

  // Модальное окно вопроса.
  win.App.openQuestion(disc.id, 0);
  await tick(80);
  check("окно вопроса открылось с текстом ответа", () => {
    const modal = win.document.querySelector("#modal-root .modal");
    if (!modal) throw new Error("окно не открылось");
    const text = modal.textContent;
    if (text.trim().length < 100) throw new Error("мало текста в окне: " + text.slice(0, 200));
    if (!modal.querySelector(".qv-title")) throw new Error("нет заголовка вопроса");
  });
  check("ответ размечен: выноска «Главное», жирный, курсив", () => {
    const modal = win.document.querySelector("#modal-root .modal");
    if (!modal) throw new Error("окно не открылось");
    if (!modal.querySelector(".callout")) throw new Error("нет выноски «Главное»");
    const text = modal.querySelector(".qv-text");
    if (!text) throw new Error("нет текста ответа");
    if (!text.querySelector("b")) throw new Error("нет жирного");
    if (!text.querySelector("i")) throw new Error("нет курсива");
    if (/\*\*|\/\/(?![^<]*>)/.test(text.textContent)) throw new Error("разметка не убрана из текста");
    // Подчёркивания в этом файле нет — проверяем отдельным образцом.
    const probe = win.document.createElement("div");
    probe.appendChild(win.App.__inlineForTest("__подчёркнуто__ и **жирно** и //курсив//"));
    if (!probe.querySelector("u")) throw new Error("не разбирается __подчёркивание__");
    if (!probe.querySelector("b")) throw new Error("не разбирается **жирный**");
    if (!probe.querySelector("i")) throw new Error("не разбирается //курсив//");
    if (/__|\*\*|\/\//.test(probe.textContent)) throw new Error("разметка осталась: " + probe.textContent);
  });

  win.UI.closeAllModals();
  await tick(320);

  // Настройки: изменение скорости меняет план.
  check("скорость чтения влияет на время", () => {
    const before = win.Views.plan().totals.minutesTotal;
    win.Store.state.settings.wordsPerMinute = 300;
    const after = win.Views.plan().totals.minutesTotal;
    win.Store.state.settings.wordsPerMinute = 150;
    if (!(after < before)) throw new Error("время не уменьшилось при большей скорости");
  });

  // Импорт через окно (диалог подменён на пустой список).
  win.App.openImport();
  await tick(60);
  check("окно импорта открывается", () => {
    const modal = win.document.querySelector("#modal-root .modal");
    if (!modal) throw new Error("окно импорта не открылось");
    if (!/Добавить файл/.test(modal.textContent)) throw new Error("нет заголовка импорта");
  });
  win.UI.closeAllModals();
  await tick(320);

  // Импорт папки: четыре файла должны по умолчанию стать ОДНОЙ дисциплиной.
  const folder = path.join(SANDBOX, "folder");
  win.App.importPaths([
    path.join(folder, "q001.txt"),
    path.join(folder, "q002.txt"),
    path.join(folder, "q003.txt"),
    path.join(folder, "q004.txt")
  ]);
  await tick(400);
  check("импорт папки предлагает одну общую дисциплину", () => {
    const modal = win.document.querySelector("#modal-root .modal");
    if (!modal) throw new Error("окно импорта не открылось");
    if (!/Одна дисциплина/.test(modal.textContent)) throw new Error("нет режима объединения: " + modal.textContent.slice(0, 200));
    const btn = Array.from(modal.querySelectorAll("button")).find((b) => /Добавить выбранные/.test(b.textContent));
    if (!btn) throw new Error("нет кнопки добавления");
  });

  // Проверяем саму логику слияния через Store — так же, как это делает кнопка.
  const mergeReads = [];
  for (let i = 1; i <= 4; i++) {
    mergeReads.push(await win.api.readFile(path.join(folder, "q00" + i + ".txt")));
  }
  check("объединение файлов даёт одну дисциплину со всеми вопросами", () => {
    const questions = [];
    for (const r of mergeReads) for (const q of r.parsed.questions) questions.push(q);
    questions.forEach((q, idx) => (q.num = idx + 1));
    win.Store.addDiscipline({
      id: "merged",
      name: "adp2",
      questions,
      parsing: { strategy: "merged", count: questions.length }
    });
    const added = win.Store.getDiscipline("merged");
    if (!added) throw new Error("дисциплина не добавилась");
    if (added.questions.length !== 4) throw new Error("вопросов: " + added.questions.length);
    if (added.questions[3].num !== 4) throw new Error("нумерация не пересчитана");
    if (!win.Views.plan().perDisc["merged"]) throw new Error("план для объединённой дисциплины не посчитан");
  });
  win.UI.closeAllModals();
  await tick(320);

  // Удаление дисциплины.
  check("удаление дисциплины работает", () => {
    const before = win.Store.activeDisciplines().length;
    const victim = win.Store.activeDisciplines()[1];
    win.Store.removeDiscipline(victim.id);
    const after = win.Store.activeDisciplines().length;
    if (after !== before - 1) throw new Error("количество не изменилось");
  });
  await tick(40);

  check("состояние сохраняется без ошибок", () => {
    const saved = getSaved();
    if (!saved) throw new Error("сохранение не вызывалось");
    if (!Array.isArray(saved.disciplines)) throw new Error("нет массива дисциплин");
  });

  // Проверим, что календарь и статистика не падают при пустой библиотеке.
  win.Store.state.disciplines.forEach((d) => win.Store.removeDiscipline(d.id));
  await tick(60);
  for (const screen of ["dashboard", "calendar", "stats", "today"]) {
    win.App.go(screen);
    await tick(30);
    check("пустая библиотека: экран «" + screen + "»", () => {
      const view = win.document.getElementById("view");
      if (/Не удалось показать/.test(view.textContent)) throw new Error(view.textContent.slice(0, 300));
    });
  }

  console.log("\n---");
  if (failures) {
    console.log("Провалено: " + failures + ", пройдено: " + passed);
    for (const e of errors) {
      console.log("\n[" + e.name + "]");
      console.log(e.err && e.err.stack ? e.err.stack.split("\n").slice(0, 6).join("\n") : e.err);
    }
    process.exitCode = 1;
  } else {
    console.log("Всё пройдено: " + passed + " проверок.");
  }

  // Интервалы приложения (автосохранение, тема) держат цикл событий — выходим явно.
  setTimeout(() => process.exit(failures ? 1 : 0), 50).unref();
  process.exit(failures ? 1 : 0);
}

run().catch((err) => {
  console.error("Сбой проверки:", err);
  process.exitCode = 1;
});
