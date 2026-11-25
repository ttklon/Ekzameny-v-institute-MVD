/*
 * test/core.test.js — проверка ядра: подсчёт, разбор файлов, планирование.
 *
 * Тесты написаны на реальных файлах из репозитория (test/fixtures): сборник
 * «все ответы», файл на один вопрос и перечень вопросов без ответов. Если
 * парсер перестанет понимать какой-то из этих форматов, тест это покажет.
 */
"use strict";

const fs = require("fs");
const path = require("path");
const assert = require("assert");

const text = require("../src/core/text");
const parser = require("../src/core/parser");
const planner = require("../src/core/planner");
const decoder = require("../src/main/decode");
const docx = require("../src/main/docx");

const FIX = path.join(__dirname, "fixtures");
const read = (f) => fs.readFileSync(path.join(FIX, f), "utf-8");

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

// =====================================================================
//  Подсчёт текста
// =====================================================================

console.log("\nПодсчёт текста");

test("считает слова, дефис не разрывает слово", () => {
  assert.strictEqual(text.countWords("административно-правовой режим"), 2);
  assert.strictEqual(text.countWords("Согласно п. «е» ч. 1 ст. 114"), 7);
  assert.strictEqual(text.countWords(""), 0);
  assert.strictEqual(text.countWords(null), 0);
});

test("считает знаки без пробелов и с пробелами", () => {
  const s = "привет мир";
  assert.strictEqual(text.countChars(s, false), 9);
  assert.strictEqual(text.countChars(s, true), 10);
});

test("кириллица, латиница и цифры считаются словами", () => {
  assert.strictEqual(text.countWords("Полиция РФ 2026 № 3-ФЗ"), 4);
  assert.strictEqual(text.countWords("статья 12 часть 3"), 4);
});

test("нормализует переводы строк и мягкие переносы", () => {
  assert.strictEqual(text.normalizeNewlines("a\r\nb\rc"), "a\nb\nc");
  assert.strictEqual(text.cleanText("текст\u00ADс\u00A0пробелом"), "текстс пробелом");
});

test("сложный текст получает поправку на сложность выше 1", () => {
  const simple = text.difficultyIndex("И вот мы идём домой, и там нас ждут.");
  const dense = text.difficultyIndex(
    "Административно-правовое регулирование общественных отношений, возникающих в сфере " +
      "внутренних дел (п. 2 ч. 1 ст. 2), осуществляется уполномоченными должностными лицами " +
      "органов внутренних дел (полиции) в порядке, предусмотренном законодательством " +
      "Российской Федерации о государственной службе; см. также ст. 12, ч. 3 ст. 25."
  );
  assert.ok(dense > simple, "плотный текст должен быть сложнее: " + dense + " vs " + simple);
  assert.ok(dense > 1, "поправка должна быть больше 1");
});

test("время чтения зависит от скорости и сложности", () => {
  const fast = text.readingMinutes(300, 1800, "wpm", 300);
  const slow = text.readingMinutes(300, 1800, "wpm", 150);
  assert.ok(Math.abs(slow - fast * 2) < 1e-9, "вдвое медленнее — вдвое дольше");
  const hard = text.readingMinutes(300, 1800, "wpm", 150, { difficulty: 1.5 });
  assert.ok(Math.abs(hard - slow * 1.5) < 1e-9, "сложность умножает время");
});

test("человекочитаемая длительность", () => {
  assert.strictEqual(text.humanDurationShort(45), "45 мин");
  assert.strictEqual(text.humanDurationShort(60), "1 ч");
  assert.strictEqual(text.humanDurationShort(135), "2 ч 15 мин");
  assert.strictEqual(text.humanDurationShort(0), "0 мин");
});

test("форматирование чисел и склонений", () => {
  assert.strictEqual(text.humanNumber(1234567).replace(/\u202F/g, " "), "1 234 567");
  assert.strictEqual(text.plural(1, "вопрос", "вопроса", "вопросов"), "вопрос");
  assert.strictEqual(text.plural(3, "вопрос", "вопроса", "вопросов"), "вопроса");
  assert.strictEqual(text.plural(11, "вопрос", "вопроса", "вопросов"), "вопросов");
  assert.strictEqual(text.plural(21, "вопрос", "вопроса", "вопросов"), "вопрос");
});

// =====================================================================
//  Разбор файлов «вопрос — ответ»
// =====================================================================

console.log("\nРазбор файлов");

test("сборник с заголовками «# Вопрос N.» разобран на вопросы", () => {
  const r = parser.parseDocument(read("sample-all-answers.txt"));
  assert.strictEqual(r.strategy, "markdown-headings");
  assert.strictEqual(r.count, 3, "ожидалось три вопроса, найдено " + r.count);
  assert.strictEqual(r.answeredCount, 3);
  assert.ok(r.totalWords > 2000, "мало слов: " + r.totalWords);
  const q = r.questions[0];
  assert.ok(q.question.indexOf("Полиция как субъект") === 0, "неверный вопрос: " + q.question.slice(0, 60));
  assert.ok(q.aWords > 700, "ответ слишком короткий: " + q.aWords);
  assert.strictEqual(q.num, 1);
  assert.strictEqual(r.questions[1].num, 45);
});

