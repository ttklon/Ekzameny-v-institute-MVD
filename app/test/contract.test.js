/*
 * test/contract.test.js — договор между интерфейсом, мостом и главным процессом.
 *
 * Самая частая причина «кнопка не работает» — интерфейс зовёт api.x, а такого
 * метода нет. Здесь эти имена сверяются автоматически, чтобы расхождение
 * ловилось до сборки.
 */
"use strict";

const fs = require("fs");
const path = require("path");
const assert = require("assert");

const ROOT = path.join(__dirname, "..");
const read = (f) => fs.readFileSync(path.join(ROOT, f), "utf-8");

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

const rendererFiles = ["renderer/js/app.js", "renderer/js/views.js", "renderer/js/store.js", "renderer/js/ui.js"];
const rendererSource = rendererFiles.map(read).join("\n");
const preload = read("preload.js");
const main = read("main.js");

// Методы, которые интерфейс вызывает у window.api.
const used = new Set();
for (const m of rendererSource.matchAll(/\bapi\.([A-Za-z0-9_]+)\s*[().]/g)) used.add(m[1]);
// Методы, которые мост отдаёт наружу (верхний уровень объекта api).
const exposed = new Set();
const apiBlock = preload.slice(preload.indexOf("const api = {"), preload.indexOf("contextBridge.exposeInMainWorld"));
for (const m of apiBlock.matchAll(/^ {2}([A-Za-z0-9_]+)\s*[:(]/gm)) exposed.add(m[1]);
// Каналы, которые слушает главный процесс, и каналы, которые зовёт мост.
const handled = new Set();
for (const m of main.matchAll(/ipcMain\.(?:handle|on)\(\s*"([^"]+)"/g)) handled.add(m[1]);
const invoked = new Set();
for (const m of preload.matchAll(/ipcRenderer\.invoke\(\s*"([^"]+)"/g)) invoked.add(m[1]);
const sent = new Set();
for (const m of main.matchAll(/webContents\.send\(\s*"([^"]+)"/g)) sent.add(m[1]);
const listened = new Set();
for (const m of preload.matchAll(/ipcRenderer\.on\(\s*"([^"]+)"/g)) listened.add(m[1]);
// Подписки-словари: {"menu:add-files": () => …, …}
for (const m of preload.matchAll(/["'](menu:[a-z-]+|app:[a-z-]+)["']\s*:/g)) listened.add(m[1]);

console.log("\nМост интерфейс ⇄ система");

test("все api.* из интерфейса есть в preload", () => {
  const missing = [...used].filter((x) => !exposed.has(x));
  assert.deepStrictEqual(missing, [], "интерфейс зовёт отсутствующие методы: " + missing.join(", "));
});

test("каждый invoke из preload обработан в main", () => {
  const missing = [...invoked].filter((x) => !handled.has(x));
  assert.deepStrictEqual(missing, [], "нет обработчиков: " + missing.join(", "));
});

test("каждый канал из main кто-то слушает в preload", () => {
  const missing = [...sent].filter((x) => !listened.has(x));
  assert.deepStrictEqual(missing, [], "сообщения уходят в пустоту: " + missing.join(", "));
});

test("в preload нет доступа к Node у интерфейса", () => {
  assert.ok(!/require\("fs"\)/.test(preload), "preload тянет fs");
  assert.ok(!/nodeIntegration:\s*true/.test(main), "nodeIntegration включён");
  assert.ok(/contextIsolation:\s*true/.test(main), "contextIsolation выключен");
});

test("внешние ссылки не открываются внутри окна", () => {
  assert.ok(/setWindowOpenHandler/.test(main), "нет ограничения новых окон");
  assert.ok(/will-navigate/.test(main), "нет ограничения переходов");
});

console.log("\nРазметка и ресурсы");

const html = read("renderer/index.html");

test("порядок скриптов правильный (зависимости раньше)", () => {
  const order = ["../src/core/text.js", "../src/core/parser.js", "../src/core/planner.js",
    "js/sky.js", "js/sound.js", "js/store.js", "js/ui.js", "js/views.js", "js/app.js"];
  let last = -1;
  for (const f of order) {
    const at = html.indexOf('src="' + f + '"');
    assert.ok(at > -1, "не подключён " + f);
    assert.ok(at > last, "нарушен порядок: " + f);
    last = at;
  }
});

test("CSP разрешает локальные файлы и не разрешает удалённые", () => {
  const csp = (html.match(/Content-Security-Policy"\s*\n?\s*content="([^"]+)"/) || [])[1] || "";
  assert.ok(csp, "нет CSP");
  assert.ok(/script-src[^;]*'self'/.test(csp), "скрипты с 'self' не разрешены");
  assert.ok(/script-src[^;]*file:/.test(csp), "скрипты с file: не разрешены — на file:// будет пустое окно");
  assert.ok(!/script-src[^;]*\*/.test(csp), "скрипты разрешены откуда угодно");
  assert.ok(!/script-src[^;]*'unsafe-eval'/.test(csp), "разрешён eval");
});

test("все локальные ресурсы из HTML существуют", () => {
  for (const m of html.matchAll(/(?:src|href)="([^"]+)"/g)) {
    const p = m[1];
    if (/^(https?:|data:|#)/.test(p)) continue;
    const file = path.join(ROOT, "renderer", p);
    assert.ok(fs.existsSync(file), "нет файла " + p);
  }
});

test("шрифты подключены локально, без внешних запросов", () => {
  const fonts = read("renderer/css/fonts.css");
  assert.ok(!/https?:\/\//.test(fonts), "шрифты грузятся из сети");
  for (const m of fonts.matchAll(/url\("([^"]+)"\)/g)) {
    const file = path.join(ROOT, "renderer", "css", m[1]);
    assert.ok(fs.existsSync(file), "нет файла шрифта " + m[1]);
  }
});

test("в сборке ровно семь готовых дисциплин и ничего лишнего", () => {
  // Готовые ответы идут вместе с приложением — по файлу на дисциплину.
  // Но в пакет не должны попадать тестовые образцы и служебные материалы.
  const pkg = JSON.parse(read("package.json"));
  for (const pattern of pkg.build.files) {
    const excluded = pattern.startsWith("!");
    // Исключения наоборот обязательны: «!test/**/*» убирает тесты из пакета.
    if (excluded) continue;
    assert.ok(!/fixtures|(^|\/)test\//i.test(pattern), "в сборку попадает " + pattern);
  }
  const dir = path.join(ROOT, "answers");
  const files = fs.readdirSync(dir).filter((f) => f.endsWith(".txt")).sort();
  assert.deepStrictEqual(files, [
    "adp2.txt",
    "gpp.txt",
    "krim.txt",
    "tp.txt",
    "tsp.txt",
    "ugp.txt",
    "upp.txt"
  ]);
  // Ни в одном файле нет служебных материалов: только вопросы с ответами.
  for (const f of files) {
    const text = fs.readFileSync(path.join(dir, f), "utf-8");
    assert.ok(text.indexOf("# Вопрос 1.") === 0, f + ": файл не начинается с первого вопроса");
    assert.ok(text.length > 100000, f + ": подозрительно маленький файл");
  }
  const fixtures = fs.readdirSync(path.join(ROOT, "test", "fixtures"));
  assert.ok(fixtures.length > 0, "нет тестовых файлов");
});

console.log("\n---");
if (failed) {
  console.log("Провалено: " + failed + ", пройдено: " + passed);
  for (const f of failures) console.log("\n[" + f.name + "]\n" + (f.err.stack || f.err.message));
  process.exitCode = 1;
} else {
  console.log("Всё пройдено: " + passed + " проверок.");
}
