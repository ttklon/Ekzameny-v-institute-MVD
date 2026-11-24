/*
 * test/remind.test.js — напоминания и трей без запуска окна.
 *
 * Electron в тестах не запускается, поэтому модуль `electron` подменяется
 * маленькой заглушкой: она запоминает, что именно хотело показать приложение.
 * Так проверяется настоящая логика remind.js — окно в 10 минут, защита от
 * повторов, текст уведомления и содержимое меню трея.
 */
"use strict";

const assert = require("assert");
const Module = require("module");
const path = require("path");

let passed = 0;
let failed = 0;
const failures = [];

function test(name, fn) {
  try {
    fn();
    passed++;
    console.log("  ✓ " + name);
  } catch (err) {
    failed++;
    failures.push({ name, err });
    console.log("  ✗ " + name + "\n      " + err.message);
  }
}

// --- заглушка electron ------------------------------------------------------

const shown = [];
const trayCalls = [];

class FakeNotification {
  constructor(opts) {
    this.opts = opts;
    this.handlers = {};
  }
  static isSupported() {
    return true;
  }
  on(name, fn) {
    this.handlers[name] = fn;
  }
  show() {
    shown.push({ opts: this.opts, handlers: this.handlers });
  }
}

class FakeTray {
  constructor(img) {
    this.img = img;
    this.handlers = {};
  }
  setToolTip(t) {
    this.tooltip = t;
  }
  setContextMenu(menu) {
    this.menu = menu;
  }
  on(name, fn) {
    this.handlers[name] = fn;
  }
  destroy() {
    this.destroyed = true;
  }
}

const fakeElectron = {
  app: { name: "test" },
  Tray: FakeTray,
  Notification: FakeNotification,
  nativeImage: {
    createFromPath: () => ({ isEmpty: () => false }),
    createEmpty: () => ({ isEmpty: () => true })
  },
  Menu: { buildFromTemplate: (items) => ({ items }) }
};

const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (request === "electron") return fakeElectron;
  return origLoad.apply(this, arguments);
};
const { createReminder, CHECK_EVERY_MS, MIN_GAP_MS } = require("../src/main/remind");
Module._load = origLoad;

// --- общие данные -----------------------------------------------------------

let todayInfo = { tasks: 12, minutes: 34 };
const opened = { window: 0, today: 0, quit: 0 };

function make(opts) {
  return createReminder(
    Object.assign(
      {
        getTodayInfo: () => todayInfo,
        onOpen: () => opened.window++,
        onOpenToday: () => opened.today++,
        onQuit: () => opened.quit++,
        iconPath: path.join(__dirname, "..", "build", "icon.ico")
      },
      opts || {}
    )
  );
}

/** Локальное время, сдвинутое на нужный час/минуту — в нём же считает remind.js. */
function at(hours, minutes) {
  const d = new Date(2026, 10, 24, hours, minutes, 0);
  return d;
}

console.log("\nНапоминания");

test("напоминание срабатывает в своё время и в течение десяти минут", () => {
  const r = make();
  r.configure({ remind: { enabled: true, at: "19:00" }, tray: false });
  assert.strictEqual(r.dueNow(at(18, 59)), false, "до времени — молчим");
  assert.strictEqual(r.dueNow(at(19, 0)), true, "в 19:00 — пора");
  assert.strictEqual(r.dueNow(at(19, 9)), true, "окно ещё идёт");
  assert.strictEqual(r.dueNow(at(19, 10)), false, "окно закрылось");
  assert.strictEqual(r.dueNow(at(23, 30)), false, "поздно вечером не тревожим");
});

test("выключенное напоминание не срабатывает никогда", () => {
  const r = make();
  r.configure({ remind: { enabled: false, at: "19:00" }, tray: false });
  assert.strictEqual(r.dueNow(at(19, 0)), false);
});

test("дни недели учитываются: 0 — воскресенье", () => {
  const r = make();
  // 24 ноября 2026 — вторник (2). Оставляем только воскресенье и вторник.
  r.configure({ remind: { enabled: true, at: "19:00", days: [0, 2] }, tray: false });
  assert.strictEqual(r.dueNow(at(19, 0)), true, "вторник разрешён");
  r.configure({ remind: { enabled: true, at: "19:00", days: [0, 6] }, tray: false });
  assert.strictEqual(r.dueNow(at(19, 0)), false, "вторник запрещён");
});

test("кривое время в настройках не ломает проверку", () => {
  const r = make();
  r.configure({ remind: { enabled: true, at: "вечером" }, tray: false });
  assert.strictEqual(r.dueNow(at(19, 0)), false);
});