test("файл на один вопрос разобран целиком", () => {
  const r = parser.parseDocument(read("sample-single-question.txt"));
  assert.strictEqual(r.strategy, "single-question-file");
  assert.strictEqual(r.count, 1);
  const q = r.questions[0];
  assert.strictEqual(q.num, 45);
  assert.ok(q.aWords > 500, "ответ должен быть большим: " + q.aWords);
  assert.ok(q.title.length > 20, "нет заголовка");
});

test("перечень вопросов без ответов распознан по нумерации", () => {
  const r = parser.parseDocument(read("sample-question-list.txt"), { assumeAnswerWords: 250 });
  assert.strictEqual(r.strategy, "numbered-list");
  assert.strictEqual(r.count, 149, "найдено " + r.count);
  assert.ok(r.questions[0].question.indexOf("Полиция как субъект") === 0);
  assert.ok(r.questions[148].num === 149);
  // Ответов в файле нет — объём оценён, и об этом есть предупреждение.
  assert.ok(r.warnings.some((w) => w.type === "no-answers"), "нет предупреждения об оценке");
  assert.ok(r.questions[0].estimated, "вопрос должен быть помечен как оценённый");
  assert.ok(r.questions[0].aWords === 250, "оценка не применилась: " + r.questions[0].aWords);
});

test("«Ответ:» отделяет вопрос от ответа", () => {
  const src = [
    "1. Что такое полиция?",
    "Ответ: Полиция — это орган внутренних дел.",
    "",
    "2. Какие принципы деятельности полиции?",
    "Ответ: Соблюдение прав, законность, открытость.",
    "",
    "3. Что такое общественный порядок?",
    "Ответ: Система отношений, обеспечивающая безопасность."
  ].join("\n");
  const r = parser.parseDocument(src);
  assert.strictEqual(r.count, 3);
  assert.strictEqual(r.strategy, "numbered-with-answers");
  assert.ok(r.questions[0].answer.indexOf("орган внутренних дел") > -1, "ответ не отделён: " + r.questions[0].answer);
});

test("заголовок, а сразу под ним вводная строка ответа", () => {
  // Так устроено большинство реальных файлов: одна строка заголовка, затем
  // сразу длинный абзац ответа без пустой строки между ними.
  const src = [
    "# Вопрос 85. Тактические нормативы взвода, отделения в наступлении",
    "Ответ составлен по учебникам общей тактики для мотострелковых подразделений; термин «противник» взят из них же и означает противостоящую сторону.",
    "## Взвод",
    "- **Фронт наступления:** до 400 метров."
  ].join("\n");
  const r = parser.parseDocument(src);
  assert.strictEqual(r.count, 1);
  assert.strictEqual(r.questions[0].question, "Тактические нормативы взвода, отделения в наступлении");
  assert.ok(r.questions[0].answer.indexOf("Ответ составлен по учебникам") === 0, "ответ начался не с вводной строки: " + r.questions[0].answer.slice(0, 80));
});

test("заголовок из двух фраз не разрезается, если ниже есть ответ", () => {
  const src = [
    "# Вопрос 29. Подготовка к обыску. Использование помощи специалистов при подготовке технико-криминалистических средств поиска",
    "> **Подготовка к обыску** — действия следователя от принятия решения об обыске до начала поиска.",
    "",
    "Далее идёт подробный разбор."
  ].join("\n");
  const r = parser.parseDocument(src);
  assert.strictEqual(r.count, 1);
  assert.ok(r.questions[0].question.indexOf("Использование помощи специалистов") > -1, "вторая фраза заголовка потеряна: " + r.questions[0].question);
  assert.ok(r.questions[0].answer.indexOf("Подготовка к обыску") > -1, "ответ потерян");
});

test("вопрос и ответ подряд, без пустых строк между ними", () => {
  const src = [
    "1. Что такое административное правонарушение?",
    "Правонарушением признаётся противоправное виновное деяние, за которое установлена ответственность по КоАП РФ.",
    "2. Что такое административное наказание?",
    "Наказание — установленная государством мера ответственности за совершение правонарушения.",
    "3. Кто рассматривает дела об административных правонарушениях?",
    "Судьи, органы внутренних дел и иные уполномоченные органы в пределах своей компетенции."
  ].join("\n");
  const r = parser.parseDocument(src);
  assert.strictEqual(r.count, 3, "распознано " + r.count);
  assert.ok(r.questions[0].answer.indexOf("Правонарушением признаётся") === 0, "ответ 1 съеден вопросом");
  assert.ok(r.questions[1].answer.indexOf("Наказание —") === 0, "ответ 2 съеден вопросом");
  assert.ok(r.questions[2].question.indexOf("Кто рассматривает") === 0, "вопрос 3 неверен");
});

