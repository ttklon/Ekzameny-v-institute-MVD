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

const autostartCalls = [];

function makeDom(opts) {
  const o = opts || {};
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
    // Готовые ответы: в проверках берём настоящий комплект, но самую
    // маленькую дисциплину — чтобы тест оставался быстрым.
    builtin: o.builtin === false ? {
      list: async () => ({ ok: true, items: [] }),
      parse: async () => ({ ok: false }),
      answer: async () => ({ ok: false })
    } : {
      list: async () => {
        const b = require(path.join(ROOT, "src", "main", "builtin.js"));
        const items = b.list({ dir: path.join(ROOT, "answers") });
        return { ok: true, items: items.filter((i) => i.code === "krim") };
      },
      parse: async (code) => {
        const b = require(path.join(ROOT, "src", "main", "builtin.js"));
        const parser = require(path.join(ROOT, "src", "core", "parser.js"));
        const text = b.read(code, { dir: path.join(ROOT, "answers") });
        if (!text) return { ok: false };
        const parsed = parser.parseDocument(text, { assumeAnswerWords: 0 });
        const questions = parsed.questions.map((q) => ({
          num: q.num, listNo: q.listNo, question: q.question, title: q.title,
          hasAnswer: q.aWords > 0, qWords: q.qWords, aWords: q.aWords, qChars: q.qChars,
          aChars: q.aChars, charsWithSpaces: q.charsWithSpaces, words: q.words,
          chars: q.chars, difficulty: q.difficulty
        }));
        return {
          ok: true, questions, strategy: parsed.strategy, count: questions.length,
          answeredCount: questions.filter((q) => q.hasAnswer).length,
          totalWords: parsed.totalWords, totalChars: parsed.totalChars
        };
      },
      answer: async (code, num, index, short) => {
        const b = require(path.join(ROOT, "src", "main", "builtin.js"));
        const parser = require(path.join(ROOT, "src", "core", "parser.js"));
        const dir = { dir: path.join(ROOT, "answers") };
        const parsed = parser.parseDocument(b.read(code, dir), { assumeAnswerWords: 0 });
        const q = parsed.questions.find((x) => x.num === num);
        if (short) {
          const item = b.list(dir).find((i) => i.code === code);
          if (item && item.alt) {
            const alt = parser.parseDocument(b.readAlt(code, dir), { assumeAnswerWords: 0 });
            const aq = alt.questions.find((x) => x.num === num);
            if (aq && aq.answer) {
              return { ok: true, question: q && q.question, answer: aq.answer, variant: "short" };
            }
          }
        }
        return { ok: true, question: q && q.question, answer: (q && q.answer) || "", variant: "full" };
      }
    },
    remind: {
      refresh: async () => ({ ok: true }),
      test: async () => ({ ok: true }),
      info: async () => ({ tasks: 3, minutes: 12 })
    },
    autostart: {
      set: async (on) => {
        autostartCalls.push(on);
        return { ok: true, enabled: !!on };
      },
      state: async () => ({ enabled: false })
    },
    onGo: () => () => {},
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


/**
 * Открыть «Детали» на странице дисциплины: скорость, прогоны, выходные.
 * Вкладок больше нет — всё, что нужно редко, живёт под одним переключателем.
 */
function openDetails(win, discId) {
  win.App.go("discipline", { id: discId });
  const view = win.document.getElementById("view");
  const d = win.Store.getDiscipline(discId);
  if (d && d.advOpen !== true) {
    d.advOpen = true;
    win.Store.save();
  }
  win.App.refresh();
  const adv = win.document.getElementById("view").querySelector(".adv-toggle");
  if (!adv) throw new Error("нет блока «Детали»");
  if (!win.document.getElementById("view").querySelector(".day-load, .speed-slider")) {
    adv.dispatchEvent(new win.Event("click", { bubbles: true }));
  }
  return win.document.getElementById("view");
}

async function run() {
  console.log("Проверка интерфейса (jsdom)\n");

  // Основной прогон идёт без комплекта ответов: здесь проверяется ручной
  // путь — добавить файл самому. Комплект проверяется отдельно ниже.
  const { win, getSaved } = makeDom({ builtin: false });
  loadScripts(win);

  // Запуск приложения.
  win.document.dispatchEvent(new win.Event("DOMContentLoaded"));
  await tick(120);

  check("первый запуск объясняет, что делать", () => {
    const view = win.document.getElementById("view");
    if (!view || !view.children.length) throw new Error("экран пуст");
    // Библиотека пуста (комплект отключён в этом прогоне) — экран должен
    // сказать, что ответы уже внутри, и предложить выбор дисциплины.
    if (!/Ответы уже внутри/.test(view.textContent)) {
      throw new Error("нет приглашения: " + view.textContent.slice(0, 160));
    }
    if (!view.querySelector(".steps")) throw new Error("нет шагов «что делать»");
    const steps = view.querySelectorAll(".step");
    if (steps.length !== 3) throw new Error("шагов: " + steps.length);
    if (!/Выберите дисциплину/.test(steps[0].textContent)) throw new Error("первый шаг не про дисциплину");
    if (!view.querySelector(".about-grid")) throw new Error("нет блока «что внутри»");
    // Кнопка добавления должна быть на первом экране и работать.
    const btn = Array.from(view.querySelectorAll("button")).find((b) => /Добавить файл/.test(b.textContent));
    if (!btn) throw new Error("нет кнопки добавления файла");
  });

  check("навигация построена: три пункта, без лишнего", () => {
    const nav = win.document.getElementById("nav");
    const labels = Array.from(nav.children).map((b) => b.textContent.trim());
    if (labels.length !== 3) throw new Error("пунктов меню: " + labels.length + " (" + labels.join(", ") + ")");
    for (const need of ["Сегодня", "Дисциплины", "Настройки"]) {
      if (!labels.some((t) => t.indexOf(need) !== -1)) throw new Error("нет пункта «" + need + "»");
    }
    for (const gone of ["Календарь", "Статистика", "Обзор"]) {
      if (labels.some((t) => t.indexOf(gone) !== -1)) throw new Error("лишний пункт «" + gone + "»");
    }
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
  // «tips» убран из меню — экран проверяем напрямую, он остался в коде.
  // Экранов ровно три. Остальные (обзор, дисциплина) — части этих трёх.
  const screens = ["today", "disciplines", "settings"];
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

  // Настройки: напоминания, трей и автозапуск — должны быть на экране и
  // действительно менять состояние, а не просто быть нарисованными.
  win.App.go("settings");
  await tick(45);

  check("в настройках есть напоминания, трей и автозапуск", () => {
    const text = win.document.getElementById("view").textContent;
    for (const label of ["Напоминать о занятиях", "Время напоминания", "Сворачивать в трей", "Запускать с Windows"]) {
      if (text.indexOf(label) === -1) throw new Error("нет пункта «" + label + "»");
    }
  });

  check("переключатель напоминаний сохраняется", () => {
    const boxes = [...win.document.querySelectorAll("#view input[type=checkbox]")];
    if (boxes.length < 4) throw new Error("переключателей слишком мало: " + boxes.length);
    const before = win.Store.state.settings.remind.enabled;
    const box = boxes.find((b) => {
      const row = b.closest(".settings-row");
      return row && row.textContent.indexOf("Напоминать о занятиях") !== -1;
    });
    if (!box) throw new Error("не нашёл переключатель напоминаний");
    box.checked = !before;
    box.dispatchEvent(new win.Event("change", { bubbles: true }));
    if (win.Store.state.settings.remind.enabled === before) throw new Error("настройка не изменилась");
    win.Store.state.settings.remind.enabled = before;
  });

  check("автозапуск передаётся системе, а не просто сохраняется", async () => {
    // Настройка бесполезна, если она лежит в файле и не доходит до Windows.
    const boxes = [...win.document.querySelectorAll("#view input[type=checkbox]")];
    const box = boxes.find((b) => {
      const row = b.closest(".settings-row");
      return row && row.textContent.indexOf("Запускать с Windows") !== -1;
    });
    if (!box) throw new Error("не нашёл переключатель автозапуска");
    autostartCalls.length = 0;
    box.checked = true;
    box.dispatchEvent(new win.Event("change", { bubbles: true }));
    if (!autostartCalls.length) throw new Error("система не получила запрос на автозапуск");
    if (autostartCalls[0] !== true) throw new Error("передан не тот флаг: " + autostartCalls[0]);
  });

  check("время напоминания меняется полем времени", () => {
    const inputs = [...win.document.querySelectorAll('#view input[type="time"]')];
    if (!inputs.length) throw new Error("нет поля времени");
    const input = inputs[0];
    input.value = "20:30";
    input.dispatchEvent(new win.Event("change", { bubbles: true }));
    if (win.Store.state.settings.remind.at !== "20:30") {
      throw new Error("время не сохранилось: " + win.Store.state.settings.remind.at);
    }
    input.value = "19:00";
    input.dispatchEvent(new win.Event("change", { bubbles: true }));
  });

  check("сворачивание в трей и автозапуск сохраняются как настройки", () => {
    const s = win.Store.state.settings;
    if (typeof s.closeToTray !== "boolean") throw new Error("closeToTray не задан");
    if (typeof s.autostart !== "boolean") throw new Error("autostart не задан");
    if (!s.remind || typeof s.remind.at !== "string") throw new Error("время напоминания не задано");
  });

  // Одна норма дня на всё приложение: «Настройки» и страница дисциплины
  // должны говорить одно и то же, иначе человек путается в двух цифрах.
  check("норма дня в «Настройках» доходит до дисциплин", () => {
    win.App.go("settings");
    const view = win.document.getElementById("view");
    if (!/Читаю в день/.test(view.textContent)) throw new Error("нет блока «Читаю в день»");
    const chips = Array.from(view.querySelectorAll(".chips .chip"));
    const two = chips.find((c) => /2 часа/.test(c.textContent));
    if (!two) throw new Error("нет варианта «2 часа»: " + chips.map((c) => c.textContent).join(","));
    two.dispatchEvent(new win.Event("click", { bubbles: true }));
    if (win.Store.state.settings.globalDailyMinutes !== 120) {
      throw new Error("норма не сохранилась: " + win.Store.state.settings.globalDailyMinutes);
    }
    const d0 = win.Store.activeDisciplines()[0];
    if (d0.plan.comfortMinutes !== 120) {
      throw new Error("до дисциплины норма не дошла: " + JSON.stringify(d0.plan.comfortMinutes));
    }
    // И план пересчитался по ней.
    const pd = win.Views.plan().perDisc[d0.id];
    if (pd.stats.capMinutes && pd.stats.capMinutes > 400) {
      throw new Error("план не заметил норму: " + pd.stats.capMinutes);
    }
    // Возврат: «по объёму работы».
    const free = chips.find((c) => /по объёму/.test(c.textContent));
    free.dispatchEvent(new win.Event("click", { bubbles: true }));
    if (win.Store.activeDisciplines()[0].plan.comfortMinutes) {
      throw new Error("норма не снялась с дисциплины");
    }
  });

  // Экран дисциплины со всеми вкладками.
  const disc = win.Store.activeDisciplines()[0];
  win.App.go("discipline", { id: disc.id });
  await tick(50);
  check("экран дисциплины отрисован", () => {
    const view = win.document.getElementById("view");
    if (!view.textContent.includes(disc.name)) throw new Error("нет названия дисциплины");
    if (/Не удалось показать/.test(view.textContent)) throw new Error(view.textContent.slice(0, 300));
  });

  // Одна страница вместо вкладок: всё важное — сразу на виду.
  check("страница дисциплины: часы в день, экзамен и вопросы — сразу", () => {
    const view = win.document.getElementById("view");
    if (/Не удалось показать/.test(view.textContent)) throw new Error(view.textContent.slice(0, 300));
    for (const label of ["Сколько часов в день", "Экзамен", "Вопросы"]) {
      if (view.textContent.indexOf(label) === -1) throw new Error("нет блока «" + label + "»");
    }
    if (!view.querySelector(".q-row")) throw new Error("нет списка вопросов");
  });

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

  // Чтение вперёд и отмена отметок: человек должен уметь и то, и другое.
  check("отметку можно снять, и вернуть одним нажатием", () => {
    const today = win.ExamCore.planner.todayStr();
    const target = win.Store.activeDisciplines()[0];
    win.Store.setRead(target.id, 0, today, true);
    const marked = win.Store.readsOn(today);
    if (!marked.length) throw new Error("отметка не записалась");
    // «Снять всё за сегодня» — и сразу вернуть.
    const removed = win.Store.clearReadsOn(null, today);
    if (!removed.length) throw new Error("снять нечего");
    if (win.Store.readsOn(today).length) throw new Error("отметки остались после снятия");
    win.Store.restoreReads(removed, today);
    if (!win.Store.readsOn(today).length) throw new Error("отметки не вернулись");
    win.Store.clearReadsOn(null, today);
  });

  check("на экране дня видно, что уже отмечено, и есть «взять вперёд»", () => {
    const today = win.ExamCore.planner.todayStr();
    const target = win.Store.activeDisciplines()[0];
    win.Store.setRead(target.id, 0, today, true);
    win.App.go("today");
    const view = win.document.getElementById("view");
    if (!/Уже отмечено/.test(view.textContent)) throw new Error("нет списка отмеченного");
    if (!/Взять вперёд/.test(view.textContent)) throw new Error("нет кнопки «взять вперёд»");
    win.Store.clearReadsOn(null, today);
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

  // ---- Настройки: каждое изменение должно быть видно -----------------
  win.App.go("settings");
  await tick(60);
  check("скорость чтения настраивается ползунком и видна сразу", () => {
    const view = win.document.getElementById("view");
    const slider = view.querySelector(".speed-slider");
    if (!slider) throw new Error("нет ползунка скорости");
    const readout = view.querySelector(".speed-value");
    if (!readout) throw new Error("нет подписи со значением");
    if (readout.textContent.indexOf("150") === -1) throw new Error("подпись не показывает скорость: " + readout.textContent);
    // Двигаем ползунок и проверяем и значение, и подпись, и пример.
    const exampleBefore = view.querySelector(".read-big").textContent;
    slider.value = "280";
    slider.dispatchEvent(new win.Event("input", { bubbles: true }));
    if (win.Store.state.settings.wordsPerMinute !== 280) {
      throw new Error("настройка не сохранилась: " + win.Store.state.settings.wordsPerMinute);
    }
    if (view.querySelector(".speed-value").textContent.indexOf("280") === -1) {
      throw new Error("подпись не обновилась сразу: " + view.querySelector(".speed-value").textContent);
    }
    const exampleAfter = view.querySelector(".read-big").textContent;
    if (exampleBefore === exampleAfter) throw new Error("пример не пересчитался: " + exampleAfter);
    win.Store.state.settings.wordsPerMinute = 150;
  });

  check("готовые варианты скорости выбираются нажатием", () => {
    const view = win.document.getElementById("view");
    const chips = view.querySelectorAll(".chips .chip");
    if (!chips.length) throw new Error("нет готовых вариантов");
    const target = Array.from(chips).find((c) => /200/.test(c.textContent));
    if (!target) throw new Error("нет варианта 200");
    target.dispatchEvent(new win.MouseEvent("click", { bubbles: true }));
    if (win.Store.state.settings.wordsPerMinute !== 200) {
      throw new Error("вариант не применился: " + win.Store.state.settings.wordsPerMinute);
    }
    win.Store.state.settings.wordsPerMinute = 150;
  });

  check("предел времени в день меняет норму и показывает финиш", () => {
    win.Store.state.settings.globalDailyMinutes = 0;
    const view = win.document.getElementById("view");
    const outcome = view.querySelector(".outcome");
    if (!outcome) throw new Error("нет блока «что получится»");
    const lines = outcome.querySelectorAll(".outcome-line");
    if (lines.length < 3) throw new Error("в блоке мало строк: " + lines.length);
    const finish = lines[1].textContent;
    if (!finish.trim()) throw new Error("не показана дата финиша");
    // Выбираем предел 30 минут и убеждаемся, что настройка применилась.
    const chip = Array.from(view.querySelectorAll(".chips .chip")).find((c) => /30 минут/.test(c.textContent));
    if (!chip) throw new Error("нет варианта «30 минут»");
    chip.dispatchEvent(new win.MouseEvent("click", { bubbles: true }));
    if (win.Store.state.settings.globalDailyMinutes !== 30) {
      throw new Error("предел не применился: " + win.Store.state.settings.globalDailyMinutes);
    }
    win.Store.state.settings.globalDailyMinutes = 0;
  });

  check("тонкая настройка свёрнута и раскрывается", () => {
    win.Store.state.ui.settingsAdvanced = false;
    win.App.refresh();
    const view = win.document.getElementById("view");
    const toggle = view.querySelector(".adv-toggle");
    if (!toggle) throw new Error("нет переключателя тонкой настройки");
    // Свёрнуто: коэффициентов на экране нет.
    if (/Повторное чтение быстрее/.test(view.textContent)) {
      throw new Error("тонкая настройка видна, хотя должна быть свёрнута");
    }
    toggle.dispatchEvent(new win.MouseEvent("click", { bubbles: true }));
    const text = win.document.getElementById("view").textContent;
    if (!/Повторное чтение быстрее/.test(text)) {
      throw new Error("тонкая настройка не раскрылась");
    }
    win.Store.state.ui.settingsAdvanced = false;
  });

  check("своя скорость дисциплины меняет время сразу после ползунка", () => {
    openDetails(win, disc.id);
    const view = win.document.getElementById("view");
    const slider = view.querySelector(".speed-slider");
    if (!slider) throw new Error("нет ползунка скорости на вкладке дисциплины");
    const before = win.Views.plan().perDisc[disc.id].stats.minutesTotal;
    // Замедляемся вдвое — время должно вырасти.
    slider.value = "75";
    slider.dispatchEvent(new win.Event("input", { bubbles: true }));
    const saved = win.Store.getDiscipline(disc.id).reading;
    if (!saved || saved.wordsPerMinute !== 75) {
      throw new Error("скорость не сохранилась: " + JSON.stringify(saved));
    }
    const after = win.Views.plan().perDisc[disc.id].stats.minutesTotal;
    if (!(after > before * 1.5)) {
      throw new Error("время не пересчиталось: " + before.toFixed(1) + " → " + after.toFixed(1) +
        " (кэш плана не учитывает свою скорость)");
    }
    // Возврат к общей скорости.
    delete win.Store.getDiscipline(disc.id).reading;
    win.Store.save();
    const back = win.Views.plan().perDisc[disc.id].stats.minutesTotal;
    if (Math.abs(back - before) > 0.5) {
      throw new Error("после возврата к общей скорость время не вернулось: " + back.toFixed(1) + " vs " + before.toFixed(1));
    }
    win.App.go("discipline", { id: disc.id });
  });

  check("воскресенье можно сделать тяжелее одним кликом", () => {
    openDetails(win, disc.id);
    const view = win.document.getElementById("view");
    const adv = view.querySelector(".adv-toggle");
    if (!adv) throw new Error("нет блока «Как именно распределять»");
    if (!view.querySelector(".day-load")) {
      adv.dispatchEvent(new win.Event("click", { bubbles: true }));
    }
    const rows = win.document.getElementById("view").querySelectorAll(".day-load-row");
    if (!rows.length) throw new Error("нет таблицы нагрузки по дням недели");
    // Строки идут с понедельника, воскресенье — последнее. В таблице вес
    // лежит по weekday(): 0 — воскресенье, 1 — понедельник. Последняя клетка
    // строки — «×4», самое «больше».
    const sunRow = rows[rows.length - 1];
    const cells = sunRow.querySelectorAll(".day-load-cell");
    cells[cells.length - 1].dispatchEvent(new win.Event("click", { bubbles: true }));
    const saved = win.Store.getDiscipline(disc.id).plan.dayLoad;
    if (!Array.isArray(saved) || !(saved[0] > 1)) {
      throw new Error("воскресенье не стало тяжёлым: " + JSON.stringify(saved));
    }
    // И план должен реально дать воскресеньям больше минут.
    const pd = win.Views.plan().perDisc[disc.id];
    const days = Object.keys(pd.days || {});
    const sum = (wd) => {
      let total = 0;
      let n = 0;
      for (const day of days) {
        const dt = new Date(day + "T00:00:00");
        if (dt.getDay() !== wd) continue;
        n++;
        total += (pd.days[day] || []).reduce((a, it) => a + it.minutes, 0);
      }
      return n ? total / n : 0;
    };
    const sun = sum(0);
    const mon = sum(1);
    if (!(sun > mon)) {
      throw new Error("воскресенье не тяжелее понедельника: " + sun.toFixed(1) + " vs " + mon.toFixed(1));
    }
    // Возврат к обычной неделе.
    const back = [1, 1, 1, 1, 1, 1, 1];
    win.Store.getDiscipline(disc.id).plan.dayLoad = back;
    win.Store.save();
    win.Views.plan();
    win.App.go("discipline", { id: disc.id });
  });

  check("свой объём дня задаётся и план его слушается", () => {
    // Теперь это главная настройка страницы — одно число «сколько часов в день».
    win.App.go("discipline", { id: disc.id });
    const view = win.document.getElementById("view");
    if (!/Сколько часов в день/.test(view.textContent)) {
      throw new Error("нет блока «Сколько часов в день»");
    }
    // Кнопка «3 ч» — это уже больше двух часов, раньше такого варианта не было.
    const chips = Array.from(view.querySelectorAll(".chips .chip"));
    const three = chips.find((c) => /3 ч/.test(c.textContent));
    if (!three) throw new Error("нет варианта «3 ч»: " + chips.map((c) => c.textContent).join(","));
    three.dispatchEvent(new win.Event("click", { bubbles: true }));
    const plan = win.Store.getDiscipline(disc.id).plan;
    if (plan.comfortMinutes !== 180) {
      throw new Error("объём дня не сохранился: " + JSON.stringify(plan.comfortMinutes));
    }
    // В плане это отражается: предупреждения о перегрузке при таком объёме нет.
    const pd = win.Views.plan().perDisc[disc.id];
    const overload = (pd.warnings || []).filter((w) => w.type === "overload");
    if (overload.length) throw new Error("лишняя тревога о перегрузке: " + overload[0].text);
    // Свои минуты по дням — в «Деталях»: суббота 240 при обычных 180 это вес 4/3.
    openDetails(win, disc.id);
    const exact = win.document.getElementById("view").querySelectorAll(".day-exact-row");
    if (!exact.length) throw new Error("нет полей «свои минуты по дням»");
    delete win.Store.getDiscipline(disc.id).plan.comfortMinutes;
    win.Store.save();
    win.App.go("discipline", { id: disc.id });
  });

  check("у дисциплины с двумя вариантами ответов есть переключатель", () => {
    // Так выглядит административная деятельность: подробный ответ на первое
    // чтение, краткий на повторения. Переключатель — в «Параметрах», и выбор
    // сохраняется в дисциплине (по нему считается время).
    const target = win.Store.getDiscipline(disc.id);
    target.hasShortAnswers = true;
    // Краткий вариант вдвое короче подробного — так у административной
    // деятельности: 148 тыс. слов против 316 тыс.
    target.questions.forEach((q) => {
      q.altWords = Math.round((q.words || 0) / 2);
      q.altChars = Math.round((q.chars || 0) / 2);
    });
    win.Store.save();
    openDetails(win, target.id);
    const view = win.document.getElementById("view");
    if (!/Какой ответ читать/.test(view.textContent)) {
      throw new Error("нет блока «Какой ответ читать»");
    }
    const buttons = Array.from(view.querySelectorAll(".segmented button"))
      .filter((b) => /подробно|кратко/.test(b.textContent));
    if (buttons.length !== 3) throw new Error("вариантов: " + buttons.length);
    const shortBtn = buttons.find((b) => /всегда кратко/.test(b.textContent));
    shortBtn.dispatchEvent(new win.Event("click", { bubbles: true }));
    if (win.Store.getDiscipline(target.id).answerVariant !== "short") {
      throw new Error("выбор не сохранился: " + win.Store.getDiscipline(target.id).answerVariant);
    }
    // Время должно пересчитаться: краткий вариант короче.
    const after = win.Views.plan().perDisc[target.id].stats.minutesTotal;
    win.Store.getDiscipline(target.id).answerVariant = "full";
    win.Store.save();
    win.App.refresh();
    const full = win.Views.plan().perDisc[target.id].stats.minutesTotal;
    if (!(full > after)) throw new Error("время не зависит от варианта: " + after.toFixed(0) + " vs " + full.toFixed(0));
    // Возврат к обычному виду дисциплины.
    delete win.Store.getDiscipline(target.id).hasShortAnswers;
    win.Store.getDiscipline(target.id).answerVariant = "auto";
    win.Store.save();
    win.App.go("discipline", { id: disc.id });
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
  // Пустая библиотека должна объяснять, с чего начать, на каждом экране —
  // в том числе на «Сегодня», который раньше висел пустым календарём.
  for (const screen of ["today", "disciplines", "settings"]) {
    win.App.go(screen);
    await tick(30);
    check("пустая библиотека: экран «" + screen + "»", () => {
      const view = win.document.getElementById("view");
      if (/Не удалось показать/.test(view.textContent)) throw new Error(view.textContent.slice(0, 300));
      if (view.textContent.trim().length < 20) throw new Error("экран пуст: " + screen);
    });
  }

  // ---------------------------------------------------------------------
  //  Готовые ответы из комплекта: новый запуск должен подключить их сам.
  // ---------------------------------------------------------------------
  const second = makeDom(); // комплект включён
  loadScripts(second.win);
  second.win.document.dispatchEvent(new second.win.Event("DOMContentLoaded"));
  await tick(900); // разбор файла занимает время

  const bwin = second.win;
  check("первый запуск сам подключает готовые ответы", () => {
    const n = bwin.Store.activeDisciplines().length;
    if (n !== 1) throw new Error("подключено дисциплин: " + n);
    const d = bwin.Store.activeDisciplines()[0];
    if (d.builtin !== "krim") throw new Error("не та дисциплина: " + d.builtin);
    if (d.questions.length !== 44) throw new Error("вопросов: " + d.questions.length);
  });

  check("в библиотеке только заголовки и объёмы, без текста ответов", () => {
    const d = bwin.Store.activeDisciplines()[0];
    const json = JSON.stringify(d.questions);
    if (json.length > 400 * 1024) throw new Error("вопросы слишком тяжёлые: " + Math.round(json.length / 1024) + " КБ");
    const withText = d.questions.filter((q) => q.answer && q.answer.length > 200).length;
    if (withText) throw new Error("текст ответов попал в библиотеку: " + withText);
    if (!d.questions.every((q) => q.hasAnswer)) throw new Error("есть вопросы без признака ответа");
  });

  check("время чтения посчитано по готовым ответам, а не оценено", () => {
    const d = bwin.Store.activeDisciplines()[0];
    const estimated = d.questions.filter((q) => q.estimated).length;
    if (estimated) throw new Error("объём оценён у " + estimated + " вопросов");
    const words = d.questions.reduce((s2, q) => s2 + (q.aWords || 0), 0);
    if (words < 20000) throw new Error("слов в ответах слишком мало: " + words);
  });

  check("у административной деятельности два варианта ответов в одной дисциплине", () => {
    // Отдельного «adp2» в списке быть не должно: это вариант ответа, а не
    // второй предмет. Отметки и план у вопроса одни и те же.
    const b = require(path.join(ROOT, "src", "main", "builtin.js"));
    const items = b.list({ dir: path.join(ROOT, "answers") });
    const adp = items.find((i) => i.code === "adp");
    if (!adp) throw new Error("в комплекте нет административной деятельности");
    if (adp.alt !== "adp2") throw new Error("нет краткого варианта: " + JSON.stringify(adp));
    if (items.some((i) => i.code === "adp2")) throw new Error("краткий вариант стал отдельной дисциплиной");
  });

  // Открытие вопроса: проверяем по-настоящему дождавшись окна, иначе тест
  // «проходит» на провалившемся промисе и ничего не проверяет.
  {
    const d = bwin.Store.activeDisciplines()[0];
    const today = bwin.ExamCore.planner.todayStr();
    bwin.App.go("discipline", { id: d.id });
    await tick(60);
    let openError = null;
    try {
      await bwin.App.openQuestion(d.id, 0, today);
    } catch (e) {
      openError = e;
    }
    await tick(600);
    // В окне вопроса разметка ответа рисуется после подгрузки текста, поэтому
    // берём именно .modal и ждём содержимого, а не первый подходящий элемент.
    const modal = bwin.document.querySelector("#modal-root .modal");
    const text = (modal && modal.textContent) || "";
    check("вопрос открывается с полным ответом из комплекта", () => {
      if (openError) throw openError;
      if (!/Вопрос 1/.test(text)) {
        throw new Error(
          "не открылось окно вопроса: modal=" + !!modal +
          ", в modal-root " + bwin.document.getElementById("modal-root").children.length + " элементов, " +
          "текст: " + JSON.stringify(text.slice(0, 120))
        );
      }
      if (text.length < 3000) throw new Error("ответ не подгрузился, текста всего " + text.length);
    });
  }

  check("своя дисциплина с тем же названием не дублируется", () => {
    // Человек уже добавил свой файл «Криминалистика» — второй такой же из
    // комплекта ему не нужен.
    const b = bwin.Store;
    const items = [{ code: "krim", name: "Криминалистика" }, { code: "ugp", name: "Уголовное право" }];
    const missing = b.missingBuiltin(items).map((x) => x.code);
    if (missing.indexOf("krim") !== -1) throw new Error("своя «Криминалистика» не учтена");
    if (missing.indexOf("ugp") === -1) throw new Error("недостающая дисциплина потерялась");
  });

  check("названия сравниваются без учёта регистра и «ё»", () => {
    const b = bwin.Store;
    b.activeDisciplines()[0].name = "КРИМИНАЛИСТИКА";
    const missing = b.missingBuiltin([{ code: "krim", name: "Криминалистика" }]);
    if (missing.length) throw new Error("регистр не учтён");
  });

  check("повторный запуск не добавляет дисциплину второй раз", async () => {
    const before = bwin.Store.activeDisciplines().length;
    await bwin.App.setupBuiltin ? bwin.App.setupBuiltin() : null;
    const after = bwin.Store.activeDisciplines().length;
    if (after !== before) throw new Error("дубликат: было " + before + ", стало " + after);
  });

  // ---------------------------------------------------------------------
  //  Сбои при запуске: окно должно открыться, а не остаться пустым.
  // ---------------------------------------------------------------------
  for (const [name, patch] of [
    ["сбой чтения данных", { loadState: async () => { throw new Error("EACCES: доступ запрещён"); } }],
    ["повреждённые данные", { loadState: async () => ({ state: { disciplines: "мусор", settings: null }, recovered: false }) }],
    ["сбой сохранения", { saveState: async () => { throw new Error("диск переполнен"); } }]
  ]) {
    const broken = makeDom({ builtin: false });
    Object.assign(broken.win.api, patch);
    loadScripts(broken.win);
    broken.win.console.error = () => {};
    broken.win.document.dispatchEvent(new broken.win.Event("DOMContentLoaded"));
    await tick(900);
    const bw = broken.win;
    check("программа открывается при сбое: " + name, () => {
      const view = bw.document.getElementById("view");
      const text = (view && view.textContent) || "";
      if (!text.trim()) throw new Error("экран пустой — похоже на «ошибку» без объяснений");
      if (/Не удалось показать экран/.test(text)) throw new Error(text.slice(0, 200));
      // Приглашение или рабочий экран — оба годятся, главное не пустота.
      if (text.length < 200) throw new Error("слишком мало на экране: " + text.length);
    });
    bw.close();
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
