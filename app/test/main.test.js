/*
 * test/main.test.js — проверка главного процесса без запуска окна.
 *
 * Здесь проверяется то, что интерфейс не видит: сохранение библиотеки
 * (включая восстановление из резервной копии), копии текстов и запись CSV.
 * Хранилище работает с папкой профиля, поэтому ей подсовывается временная.
 */
"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const assert = require("assert");

const { createStore } = require("../src/main/store");

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

const dir = fs.mkdtempSync(path.join(os.tmpdir(), "planner-test-"));
const store = createStore(dir);
const P = store.paths;

const library = {
  version: 1,
  disciplines: [
    { id: "d1", name: "Тест", questions: [{ num: 1, title: "В" }], reads: { 0: ["2026-11-24"] } }
  ],
  settings: { wordsPerMinute: 150 },
  ui: { view: "today" }
};

console.log("\nХранилище");

test("сначала библиотеки нет — это не ошибка", () => {
  const r = store.load();
  assert.strictEqual(r.state, null);
  assert.strictEqual(r.recovered, false);
});

test("библиотека сохраняется и читается обратно", () => {
  const saved = store.save(library);
  assert.ok(saved.ok, "save не вернул ok: " + (saved && saved.error));
  assert.ok(saved.bytes > 100, "подозрительно маленький файл");
  const loaded = store.load();
  assert.strictEqual(loaded.recovered, false);
  assert.strictEqual(loaded.state.disciplines.length, 1);
  assert.strictEqual(loaded.state.disciplines[0].name, "Тест");
  assert.deepStrictEqual(loaded.state.disciplines[0].reads["0"], ["2026-11-24"]);
  assert.strictEqual(loaded.state.settings.wordsPerMinute, 150);
});

test("предыдущая версия остаётся в резервной копии", () => {
  store.save(Object.assign({}, library, { settings: { wordsPerMinute: 200 } }));
  assert.ok(fs.existsSync(P.backupFile), "нет файла резервной копии");
  const bak = JSON.parse(fs.readFileSync(P.backupFile, "utf-8"));
  assert.strictEqual(bak.settings.wordsPerMinute, 150, "в копии не предыдущая версия");
});

test("повреждённый основной файл восстанавливается из копии", () => {
  fs.writeFileSync(P.mainFile, "{ это не json", "utf-8");
  const loaded = store.load();
  assert.strictEqual(loaded.recovered, true, "восстановление не отмечено");
  assert.strictEqual(loaded.state.settings.wordsPerMinute, 150, "взята не резервная копия");
});

test("после восстановления запись снова работает", () => {
  store.save(library);
  const loaded = store.load();
  assert.strictEqual(loaded.recovered, false, "снова пометил как восстановленную");
  assert.ok(fs.existsSync(P.mainFile));
});

test("временный файл не остаётся после записи", () => {
  store.save(library);
  assert.ok(!fs.existsSync(path.join(dir, "library.tmp.json")), "остался временный файл");
});

console.log("\nТексты файлов");

test("копия текста сохраняется и читается", () => {
  const text = "Вопрос 1. Тест\nОтвет: проверка";
  const name = store.saveText("disc-1", text);
  assert.strictEqual(name, "disc-1.txt");
  assert.strictEqual(store.loadText(name), text);
});

test("имя с недопустимыми знаками не выводит за папку", () => {
  const name = store.saveText("../../evil", "данные");
  assert.ok(name.indexOf("..") === -1, "переход вверх сохранился: " + name);
  assert.ok(name.indexOf("/") === -1 && name.indexOf("\\") === -1, "разделитель в имени: " + name);
  const file = path.join(dir, "texts", name);
  assert.strictEqual(fs.readFileSync(file, "utf-8"), "данные");
  assert.strictEqual(store.loadText(name), "данные");
});

test("удалённый текст больше не читается", () => {
  const name = store.saveText("temp", "скоро удалю");
  assert.strictEqual(store.removeText(name), true);
  assert.strictEqual(store.loadText(name), null);
});

test("размер хранилища считается", () => {
  store.save(library);
  store.saveText("d2", "текст для подсчёта");
  const stats = store.stats();
  assert.ok(stats.libraryBytes > 0, "нет размера библиотеки");
  assert.ok(stats.textsBytes > 0, "нет размера текстов");
  assert.strictEqual(stats.dir, dir);
});

console.log("\nВыгрузка");

test("резервная копия содержит всю библиотеку", () => {
  const target = path.join(dir, "backup.json");
  const res = store.exportTo(target, library);
  assert.ok(res.ok, res.error);
  const parsed = JSON.parse(fs.readFileSync(target, "utf-8"));
  assert.strictEqual(parsed.disciplines[0].name, "Тест");
  assert.strictEqual(parsed.settings.wordsPerMinute, 150);
});

test("в выгрузке нет служебных полей вроде undefined", () => {
  const target = path.join(dir, "backup2.json");
  store.exportTo(target, library);
  const raw = fs.readFileSync(target, "utf-8");
  assert.ok(raw.indexOf("undefined") === -1, "в файле есть undefined");
  assert.ok(JSON.parse(raw), "файл не разбирается");
});

fs.rmSync(dir, { recursive: true, force: true });

console.log("\n---");
if (failed) {
  console.log("Провалено: " + failed + ", пройдено: " + passed);
  for (const f of failures) console.log("\n[" + f.name + "]\n" + (f.err.stack || f.err.message));
  process.exitCode = 1;
} else {
  console.log("Всё пройдено: " + passed + " проверок.");
}