test("перечень вопросов, затем ответы с теми же номерами", () => {
  // Самая частая структура настоящих файлов: сверху все вопросы, снизу все
  // ответы. Раньше ответы принимались за вопросы, и всё оставалось без ответов.
  const src = [
    "1. Понятие административного правонарушения",
    "2. Признаки административного правонарушения",
    "3. Виды административных наказаний",
    "",
    "ОТВЕТЫ",
    "",
    "1. Административным правонарушением признаётся противоправное виновное деяние физического лица.",
    "",
    "2. Признаки: противоправность, виновность, наказуемость, деяние.",
    "",
    "3. Виды наказаний перечислены в статье 3.2 КоАП РФ: предупреждение, штраф."
  ].join("\n");
  const r = parser.parseDocument(src);
  assert.strictEqual(r.count, 3, "вопросов " + r.count);
  assert.strictEqual(r.strategy, "list-and-answers");
  assert.ok(r.questions[0].question.indexOf("Понятие административного") === 0, "вопрос 1: " + r.questions[0].question);
  assert.ok(r.questions[0].answer.indexOf("Административным правонарушением") === 0, "ответ 1: " + r.questions[0].answer);
  assert.ok(r.questions[2].answer.indexOf("Виды наказаний") === 0, "ответ 3: " + r.questions[2].answer);
  assert.strictEqual(r.questions.filter((q) => q.hasAnswer).length, 3, "не все с ответами");
  assert.ok(!r.warnings.some((w) => w.type === "no-answers"), "не должно быть оценки объёма");
});

test("ответы под номерами отдельной строкой («1.» и текст ниже)", () => {
  const src = [
    "1. Понятие административного правонарушения",
    "2. Признаки административного правонарушения",
    "",
    "ОТВЕТЫ",
    "",
    "1.",
    "Административным правонарушением признаётся противоправное виновное деяние.",
    "",
    "2.",
    "Признаки: противоправность, виновность, наказуемость, деяние."
  ].join("\n");
  const r = parser.parseDocument(src);
  assert.strictEqual(r.count, 2, "вопросов " + r.count);
  assert.strictEqual(r.strategy, "list-and-answers");
  assert.ok(r.questions[0].answer.indexOf("Административным") === 0, "ответ 1: " + r.questions[0].answer);
  assert.ok(r.questions[1].answer.indexOf("Признаки") === 0, "ответ 2: " + r.questions[1].answer);
});

test("«Вопрос N.» сверху и «Ответ N.» снизу", () => {
  const src = [
    "Вопрос 1. Понятие административного правонарушения",
    "Вопрос 2. Признаки административного правонарушения",
    "",
    "Ответ 1. Административным правонарушением признаётся противоправное виновное деяние.",
    "",
    "Ответ 2. Признаки: противоправность, виновность, наказуемость."
  ].join("\n");
  const r = parser.parseDocument(src);
  assert.strictEqual(r.count, 2, "вопросов " + r.count);
  assert.strictEqual(r.strategy, "questions-and-answers");
  assert.ok(r.questions[0].answer.indexOf("Административным") === 0, "ответ 1: " + r.questions[0].answer);
  assert.ok(r.questions[1].answer.indexOf("Признаки") === 0, "ответ 2: " + r.questions[1].answer);
});

test("ответы без номеров под заголовком «Ответы»", () => {
  // Выгрузка из Word: сверху перечень вопросов, ниже раздел «Ответы»,
  // под ним ответы обычными абзацами в том же порядке. Номеров у ответов нет.
  const src = [
    "1. Понятие административного правонарушения",
    "2. Признаки административного правонарушения",
    "3. Виды административных наказаний",
    "",
    "Ответы:",
    "",
    "Правонарушением признаётся противоправное виновное деяние лица, за которое установлена ответственность.",
    "",
    "К признакам относят противоправность, виновность, наказуемость и само деяние.",
    "",
    "Виды наказаний перечислены в статье 3.2 КоАП РФ: предупреждение, штраф и другие."
  ].join("\n");
  const r = parser.parseDocument(src);
  assert.strictEqual(r.count, 3, "вопросов " + r.count);
  assert.strictEqual(r.strategy, "list-and-plain-answers");
  assert.strictEqual(r.questions.filter((q) => q.hasAnswer).length, 3, "не все с ответами");
  assert.ok(r.questions[0].answer.indexOf("Правонарушением признаётся") === 0, "ответ 1: " + r.questions[0].answer);
  assert.ok(r.questions[2].answer.indexOf("Виды наказаний") === 0, "ответ 3: " + r.questions[2].answer);
  assert.ok(!r.warnings.some((w) => w.type === "no-answers"), "не должно быть оценки объёма");
});

test("ответы подряд без пустых строк тоже делятся по одному", () => {
  const src = [
    "1. Понятие административного правонарушения",
    "2. Признаки административного правонарушения",
    "",
    "ОТВЕТЫ",
    "Правонарушением признаётся противоправное виновное деяние лица, за которое установлена ответственность.",
    "К признакам относят противоправность, виновность, наказуемость и само деяние."
  ].join("\n");
  const r = parser.parseDocument(src);
  assert.strictEqual(r.count, 2, "вопросов " + r.count);
  assert.strictEqual(r.questions.filter((q) => q.hasAnswer).length, 2, "не все с ответами");
  assert.ok(r.questions[1].answer.indexOf("К признакам") === 0, "ответ 2: " + r.questions[1].answer);
});

