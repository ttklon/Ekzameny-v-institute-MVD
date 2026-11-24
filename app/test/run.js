/*
 * test/run.js — все проверки одной командой: `npm test`.
 *
 * Каждый набор запускается отдельным процессом: если один упадёт, остальные
 * всё равно выполнятся, а код возврата будет ненулевым.
 */
"use strict";

const { spawnSync } = require("child_process");
const path = require("path");

const suites = [
  { file: "core.test.js", title: "Ядро: подсчёт, разбор файлов, планирование" },
  { file: "main.test.js", title: "Главный процесс: хранение, копии, выгрузка" },
  { file: "contract.test.js", title: "Договор: интерфейс ⇄ мост ⇄ главный процесс" },
  { file: "remind.test.js", title: "Напоминания и трей" },
  { file: "dom.test.js", title: "Интерфейс: экраны, отметки, импорт" }
];

let failed = 0;
const started = Date.now();

for (const suite of suites) {
  console.log("\n=== " + suite.title + " ===");
  const res = spawnSync(process.execPath, [path.join(__dirname, suite.file)], {
    stdio: "inherit",
    env: process.env
  });
  if (res.status !== 0) failed++;
}

const secs = ((Date.now() - started) / 1000).toFixed(1);
console.log("\n" + (failed ? "Наборов с ошибками: " + failed : "Все проверки прошли") + " (" + secs + " с)");
process.exit(failed ? 1 : 0);
