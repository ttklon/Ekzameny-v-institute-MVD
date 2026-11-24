/*
 * Smoke-тест ядра на реальном файле из репозитория (только чтение, ничего не меняет).
 */
const fs = require("fs");
const path = require("path");

const textstats = require("../src/core/textstats");
const parser = require("../src/core/parser");
const planner = require("../src/core/planner");

// Путь к реальному файлу в корне репозитория.
const repoFile = path.resolve(__dirname, "..", "..", "Примерный перечень вопросов к экзамену по административной деятельности полиции России.txt");
const buf = fs.readFileSync(repoFile);
const text = buf.toString("utf-8"); // файл валиден как UTF-8

const settings = {
  speedUnit: "wpm",
  wordsPerMinute: 250,
  charsPerMinute: 1500,
  restDays: [],
  global: { dailyMinutes: 60 }
};

console.log("=== ПАРСЕР ===");
const parsed = parser.parseDocument(text, { unit: "wpm", rate: 250, assumeAnswerWords: 220 });
console.log("Стратегия:", parsed.strategy);
console.log("Всего вопросов:", parsed.count);
console.log("Всего слов (с учётом предполагаемого ответа):", parsed.totalWords);
console.log("Всего минут чтения:", parsed.totalMinutes.toFixed(1));
console.log("Пример вопроса #1:", parsed.questions[0].question.slice(0, 80));
console.log("Пример вопроса #24 (мусор '181' не должен попасть):");
// Проверяем, что нет вопроса с num=181 и пустым текстом
const stray = parsed.questions.find((q) => q.num === 181 && q.question.length < 5);
console.log("  найден мусорный вопрос 181?", !!stray);

const disc = {
  id: "test-1",
  name: "Административная деятельность полиции",
  questions: parsed.questions,
  plan: {
    startDate: "2025-11-24",
    examDate: "2025-12-24",
    passes: 3,
    mode: "questions",
    perDayQuestions: 10,
    perDayMinutes: 15,
    assumeAnswerWords: 220,
    restDays: [],
    reviewSpeedFactor: 1.3
  },
  progress: {}
};

console.log("\n=== ПЛАНИРОВЩИК (режим 'questions', 10 вопр/день, 3 прогона) ===");
let r = planner.computeAll({ settings, disciplines: [disc] }, "2025-11-24");
printResult(r, disc.id);

console.log("\n=== ПЛАНИРОВЩИК (режим 'minutes', 20 мин/день) ===");
disc.plan.mode = "minutes";
disc.plan.perDayMinutes = 20;
r = planner.computeAll({ settings, disciplines: [disc] }, "2025-11-24");
printResult(r, disc.id);

console.log("\n=== ГЛОБАЛЬНЫЙ БЮДЖЕТ (2 дисциплины, по 60 мин/день) ===");
const disc2 = JSON.parse(JSON.stringify(disc));
disc2.id = "test-2";
disc2.name = "Уголовный процесс";
disc2.plan.mode = "global";
disc.plan.mode = "global";
r = planner.computeAll({ settings, disciplines: [disc, disc2] }, "2025-11-24");
console.log("Дней в расписании:", Object.keys(r.combined).length);
const sampleDay = Object.keys(r.combined)[0];
const byDisc = {};
r.combined[sampleDay].forEach((u) => (byDisc[u.discId] = (byDisc[u.discId] || 0) + 1));
console.log("Первый день", sampleDay, "распределение по дисциплинам:", byDisc);

console.log("\n=== ПЕРЕСЧЁТ ПОСЛЕ ОТМЕТКИ ПРОГРЕССА ===");
disc.plan.mode = "questions";
disc.plan.perDayQuestions = 10;
// Отметим первые 5 вопросов 1-го прогона как прочитанные.
disc.progress = {};
for (let i = 0; i < 5; i++) disc.progress[i + ":1"] = { done: true, date: "2025-11-24" };
r = planner.computeAll({ settings, disciplines: [disc] }, "2025-11-24");
const pd = r.perDisc[disc.id];
console.log("Осталось единиц:", pd.stats.remainingUnits, "/ всего:", pd.stats.totalUnits);
console.log("Прогресс сегодня (задачи на 2025-11-24):", r.combined["2025-11-24"] ? r.combined["2025-11-24"].length : 0, "единиц");

function printResult(r, id) {
  const pd = r.perDisc[id];
  if (pd.error) {
    console.log("  ОШИБКА:", pd.error);
    return;
  }
  console.log("  Всего единиц (вопрос×прогон):", pd.stats.totalUnits);
  console.log("  Дней доступно:", pd.stats.daysAvailable);
  console.log("  Норма в день:", pd.stats.perDayTarget);
  console.log("  Отстаёт:", pd.stats.behind);
  console.log("  Дней в расписании:", Object.keys(pd.schedule).length);
  const firstDay = Object.keys(pd.schedule).find((d) => pd.schedule[d].length > 0);
  if (firstDay) console.log("  Первый день", firstDay, "→", pd.schedule[firstDay].length, "единиц");
  console.log("  Предупреждения:", r.warnings.map((w) => w.text));
}

console.log("\nВсе тесты выполнены без исключений.");