test("вопрос и ответ через тире в одной строке", () => {
  const src = [
    "1. Понятие административного правонарушения — противоправное виновное деяние лица, за которое установлена ответственность.",
    "2. Виды наказаний — предупреждение, штраф, лишение специального права и иные меры.",
    "3. Порядок обжалования — в течение десяти суток со дня вручения копии."
  ].join("\n");
  const r = parser.parseDocument(src);
  assert.strictEqual(r.count, 3);
  assert.strictEqual(r.questions.filter((q) => q.hasAnswer).length, 3, "не все с ответами");
  assert.strictEqual(r.questions[0].question, "Понятие административного правонарушения");
});

test("жирная нумерация «**1. Вопрос**» распознаётся", () => {
  const src = [
    "**1. Понятие административного правонарушения**",
    "Правонарушением признаётся противоправное виновное деяние лица.",
    "",
    "**2. Признаки административного правонарушения**",
    "К признакам относят противоправность, виновность и наказуемость."
  ].join("\n");
  const r = parser.parseDocument(src);
  assert.strictEqual(r.count, 2, "вопросов " + r.count);
  assert.strictEqual(r.questions[0].question, "Понятие административного правонарушения");
  assert.ok(r.questions[0].answer.indexOf("Правонарушением") === 0);
});

test("вопросы со знаком «?» без нумерации", () => {
  const src = [
    "Что такое административное правонарушение?",
    "Это противоправное виновное деяние, за которое предусмотрена ответственность по КоАП РФ.",
    "",
    "Какие виды наказаний применяются?",
    "Предупреждение, штраф, административный арест и другие меры.",
    "",
    "Кто рассматривает дела об административных правонарушениях?",
    "Органы внутренних дел, суды и иные уполномоченные органы."
  ].join("\n");
  const r = parser.parseDocument(src);
  assert.strictEqual(r.count, 3, "найдено " + r.count);
  assert.strictEqual(r.strategy, "question-lines");
});

test("текст без структуры импортируется как один вопрос", () => {
  const r = parser.parseDocument("Просто абзац текста без всякой структуры.");
  assert.strictEqual(r.count, 1);
  assert.strictEqual(r.strategy, "whole-document");
  assert.ok(r.warnings.some((w) => w.type === "whole-document"), "нет предупреждения");
});

test("пустой файл обработан без ошибок", () => {
  const r = parser.parseDocument("   \n\n  ");
  assert.strictEqual(r.count, 0);
  assert.strictEqual(r.strategy, "empty");
  assert.ok(r.warnings.length > 0);
});

test("мусор от PDF (номера страниц) не ломает разбор", () => {
  const src = [
    "1. Первый вопрос",
    "Ответ на первый вопрос.",
    "",
    "15",
    "",
    "2. Второй вопрос",
    "Ответ на второй вопрос.",
    "",
    "16",
    "",
    "3. Третий вопрос",
    "Ответ на третий вопрос."
  ].join("\n");
  const r = parser.parseDocument(src);
  assert.strictEqual(r.count, 3, "найдено " + r.count);
});

test("два перечня в одном файле не теряются", () => {
  const src = [
    "1. Вопрос из первого перечня",
    "",
    "2. Второй вопрос первого перечня",
    "",
    "1. Вопрос из второго перечня",
    "",
    "2. Второй вопрос второго перечня"
  ].join("\n");
  const r = parser.parseDocument(src);
  assert.strictEqual(r.count, 4, "найдено " + r.count);
  assert.strictEqual(r.questions[2].num, 1, "второй перечень не распознан");
});

// =====================================================================
//  Даты и календарь
// =====================================================================

console.log("\nДаты и календарь");

test("разбор и форматирование дат без часовых поясов", () => {
  assert.strictEqual(planner.fmtDate(planner.parseDate("2026-11-24")), "2026-11-24");
  assert.strictEqual(planner.addDays("2026-11-30", 1), "2026-12-01");
  assert.strictEqual(planner.addDays("2026-12-31", 1), "2027-01-01");
  assert.strictEqual(planner.addDays("2026-03-01", -1), "2026-02-28");
  assert.strictEqual(planner.daysBetween("2026-11-24", "2026-12-24"), 30);
});

test("проверка дат отсекает мусор", () => {
  assert.strictEqual(planner.isValidDate("2026-11-24"), true);
  assert.strictEqual(planner.isValidDate("2026-02-30"), false);
  assert.strictEqual(planner.isValidDate("24.11.2026"), false);
  assert.strictEqual(planner.isValidDate(""), false);
});

test("выходные дни исключаются из активных", () => {
  // 24 ноября 2026 — вторник.
  const days = planner.listActiveDays("2026-11-24", "2026-11-29", [0, 6]);
  assert.deepStrictEqual(days, ["2026-11-24", "2026-11-25", "2026-11-26", "2026-11-27"]);
});

// =====================================================================
//  Планирование
// =====================================================================

console.log("\nПланирование");

