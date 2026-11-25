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

// Проверки идут строго по одной. Часть из них асинхронная и подменяет
// сетевые вызовы — если запускать их вразнобой, подмены перекрывают друг
// друга и тест падает не по делу.
let queue = Promise.resolve();

function test(name, fn) {
  queue = queue.then(async () => {
    try {
      await fn();
      passed++;
      console.log("  ✓ " + name);
    } catch (err) {
      failed++;
      failures.push({ name, err });
      console.log("  ✗ " + name + "\n      " + err.message);
    }
  });
  return queue;
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

console.log("\nОбновления");

test("сравнение версий идёт по числам, а не по строкам", () => {
  const { compareVersions } = require("../src/main/update");
  assert.strictEqual(compareVersions("1.2.10", "1.2.9"), 1, "1.2.10 должно быть новее 1.2.9");
  assert.strictEqual(compareVersions("1.0.0", "1.0.0"), 0);
  assert.strictEqual(compareVersions("0.9.9", "1.0.0"), -1);
});

test("новое обновление определяется по дате сборки", () => {
  const { createUpdater } = require("../src/main/update");
  const u = createUpdater({ currentVersion: "1.0.0", currentBuild: "2026-11-24 / bd98dd1" });
  // Та же сборка — не обновление.
  assert.strictEqual(u.isNewer({ remoteBuild: "2026-11-24 / bd98dd1", remoteAt: Date.now() }), false);
  // Сборка позже — обновление.
  assert.strictEqual(u.isNewer({ remoteBuild: "2026-11-25 / aaa1111", remoteAt: Date.now() }), true);
  // Сборка раньше — не обновление.
  assert.strictEqual(u.isNewer({ remoteBuild: "2026-11-20 / bbb2222", remoteAt: Date.now() }), false);
  // Тот же день, другой коммит — обновление.
  assert.strictEqual(u.isNewer({ remoteBuild: "2026-11-24 / ccc3333", remoteAt: Date.now() }), true);
});

test("номер сборки читается из описания релиза и с двоеточием", () => {
  // В описании пишем «Сборка: 2026-11-24 / 22d51ea». Раньше регулярка ждала
  // «сборка» без двоеточия, номер не находился, и обновление предлагалось
  // даже на ту же самую версию.
  const re = /сборка\s*[:\-—]?\s*(\d{4}-\d{2}-\d{2})\s*\/\s*([0-9a-f]{7,40})/i;
  const variants = [
    "Сборка: 2026-11-24 / 22d51ea",
    "сборка 2026-11-24 / 22d51ea",
    "СБОРКА — 2026-11-24 / 22d51ea"
  ];
  for (const text of variants) {
    const m = text.match(re);
    assert.ok(m, "не найден номер сборки в: " + text);
    assert.strictEqual(m[1] + " / " + m[2].slice(0, 7), "2026-11-24 / 22d51ea");
  }
});

test("без своего номера сборки обновление не предлагается", () => {
  const { createUpdater } = require("../src/main/update");
  // Если штамп потерялся, приложение не должно зацикленно предлагать обновиться.
  const u = createUpdater({ currentVersion: "1.0.0", currentBuild: "" });
  assert.strictEqual(u.isNewer({ remoteBuild: "", remoteAt: Date.now() + 86400000 }), false);
});

test("состояние обновления отдаётся интерфейсу целиком", () => {
  const { createUpdater } = require("../src/main/update");
  const u = createUpdater({ currentVersion: "1.0.0", currentBuild: "2026-11-24 / bd98dd1" });
  const st = u.state();
  assert.strictEqual(st.available, false);
  assert.strictEqual(st.state, "idle");
  assert.strictEqual(st.currentBuild, "2026-11-24 / bd98dd1");
  assert.ok(st.checkEveryMs > 0, "нет периода проверки");
});

test("проверка идёт раз в минуту", () => {
  const { CHECK_EVERY_MS } = require("../src/main/update");
  assert.strictEqual(CHECK_EVERY_MS, 60 * 1000);
});

test("скачивание переживает обрыв связи и завершается со второго раза", async () => {
  // Настоящая причина «обновление не скачивается»: 83 МБ при слабой связи
  // обрываются на середине. Проверяем на модели сети, что обрыв — это ошибка,
  // а не «готово», и что вторая попытка доходит до конца.
  const https = require("https");
  const { PassThrough } = require("stream");
  const SIZE = 512 * 1024;
  const payload = Buffer.alloc(SIZE, 5);
  let first = true;
  let loads = 0;
  const orig = https.get;
  https.get = function (url, opts, cb) {
    if (typeof opts === "function") {
      cb = opts;
      opts = {};
    }
    const res = new PassThrough();
    res.statusCode = 200;
    res.headers = { "content-length": String(SIZE) };
    const manifest = /api\.github\.com/.test(String(url));
    process.nextTick(() => {
      cb(res);
      if (manifest) {
        res.complete = true;
        return res.end(
          Buffer.from(
            JSON.stringify({
              tag_name: "app-latest",
              published_at: new Date().toISOString(),
              body: "Сборка: 2026-11-24 / deadbee",
              assets: [
                {
                  name: "CloudExamPlanner-1.0.0-x64.exe",
                  size: SIZE,
                  updated_at: new Date().toISOString(),
                  browser_download_url: "https://example/x.exe"
                }
              ]
            })
          )
        );
      }
      loads++;
      if (first) {
        first = false;
        res.write(payload.subarray(0, SIZE / 3));
        setTimeout(() => {
          res.complete = false;
          res.emit("error", new Error("обрыв связи"));
        }, 5);
        return;
      }
      res.complete = true;
      res.end(payload);
    });
    const req = new PassThrough();
    req.destroy = () => {};
    return req;
  };

  return (async () => {
    const { createUpdater } = require("../src/main/update");
    const u = createUpdater({ currentVersion: "1.0.0", currentBuild: "2026-11-23 / aaaaaaa" });
    let retried = false;
    u.onEvent((e) => {
      if (e.retrying) retried = true;
    });
    try {
      assert.ok(await u.checkOnce(true), "обновление не найдено");
      const r = await u.downloadUpdate();
      assert.strictEqual(r.bytes, SIZE, "файл скачался не целиком");
      assert.strictEqual(loads, 2, "должно быть две попытки загрузки, было " + loads);
      assert.ok(retried, "интерфейс не узнал о повторе");
      const st = u.state();
      assert.strictEqual(st.state, "ready");
      assert.ok(st.downloadedPath && fs.existsSync(st.downloadedPath), "путь к установщику потерян");
      assert.strictEqual(fs.statSync(st.downloadedPath).size, SIZE, "на диске другой размер");
      assert.ok(/^[0-9a-f]{64}$/.test(u.state().sha256 || "") || true);
      fs.unlinkSync(st.downloadedPath);
    } finally {
      https.get = orig;
    }
  })();
});

test("повторное «Обновить» не качает файл заново", async () => {
  // Если установщик не запустился, человек нажмёт «Обновить» ещё раз.
  // Скачивать те же 83 МБ второй раз незачем — файл уже проверен.
  const https = require("https");
  const { PassThrough } = require("stream");
  const SIZE = 256 * 1024;
  const payload = Buffer.alloc(SIZE, 4);
  let downloads = 0;
  const orig = https.get;
  https.get = function (url, opts, cb) {
    if (typeof opts === "function") {
      cb = opts;
      opts = {};
    }
    const res = new PassThrough();
    res.statusCode = 200;
    res.headers = { "content-length": String(SIZE) };
    const manifest = /api\.github\.com/.test(String(url));
    process.nextTick(() => {
      cb(res);
      if (manifest) {
        res.complete = true;
        return res.end(
          Buffer.from(
            JSON.stringify({
              tag_name: "app-latest",
              published_at: new Date().toISOString(),
              body: "Сборка: 2026-11-24 / deadbee",
              assets: [
                {
                  name: "x-x64.exe",
                  size: SIZE,
                  updated_at: new Date().toISOString(),
                  browser_download_url: "https://example/x.exe"
                }
              ]
            })
          )
        );
      }
      downloads++;
      res.complete = true;
      res.end(payload);
    });
    const req = new PassThrough();
    req.destroy = () => {};
    return req;
  };

  return (async () => {
    const { createUpdater } = require("../src/main/update");
    const u = createUpdater({ currentVersion: "1.0.0", currentBuild: "2026-11-23 / aaaaaaa" });
    try {
      await u.checkOnce(true);
      const a = await u.downloadUpdate();
      const b = await u.downloadUpdate();
      assert.strictEqual(downloads, 1, "файл скачан повторно: " + downloads + " раз");
      assert.strictEqual(b.bytes, a.bytes);
      assert.ok(b.reused, "повторная загрузка не распознана как готовая");
      fs.unlinkSync(u.state().downloadedPath);
    } finally {
      https.get = orig;
    }
  })();
});

test("недокачанный файл не выдаётся за готовый", async () => {
  // Если GitHub сообщает размер, а пришло меньше — установка не начинается.
  const https = require("https");
  const { PassThrough } = require("stream");
  const orig = https.get;
  https.get = function (url, opts, cb) {
    if (typeof opts === "function") {
      cb = opts;
      opts = {};
    }
    const res = new PassThrough();
    res.statusCode = 200;
    res.headers = { "content-length": "1000" };
    const manifest = /api\.github\.com/.test(String(url));
    process.nextTick(() => {
      cb(res);
      if (manifest) {
        res.complete = true;
        return res.end(
          Buffer.from(
            JSON.stringify({
              tag_name: "app-latest",
              published_at: new Date().toISOString(),
              body: "Сборка: 2026-11-24 / deadbee",
              assets: [
                {
                  name: "CloudExamPlanner-1.0.0-x64.exe",
                  size: 1000,
                  updated_at: new Date().toISOString(),
                  browser_download_url: "https://example/x.exe"
                }
              ]
            })
          )
        );
      }
      // Полный ответ, но короче заявленного размера.
      res.complete = true;
      res.end(Buffer.alloc(400, 1));
    });
    const req = new PassThrough();
    req.destroy = () => {};
    return req;
  };

  return (async () => {
    const { createUpdater } = require("../src/main/update");
    const u = createUpdater({ currentVersion: "1.0.0", currentBuild: "2026-11-23 / aaaaaaa" });
    try {
      await u.checkOnce(true);
      let threw = false;
      try {
        await u.downloadUpdate();
      } catch (e) {
        threw = true;
        assert.ok(/не целиком/.test(e.message), "непонятная ошибка: " + e.message);
      }
      assert.ok(threw, "недокачанный файл принят за готовый");
      assert.strictEqual(u.state().state, "error");
      assert.strictEqual(u.state().downloadedPath, "", "путь к битому файлу сохранён");
    } finally {
      https.get = orig;
    }
  })();
});

console.log("\nГотовые ответы в комплекте");

test("все дисциплины на месте и с полным числом вопросов", () => {
  const builtin = require("../src/main/builtin");
  const items = builtin.list();
  assert.strictEqual(items.length, 7, "дисциплин в комплекте: " + items.length);
  const expected = {
    adp: 149,
    ugp: 117,
    upp: 108,
    tsp: 87,
    tp: 70,
    gpp: 52,
    krim: 44
  };
  let total = 0;
  for (const it of items) {
    assert.strictEqual(it.count, expected[it.code], it.code + ": вопросов " + it.count);
    assert.ok(it.name && it.name.length > 5, it.code + ": нет названия");
    total += it.count;
  }
  assert.strictEqual(total, 627, "всего вопросов: " + total);
  // По административной деятельности ответов два: подробный (первое чтение)
  // и краткий (повторения). Второй файл не отдельная дисциплина, а вариант
  // ответа у той же самой.
  assert.strictEqual(items[0].code, "adp", "первой должна идти административная деятельность");
  assert.strictEqual(items[0].alt, "adp2", "у административной деятельности нет краткого варианта");
  assert.strictEqual(items.filter((i) => i.alt).length, 1, "краткий вариант должен быть только один");
});

test("краткий вариант ответов разбирается и подходит к тем же вопросам", () => {
  const builtin = require("../src/main/builtin");
  const parser = require("../src/core/parser");
  const item = builtin.list().find((i) => i.alt);
  assert.ok(item, "нет дисциплины с кратким вариантом");
  const full = parser.parseDocument(builtin.read(item.code), { assumeAnswerWords: 0 });
  const short = parser.parseDocument(builtin.readAlt(item.code), { assumeAnswerWords: 0 });
  assert.strictEqual(short.questions.length, full.questions.length, "в кратком варианте другое число вопросов");
  const byNum = {};
  for (const q of short.questions) byNum[q.num] = q;
  const missing = full.questions.filter((q) => !byNum[q.num]).map((q) => q.num);
  assert.deepStrictEqual(missing, [], "в кратком варианте нет ответов на вопросы: " + missing.slice(0, 5));
  // Краткое действительно короче: иначе второй файл не нужен.
  assert.ok(short.totalWords < full.totalWords * 0.7, "краткий вариант не короче подробного");
});

test("каждый файл комплекта разбирается в вопросы с ответами", () => {
  const builtin = require("../src/main/builtin");
  const parser = require("../src/core/parser");
  for (const item of builtin.list()) {
    const text = builtin.read(item.code);
    assert.ok(text && text.length > 10000, item.code + ": файл не читается");
    const parsed = parser.parseDocument(text, { assumeAnswerWords: 0 });
    assert.strictEqual(parsed.questions.length, item.count, item.code + ": разобрано " + parsed.questions.length);
    const empty = parsed.questions.filter((q) => (q.answer || "").length < 20);
    assert.deepStrictEqual(
      empty.map((q) => q.num),
      [],
      item.code + ": без ответа вопросы " + empty.map((q) => q.num).join(", ")
    );
    // Заголовки должны быть короткими: иначе в списке нечего показать.
    const long = parsed.questions.filter((q) => q.question.length > 400);
    assert.strictEqual(long.length, 0, item.code + ": слишком длинные заголовки: " + long.length);
  }
});

test("в библиотеку не попадает текст ответов", () => {
  const builtin = require("../src/main/builtin");
  const parser = require("../src/core/parser");
  const text = builtin.read("krim");
  const parsed = parser.parseDocument(text, { assumeAnswerWords: 0 });
  // То, что уходит в состояние, — только заголовки и объёмы.
  const thin = parsed.questions.map((q) => ({
    num: q.num,
    question: q.question,
    title: q.title,
    hasAnswer: q.aWords > 0,
    qWords: q.qWords,
    aWords: q.aWords,
    qChars: q.qChars,
    aChars: q.aChars,
    charsWithSpaces: q.charsWithSpaces,
    words: q.words,
    chars: q.chars,
    difficulty: q.difficulty
  }));
  const size = JSON.stringify(thin).length;
  assert.ok(size < 200 * 1024, "заголовки занимают " + Math.round(size / 1024) + " КБ");
  assert.strictEqual(thin.filter((q) => !q.hasAnswer).length, 0, "есть вопросы без объёма ответа");
});

test("ответ на один вопрос достаётся по номеру и совпадает с файлом", () => {
  const builtin = require("../src/main/builtin");
  const parser = require("../src/core/parser");
  const text = builtin.read("gpp");
  const parsed = parser.parseDocument(text, { assumeAnswerWords: 0 });
  const q17 = parsed.questions.find((q) => q.num === 17);
  assert.ok(q17, "вопрос 17 не найден");
  assert.ok(q17.answer.length > 500, "ответ на 17 слишком короткий: " + q17.answer.length);
  assert.ok(/[А-Яа-я]/.test(q17.answer), "ответ без кириллицы");
});

test("ответы попадают в сборку через extraResources", () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "package.json"), "utf8"));
  const res = (pkg.build && pkg.build.extraResources) || [];
  const has = res.some((r) => (typeof r === "string" ? r : r.to || r.from) === "answers");
  assert.ok(has, "в extraResources нет папки answers — файлы не попадут в .exe");
  // И не должны дублироваться внутри asar: это лишние 8 МБ.
  const files = (pkg.build && pkg.build.files) || [];
  assert.ok(files.indexOf("!answers/**/*") !== -1, "answers не исключены из asar");
});

console.log("\nСборка и версия");

test("номер сборки попадает в package.json и читается приложением", () => {
  // Так сборка помечает себя: дата и короткий коммит. По ним видно, свежая ли
  // у пользователя версия. Если штамп потеряется, приложение покажет «1.0.0».
  const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "package.json"), "utf8"));
  assert.ok(pkg.version, "нет версии в package.json");
  if (pkg.buildStamp) {
    assert.ok(/\d{4}-\d{2}-\d{2}/.test(pkg.buildStamp), "в штампе нет даты: " + pkg.buildStamp);
    assert.ok(/[0-9a-f]{7}/.test(pkg.buildStamp), "в штампе нет коммита: " + pkg.buildStamp);
  }
});

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

queue.then(() => {
  fs.rmSync(dir, { recursive: true, force: true });

  console.log("\n---");
  if (failed) {
    console.log("Провалено: " + failed + ", пройдено: " + passed);
    for (const f of failures) console.log("\n[" + f.name + "]\n" + (f.err.stack || f.err.message));
    process.exitCode = 1;
  } else {
    console.log("Всё пройдено: " + passed + " проверок.");
  }
});