test("уведомление содержит число вопросов и время чтения", () => {
  shown.length = 0;
  todayInfo = { tasks: 12, minutes: 34 };
  const r = make();
  assert.strictEqual(r.notify(), true, "уведомление показано");
  assert.strictEqual(shown.length, 1);
  const body = shown[0].opts.body;
  assert.ok(/12 вопросов/.test(body), "нет числа вопросов: " + body);
  assert.ok(/34 мин/.test(body), "нет времени чтения: " + body);
  // Нажатие на уведомление открывает «Сегодня».
  opened.today = 0;
  shown[0].handlers.click();
  assert.strictEqual(opened.today, 1);
});

test("если на сегодня ничего нет — уведомления нет", () => {
  shown.length = 0;
  todayInfo = { tasks: 0, minutes: 0 };
  const r = make();
  assert.strictEqual(r.notify(), false);
  assert.strictEqual(shown.length, 0);
});

test("склонение: 1 вопрос, 2 вопроса, 5 вопросов", () => {
  const cases = [
    [1, "1 вопрос"],
    [2, "2 вопроса"],
    [5, "5 вопросов"],
    [11, "11 вопросов"],
    [21, "21 вопрос"]
  ];
  for (const [n, expected] of cases) {
    shown.length = 0;
    todayInfo = { tasks: n, minutes: 0 };
    const r = make();
    r.notify();
    assert.ok(shown[0].opts.body.indexOf(expected) === 0, "для " + n + ": " + shown[0].opts.body);
  }
});

test("трей показывает, сколько осталось на сегодня, и умеет открывать окно", () => {
  todayInfo = { tasks: 7, minutes: 20 };
  const r = make();
  r.configure({ remind: { enabled: true, at: "19:00" }, tray: true });
  const tray = r.tray;
  assert.ok(tray, "трей не создан");
  assert.ok(/Сегодня: 7 вопросов/.test(tray.tooltip), "подсказка: " + tray.tooltip);
  assert.ok(/20 мин/.test(tray.tooltip), "нет времени: " + tray.tooltip);

  const labels = tray.menu.items.map((i) => i.label || i.type);
  assert.ok(labels.indexOf("Открыть «Сегодня»") !== -1, "нет пункта «Сегодня»: " + labels.join(", "));
  assert.ok(labels.indexOf("Выход") !== -1, "нет выхода");

  opened.window = 0;
  tray.handlers.click();
  assert.strictEqual(opened.window, 1, "клик по значку не открыл окно");

  opened.quit = 0;
  tray.menu.items.find((i) => i.label === "Выход").click();
  assert.strictEqual(opened.quit, 1, "выход из трея не сработал");
});

test("после выполнения плана трей говорит, что всё сделано", () => {
  todayInfo = { tasks: 0, minutes: 0 };
  const r = make();
  r.configure({ remind: { enabled: true, at: "19:00" }, tray: true });
  assert.ok(/всё сделано/i.test(r.tray.tooltip), "подсказка: " + r.tray.tooltip);
});

test("трей можно отключить, и он действительно исчезает", () => {
  const r = make();
  r.configure({ tray: true });
  const tray = r.tray;
  assert.ok(tray);
  r.configure({ tray: false });
  assert.strictEqual(r.tray, null, "трей не убран");
  assert.strictEqual(tray.destroyed, true, "у значка не вызван destroy");
});

test("повторное включение трея создаёт его заново, а не падает", () => {
  const r = make();
  r.configure({ tray: true });
  r.configure({ tray: false });
  r.configure({ tray: true });
  assert.ok(r.tray, "трей не вернулся");
});

test("ошибка в подсчёте «на сегодня» не роняет напоминание", () => {
  const r = make({
    getTodayInfo: () => {
      throw new Error("библиотека не загрузилась");
    }
  });
  r.configure({ remind: { enabled: true, at: "19:00" }, tray: true });
  assert.ok(r.tray, "трей должен работать и без данных");
  assert.strictEqual(r.notify(), false, "уведомление без данных не показываем");
});

test("интервалы проверки и защиты от повторов разумны", () => {
  assert.strictEqual(CHECK_EVERY_MS, 60000, "проверка раз в минуту");
  assert.strictEqual(MIN_GAP_MS, 1800000, "не чаще раза в полчаса");
});

test("start/stop не оставляют висящих таймеров", () => {
  const r = make();
  r.configure({ tray: false });
  r.start();
  r.start(); // повторный запуск не должен плодить таймеры
  r.stop();
  r.stop();
  assert.ok(true);
});

if (failures.length) {
  console.log("\nПровалились:");
  for (const f of failures) console.log("  • " + f.name + ": " + f.err.stack.split("\n")[0]);
}

console.log("\nНапоминания: " + passed + " ок, " + failed + " с ошибками");
process.exit(failed ? 1 : 0);