// Порядок вопросов в плане — главное требование: первый прогон идёт строго
// 1, 2, 3 … без перескоков, иначе читать список невозможно.
test("первый прогон идёт строго по порядку номеров", () => {
  const planner = require("../src/core/planner");
  const today = "2026-11-25";
  for (const [count, exam, passes] of [
    [44, "2026-12-10", 3],
    [44, "2026-12-25", 3],
    [149, "2027-01-15", 3],
    [149, "2027-03-01", 1],
    [20, "2026-12-05", 2]
  ]) {
    const disc = makeDisc(count);
    disc.plan = Object.assign(planner.defaultPlan(today, exam), { passes: passes });
    const plan = planner.computeAll({ settings: {}, disciplines: [disc] }, today);
    const days = plan.perDisc[disc.id].days;
    let last = 0;
    const jumps = [];
    for (const date of Object.keys(days).sort()) {
      days[date]
        .filter((it) => it.pass === 1)
        .sort((a, b) => a.qIndex - b.qIndex)
        .forEach((it) => {
          if (it.qIndex + 1 < last) jumps.push("вопрос " + (it.qIndex + 1) + " после " + last);
          last = Math.max(last, it.qIndex + 1);
        });
    }
    assert.deepStrictEqual(
      jumps,
      [],
      "вопросов " + count + ", экзамен " + exam + ", прогонов " + passes + ": " + jumps.slice(0, 3).join("; ")
    );
    // И каждый вопрос получает первое чтение ровно один раз.
    const firsts = Object.values(days).reduce((n, items) => n + items.filter((i) => i.pass === 1).length, 0);
    assert.strictEqual(firsts, count, "первых чтений: " + firsts + " вместо " + count);
  }
});

test("внутри дня новые вопросы идут раньше повторений и по возрастанию", () => {
  const planner = require("../src/core/planner");
  const today = "2026-11-25";
  const disc = makeDisc(60);
  disc.plan = Object.assign(planner.defaultPlan(today, "2026-12-20"), { passes: 3 });
  const plan = planner.computeAll({ settings: {}, disciplines: [disc] }, today);
  for (const date of Object.keys(plan.combined)) {
    const items = plan.combined[date];
    let seenReview = false;
    let prevNew = 0;
    for (const it of items) {
      if (it.pass > 1) {
        seenReview = true;
        continue;
      }
      assert.ok(!seenReview, "новый вопрос после повторения в " + date);
      assert.ok(it.qIndex >= prevNew, "новые не по порядку в " + date);
      prevNew = it.qIndex;
    }
  }
});

test("порядок сохраняется, когда в день не помещается больше вопросов", () => {
  // Тесный срок: раньше «свободный день» перетаскивал вопрос 40 во второй
  // день, и план читался вразнобой.
  const planner = require("../src/core/planner");
  const today = "2026-11-25";
  const disc = makeDisc(44, { words: 1200 });
  disc.plan = Object.assign(planner.defaultPlan(today, "2026-12-02"), { passes: 3 });
  const plan = planner.computeAll(
    { settings: { dailyCapMinutes: 20 }, disciplines: [disc] },
    today
  );
  const days = plan.perDisc[disc.id].days;
  let last = 0;
  for (const date of Object.keys(days).sort()) {
    days[date]
      .filter((it) => it.pass === 1)
      .sort((a, b) => a.qIndex - b.qIndex)
      .forEach((it) => {
        assert.ok(it.qIndex + 1 >= last, "перескок: вопрос " + (it.qIndex + 1) + " после " + last);
        last = Math.max(last, it.qIndex + 1);
      });
  }
});


function makeDisc(questionCount, opts) {
  opts = opts || {};
  const questions = [];
  for (let i = 0; i < questionCount; i++) {
    questions.push({
      num: i + 1,
      title: "Вопрос " + (i + 1),
      question: "Вопрос " + (i + 1),
      answer: "Ответ",
      words: opts.words || 600,
      chars: (opts.words || 600) * 6,
      qWords: 10,
      aWords: (opts.words || 600) - 10,
      qChars: 60,
      aChars: (opts.words || 600) * 6,
      difficulty: 1,
      hasAnswer: true
    });
  }
  return {
    id: "d1",
    name: "Тест",
    questions,
    plan: planner.defaultPlan("2026-11-24", opts.exam || "2026-12-24"),
    reads: opts.reads || {}
  };
}

const settings = planner.normalizeSettings({ wordsPerMinute: 150 });

