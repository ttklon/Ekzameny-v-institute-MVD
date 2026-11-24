/*
 * dom.test.js — headless «прокурка» интерфейса через jsdom.
 * Грузит реальные renderer-скрипты, заглушает API Electron и проходит по всем экранам,
 * импортирует настоящий файл из репозитория, открывает дисциплину и отмечает прогресс.
 */
const fs = require("fs");
const path = require("path");
const { JSDOM } = require("jsdom");

const ROOT = path.resolve(__dirname, "..", "..");
const APP = path.resolve(__dirname, "..");
const repoFile = path.join(ROOT, "Примерный перечень вопросов к экзамену по административной деятельности полиции России.txt");

const errors = [];

// --- Заглушки браузерных API ---
const fakeCtx = new Proxy(
  {},
  {
    get(t, p) {
      if (p === "createRadialGradient" || p === "createLinearGradient")
        return () => ({ addColorStop() {} });
      if (p === "canvas") return { width: 0, height: 0 };
      return () => {};
    },
    set() {
      return true;
    }
  }
);

const audioStub = {
  currentTime: 0,
  state: "running",
  destination: {},
  resume() {},
  createOscillator() {
    return { type: "", frequency: { value: 0 }, connect() { return this; }, start() {}, stop() {} };
  },
  createGain() {
    return { gain: { setValueAtTime() {}, linearRampToValueAtTime() {}, exponentialRampToValueAtTime() {} }, connect() { return this; } };
  }
};

const html = fs.readFileSync(path.join(APP, "renderer", "index.html"), "utf-8");
const dom = new JSDOM(html, { runScripts: "outside-only", pretendToBeVisual: true });
const { window } = dom;

window.matchMedia = () => ({ matches: false, addEventListener() {}, addListener() {} });
window.requestAnimationFrame = () => 0;
window.cancelAnimationFrame = () => {};
window.AudioContext = function () { return audioStub; };
window.HTMLCanvasElement.prototype.getContext = () => fakeCtx;
window.onerror = (msg) => errors.push("window.onerror: " + msg);

// --- Данные: реальный файл → дисциплина ---
const buf = fs.readFileSync(repoFile);
const text = buf.toString("utf-8");

function buildState() {
  const C = window.ExamCore;
  const P = C.planner;
  const today = P.fmtDate(new Date());
  const parsed = C.parser.parseDocument(text, { unit: "wpm", rate: 250, assumeAnswerWords: 200 });
  const disc = {
    id: "d1",
    name: "Административная деятельность полиции",
    color: "#6db3f2",
    icon: "⚖️",
    questions: parsed.questions,
    plan: {
      startDate: today,
      examDate: P.addDays(today, 30),
      passes: 3,
      mode: "questions",
      perDayQuestions: 10,
      perDayMinutes: 20,
      assumeAnswerWords: 200,
      restDays: [],
      reviewSpeedFactor: 1.3
    },
    progress: {},
    importedAt: new Date().toISOString()
  };
  return {
    version: 1,
    settings: {
      speedUnit: "wpm",
      wordsPerMinute: 250,
      charsPerMinute: 1500,
      restDays: [],
      soundEnabled: true,
      global: { dailyMinutes: 60 }
    },
    disciplines: [disc]
  };
}

const sample = null; // заполняется после загрузки ядра

window.api = {
  loadState: () => Promise.resolve(sample),
  saveState: () => Promise.resolve({ ok: true }),
  openFiles: () => Promise.resolve([]),
  readFile: (p) =>
    Promise.resolve({ ok: true, name: path.basename(p), path: p, size: buf.length, text }),
  getVersion: () => Promise.resolve("1.0.0")
};

function evalFile(rel) {
  const code = fs.readFileSync(path.join(APP, rel), "utf-8");
  window.eval(code);
}

function click(sel) {
  const el = window.document.querySelector(sel);
  if (!el) throw new Error("не найден элемент: " + sel);
  el.click();
}
function navTo(v) {
  click(`.nav-item[data-view="${v}"]`);
}