test("нагрузка по дням недели: воскресенье тяжелее обычного дня", () => {
  // 23 ноября 2026 — понедельник, значит 29 ноября — воскресенье.
  // Срок специально свободный: при тесном сроке всё упирается в «успеть до
  // экзамена», и веса дней уже не главное.
  const d = makeDisc(20);
  d.plan = Object.assign(planner.defaultPlan("2026-11-24", "2027-01-20"), {
    dayLoad: [2, 1, 1, 1, 1, 1, 1]
  });
  const r = planner.buildDisciplinePlan(d, settings, "2026-11-24");
  const minutesOn = (date) => (r.days[date] || []).reduce((n, it) => n + it.minutes, 0);
  const days = Object.keys(r.days);
  const sundays = days.filter((x) => planner.weekday(x) === 0);
  assert.ok(sundays.length > 0, "воскресенья пропали из плана");
  const sunAvg = sundays.reduce((n, x) => n + minutesOn(x), 0) / sundays.length;
  const allAvg = days.reduce((n, x) => n + minutesOn(x), 0) / days.length;
  assert.ok(
    sunAvg > allAvg * 1.4,
    "воскресенье не тяжелее обычного дня: " + sunAvg.toFixed(1) + " против " + allAvg.toFixed(1)
  );
});

test("при тесном сроке программа честно говорит, что не помещается", () => {
  // Раньше в этом случае дневной потолок вообще не работал (умножение на дату
  // давало NaN), и всё «влезало» за счёт перегруженных дней.
  const d = makeDisc(20);
  d.plan = Object.assign(planner.defaultPlan("2026-11-24", "2026-12-06"), {
    dayLoad: [2, 1, 1, 1, 1, 1, 1],
    passes: 1
  });
  const r = planner.buildDisciplinePlan(d, settings, "2026-11-24");
  const firsts = Object.values(r.days).reduce((n, items) => n + items.filter((i) => i.pass === 1).length, 0);
  assert.strictEqual(firsts, 20, "не все вопросы получили первое чтение: " + firsts);
  // Каждый день не должен выходить далеко за норму.
  const perDay = r.stats.perDayMinutes;
  const heaviest = Math.max(...Object.values(r.days).map((i) => i.reduce((n, x) => n + x.minutes, 0)));
  assert.ok(
    heaviest <= perDay * 2.2 || heaviest < 25,
    "самый тяжёлый день " + heaviest.toFixed(1) + " мин против нормы " + perDay.toFixed(1)
  );
});

test("день недели с нагрузкой 0 становится выходным", () => {
  const d = makeDisc(20);
  d.plan = Object.assign(planner.defaultPlan("2026-11-24", "2026-12-06"), {
    dayLoad: [0, 1, 1, 1, 1, 1, 1],
    restDays: []
  });
  const r = planner.buildDisciplinePlan(d, settings, "2026-11-24");
  const sundays = Object.keys(r.days).filter((x) => planner.weekday(x) === 0);
  for (const x of sundays) {
    assert.strictEqual((r.days[x] || []).length, 0, "в воскресенье " + x + " стоит работа");
  }
});

test("план покрывает весь объём за нужное число прогонов", () => {
  const d = makeDisc(20, { words: 600 });
  d.plan.passes = 3;
  const r = planner.buildDisciplinePlan(d, settings, "2026-11-24");
  let minutes = 0;
  let count = 0;
  for (const items of Object.values(r.days)) {
    for (const it of items) {
      minutes += it.minutes;
      count++;
    }
  }
  assert.strictEqual(count, 60, "должно быть 20 вопросов × 3 прогона = 60 записей, а есть " + count);
  assert.ok(Math.abs(minutes - r.stats.minutesLeft) < 0.5, "минуты не сходятся: " + minutes + " vs " + r.stats.minutesLeft);
  assert.strictEqual(r.stats.leftQuestions, 0, "не все вопросы получили первое чтение");
  assert.strictEqual(r.stats.behind, false);
});

test("каждый первый прогон раньше своих повторений", () => {
  const d = makeDisc(8, { words: 500 });
  d.plan.passes = 3;
  const r = planner.buildDisciplinePlan(d, settings, "2026-11-24");
  const passes = {};
  for (const [date, items] of Object.entries(r.days)) {
    for (const it of items) {
      if (!passes[it.qIndex]) passes[it.qIndex] = {};
      passes[it.qIndex][it.pass] = date;
    }
  }
  for (const [q, p] of Object.entries(passes)) {
    assert.ok(p[1], "у вопроса " + q + " нет первого чтения");
    if (p[2]) assert.ok(p[1] < p[2], "вопрос " + q + ": повтор раньше первого чтения");
    if (p[3]) assert.ok(p[2] < p[3], "вопрос " + q + ": третий прогон раньше второго");
  }
});

test("ничего не планируется после экзамена", () => {
  const d = makeDisc(10, { words: 400, exam: "2026-12-10" });
  const r = planner.buildDisciplinePlan(d, settings, "2026-11-24");
  for (const date of Object.keys(r.days)) {
    assert.ok(date <= "2026-12-10", "работа после экзамена: " + date);
  }
});

test("дата начала в будущем сдвигает план", () => {
  const d = makeDisc(5, { words: 300 });
  d.plan.startDate = "2026-12-01";
  const r = planner.buildDisciplinePlan(d, settings, "2026-11-24");
  const dates = Object.keys(r.days).filter((k) => r.days[k].length);
  assert.ok(dates.length > 0, "план пуст");
  assert.ok(dates.sort()[0] >= "2026-12-01", "работа началась раньше даты начала: " + dates[0]);
});

test("отметка прочитанного уменьшает остаток", () => {
  const d = makeDisc(10, { words: 500 });
  d.plan.passes = 2;
  const before = planner.remainingMinutes(d, settings);
  d.reads = { 0: ["2026-11-24"] };
  const after = planner.remainingMinutes(d, settings);
  assert.ok(after < before, "остаток не уменьшился");
  assert.ok(before - after > 0.5, "уменьшение слишком маленькое");
});

test("вопрос без ответа оценивается по средней длине", () => {
  const src = [
    "1. Первый вопрос",
    "Ответ: Развёрнутый ответ на сто слов. ".repeat(10),
    "",
    "2. Второй вопрос",
    "Ответ: Ещё один развёрнутый ответ. ".repeat(10),
    "",
    "3. Третий вопрос"
  ].join("\n");
  const r = parser.parseDocument(src);
  assert.strictEqual(r.count, 3);
  assert.strictEqual(r.answeredCount, 2);
  assert.ok(r.warnings.some((w) => w.type === "partial-answers"), "нет предупреждения");
  assert.ok(r.questions[2].aWords > 0, "оценка не подставилась");
});

test("режим «по вопросам» ставит не больше заданного в день", () => {
  const d = makeDisc(30, { words: 400 });
  d.plan.mode = "questions";
  d.plan.perDayQuestions = 2;
  d.plan.passes = 1;
  const r = planner.buildDisciplinePlan(d, settings, "2026-11-24");
  for (const [date, items] of Object.entries(r.days)) {
    const newOnDay = items.filter((i) => i.pass === 1).length;
    assert.ok(newOnDay <= 2, date + ": новых вопросов " + newOnDay);
  }
});

test("экзамен в прошлом — понятная ошибка, а не пустой экран", () => {
  const d = makeDisc(5, { words: 200, exam: "2026-01-01" });
  const r = planner.buildDisciplinePlan(d, settings, "2026-11-24");
  assert.ok(r.warnings.some((w) => w.type === "exam-passed"), "нет предупреждения о дате");
  assert.strictEqual(Object.keys(r.days).length, 0);
});

test("перегрузка обнаруживается: мало дней на много объёма", () => {
  const d = makeDisc(150, { words: 1500, exam: "2026-11-27" });
  d.plan.passes = 3;
  const r = planner.buildDisciplinePlan(d, settings, "2026-11-24");
  assert.ok(r.stats.perDayMinutes > 150, "нагрузка не распознана: " + r.stats.perDayMinutes);
  assert.ok(r.warnings.some((w) => w.type === "overload"), "нет предупреждения о перегрузке");
});

test("общий бюджет делит время между дисциплинами", () => {
  const s = planner.normalizeSettings({ wordsPerMinute: 150, globalDailyMinutes: 60 });
  const d1 = makeDisc(20, { words: 500 });
  const d2 = makeDisc(20, { words: 500 });
  d2.id = "d2";
  const res = planner.computeAll({ settings: s, disciplines: [d1, d2] }, "2026-11-24");
  const first5 = Object.keys(res.dayTotals).sort().slice(0, 5);
  const values = first5.map((k) => res.dayTotals[k]);
  for (const v of values) {
    assert.ok(v <= 90, "день сильно превышает бюджет: " + v);
  }
  // Работа идёт по обеим дисциплинам, а не только по первой.
  const discsToday = new Set();
  for (const day of first5) {
    for (const t of res.combined[day] || []) discsToday.add(t.discId);
  }
  assert.strictEqual(discsToday.size, 2, "в работе не обе дисциплины: " + Array.from(discsToday));
});

test("у дисциплины может быть своя скорость чтения", () => {
  const d = makeDisc(5, { words: 600 });
  const base = planner.totalMinutes(d, settings);
  d.reading = { wordsPerMinute: 75 };
  const slower = planner.totalMinutes(d, settings);
  assert.ok(Math.abs(slower - base * 2) < 0.5, "вдвое медленнее — вдвое дольше: " + base + " → " + slower);
  d.reading = { wordsPerMinute: 300 };
  const faster = planner.totalMinutes(d, settings);
  assert.ok(Math.abs(faster - base / 2) < 0.5, "вдвое быстрее — вдвое короче: " + base + " → " + faster);
  // Своя скорость не должна влиять на другие дисциплины.
  const other = makeDisc(5, { words: 600 });
  other.id = "d2";
  assert.ok(Math.abs(planner.totalMinutes(other, settings) - base) < 0.01, "чужая скорость протекла");
});

test("своя скорость в знаках тоже работает", () => {
  const d = makeDisc(4, { words: 500 });
  d.reading = { unit: "cpm", charsPerMinute: 1200 };
  const asChars = planner.totalMinutes(d, settings);
  // 4 вопроса × 500 слов ≈ 12 000 знаков × 3 прогона с коэффициентом 1,5.
  const expected = ((500 * 6.2) / 1200) * (1 + 1 / 1.5 + 1 / 1.5) * 4;
  assert.ok(Math.abs(asChars - expected) < 2, "знаки считаются не так: " + asChars + " vs " + expected.toFixed(1));
});