(async () => {
  try {
    evalFile("src/core/textstats.js");
    evalFile("src/core/parser.js");
    evalFile("src/core/planner.js");
    window.api.loadState = () => Promise.resolve(buildState());
    evalFile("renderer/js/audio.js");
    evalFile("renderer/js/clouds.js");
    evalFile("renderer/js/app.js"); // вызывает boot() в конце
    await new Promise((r) => setTimeout(r, 60)); // дать boot() отработать

    const expect = (cond, msg) => {
      if (!cond) errors.push("ASSERT: " + msg);
    };

    // 1. Обзор отрисовался, есть карточка дисциплины
    expect(window.document.querySelector("#view .card"), "dashboard: нет карточек");
    expect(window.document.querySelector("[data-disc]"), "dashboard: нет карточки дисциплины");

    // 2. Проходим по всем экранам
    for (const v of ["import", "disciplines", "today", "stats", "tips", "settings", "dashboard"]) {
      navTo(v);
      await new Promise((r) => setTimeout(r, 5));
      expect(window.document.querySelector("#view"), "view пуст после " + v);
    }

    // 3. Деталь дисциплины
    navTo("disciplines");
    await new Promise((r) => setTimeout(r, 5));
    click("[data-disc]");
    await new Promise((r) => setTimeout(r, 10));
    expect(window.document.querySelector("[data-qtoggle]"), "нет списка вопросов в детали");
    expect(window.document.querySelector("#f_passes"), "нет поля прогонов в детали");

    // 4. Отмечаем один вопрос (все прогоны)
    const qBefore = window.document.querySelectorAll("[data-qtoggle].done").length;
    click("[data-qtoggle]");
    await new Promise((r) => setTimeout(r, 10));
    const qAfter = window.document.querySelectorAll("[data-qtoggle].done").length;
    expect(qAfter === qBefore + 1, "после отметки вопроса число done не выросло");

    // 5. Сегодня: отмечаем задачу
    navTo("today");
    await new Promise((r) => setTimeout(r, 10));
    const task = window.document.querySelector(".task-item");
    expect(task, "нет задач на сегодня");
    if (task) {
      task.click();
      await new Promise((r) => setTimeout(r, 10));
    }

    // 6. Настройки: меняем скорость
    navTo("settings");
    await new Promise((r) => setTimeout(r, 5));
    const rate = window.document.querySelector("#s_rate");
    expect(rate, "нет поля скорости в настройках");
    if (rate) {
      rate.value = "300";
      rate.dispatchEvent(new window.Event("change"));
      await new Promise((r) => setTimeout(r, 10));
    }

    // 7. Импорт: реальный путь dropzone → парсинг → превью → добавление
    navTo("import");
    await new Promise((r) => setTimeout(r, 5));
    expect(window.document.querySelector("#drop"), "нет dropzone в импорте");
    window.api.openFiles = () => Promise.resolve([repoFile]); // заглушаем выбор файла
    window.document.querySelector("#drop").click();
    await new Promise((r) => setTimeout(r, 150)); // ingestPaths асинхронный
    expect(window.document.querySelector("[data-add]"), "после импорта нет превью для добавления");
    click("[data-add='0']");
    await new Promise((r) => setTimeout(r, 20));
    navTo("disciplines");
    await new Promise((r) => setTimeout(r, 10));
    const cards = window.document.querySelectorAll("[data-disc]").length;
    expect(cards >= 2, "после импорта не добавилась дисциплина (карточек: " + cards + ")");

    if (errors.length) {
      console.log("❌ ОШИБКИ (" + errors.length + "):");
      errors.forEach((e) => console.log("  - " + e));
      process.exit(1);
    } else {
      console.log("✅ DOM-прокурка пройдена: все экраны рендерятся, импорт/деталь/отметка прогресса работают.");
      process.exit(0);
    }
  } catch (e) {
    console.log("❌ Исключение при прокурке:", e && e.stack ? e.stack : e);
    process.exit(1);
  }
})();