test("дисциплина без своей скорости берёт общую", () => {
  const d = makeDisc(3, { words: 400 });
  const a = planner.totalMinutes(d, settings);
  d.reading = {};
  assert.ok(Math.abs(planner.totalMinutes(d, settings) - a) < 0.01, "пустая настройка изменила время");
});

test("repeated passes get shorter (review faster)", () => {
  const d = makeDisc(5, { words: 500 });
  const m1 = planner.questionMinutes(d, d.questions[0], 1, settings);
  const m2 = planner.questionMinutes(d, d.questions[0], 2, settings);
  assert.ok(m2 < m1, "повторное чтение должно быть быстрее");
  assert.ok(Math.abs(m2 - m1 / 1.5) < 0.01, "коэффициент повторения не применён");
});

test("прогресс считается по всем прогонам", () => {
  const d = makeDisc(10, { words: 300 });
  d.plan.passes = 2;
  assert.strictEqual(planner.completion(d, settings), 0);
  d.reads = { 0: ["2026-11-24"] };
  assert.ok(Math.abs(planner.completion(d, settings) - 0.05) < 1e-9, "прогресс: " + planner.completion(d, settings));
  const all = {};
  for (let i = 0; i < 10; i++) all[i] = ["2026-11-24", "2026-11-25"];
  d.reads = all;
  assert.ok(Math.abs(planner.completion(d, settings) - 1) < 1e-9, "полный прогресс не 1");
});

test("день недели считается верно", () => {
  // 24 ноября 2026 — вторник (2).
  assert.strictEqual(planner.weekday("2026-11-24"), 2);
  assert.strictEqual(planner.weekday("2026-11-29"), 0);
});

// =====================================================================
//  Файлы
// =====================================================================

console.log("\nЧтение файлов");

test("кодировка Windows-1251 определяется", () => {
  const iconv = require("iconv-lite");
  const buf = iconv.encode("Вопрос 1. Что такое полиция?", "win1251");
  const r = decoder.decodeBuffer(buf);
  assert.strictEqual(r.encoding, "windows-1251");
  assert.ok(r.text.indexOf("Что такое полиция") > -1, "текст не декодирован: " + r.text);
});

test("UTF-8 с BOM читается", () => {
  const buf = Buffer.concat([Buffer.from([0xef, 0xbb, 0xbf]), Buffer.from("Вопрос 1. Тест", "utf-8")]);
  const r = decoder.decodeBuffer(buf);
  assert.strictEqual(r.encoding, "utf-8-bom");
  assert.strictEqual(r.text, "Вопрос 1. Тест");
});

test("UTF-16LE с BOM читается", () => {
  const iconv = require("iconv-lite");
  const buf = Buffer.concat([Buffer.from([0xff, 0xfe]), iconv.encode("Вопрос 1. Тест", "utf-16le")]);
  const r = decoder.decodeBuffer(buf);
  assert.strictEqual(r.encoding, "utf-16le");
  assert.strictEqual(r.text, "Вопрос 1. Тест");
});

test("мелкая нумерация внутри ответа не режет вопрос", () => {
  const src = [
    "1. Что входит в обязанности полиции?",
    "Ответ:",
    "1. принимать заявления;",
    "2. обеспечивать порядок;",
    "",
    "2. Что такое полиция?",
    "Ответ: орган внутренних дел."
  ].join("\n");
  const r = parser.parseDocument(src);
  // Формат неоднозначный: «2.» внутри ответа неотличимо от начала вопроса.
  // Главное — первый вопрос не остаётся без ответа молча, а получает предупреждение.
  assert.ok(r.count >= 2, "вопросы потерялись");
  assert.ok(
    r.questions[0].answer.indexOf("принимать заявления") > -1 ||
      r.warnings.some((w) => w.type === "sublist-answers"),
    "нет ни ответа, ни предупреждения"
  );
});

test("текст Word (docx XML) превращается в строки", () => {
  const xml =
    '<w:document><w:body><w:p><w:r><w:t>Вопрос 1. Что такое полиция?</w:t></w:r></w:p>' +
    "<w:p><w:r><w:t>Ответ: орган внутренних дел.</w:t></w:r></w:p></w:body></w:document>";
  const out = docx.wordXmlToText(xml);
  assert.ok(out.indexOf("Вопрос 1") > -1, "нет вопроса: " + out);
  assert.ok(out.indexOf("\n") > -1, "нет перевода строки между абзацами");
});

test("сущности XML раскодируются", () => {
  const xml = "<w:p><w:r><w:t>А &amp; Б &lt;тест&gt;</w:t></w:r></w:p>";
  const out = docx.wordXmlToText(xml);
  assert.ok(out.indexOf("А & Б <тест>") > -1, "не раскодировано: " + out);
});

// =====================================================================
//  Итог
// =====================================================================

console.log("\n---");
if (failed) {
  console.log("Провалено: " + failed + ", пройдено: " + passed);
  for (const f of failures) {
    console.log("\n[" + f.name + "]\n" + (f.err.stack || f.err.message));
  }
  process.exitCode = 1;
} else {
  console.log("Всё пройдено: " + passed + " проверок.");
}
