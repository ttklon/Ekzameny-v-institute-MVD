/*
 * parser.js — универсальный приёмник файлов «вопрос — ответ».
 *
 * Задача: принять почти любой текстовый файл с вопросами и ответами (перечень
 * вопросов, «все ответы» одним файлом, docx, выгрузка из PDF, конспект) и
 * разложить его на вопросы с ответами и статистикой.
 *
 * Порядок распознавания (первое сработавшее правило побеждает):
 *   1. Заголовки «# Вопрос 12. …» (markdown, так устроены текстовые исходники ответов);
 *   2. Строки «Вопрос 12. …», «ВОПРОС № 12:», «Билет 12», «Question 12»;
 *   3. Нумерованный список «12. …» / «12) …» с явными маркерами ответа («Ответ:»);
 *   4. Нумерованный список без маркеров ответа — тогда вопрос = первый абзац
 *      блока, ответ = остальные абзацы (типичный «Все ответы 001–149»);
 *   5. Строки-вопросы, заканчивающиеся «?» — ответ до следующего вопроса;
 *   6. Абзацы через пустую строку (последняя попытка: чётные — вопросы, нечётные — ответы).
 *
 * Всё, что не удалось распознать, не теряется: возвращается предупреждение и
 * исходный текст остаётся в файле.
 */
(function (root, factory) {
  const deps =
    typeof module !== "undefined" && module.exports
      ? { text: require("./text") }
      : { text: (root.ExamCore || {}).text };
  const api = factory(deps.text);
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof window !== "undefined") {
    window.ExamCore = Object.assign(window.ExamCore || {}, { parser: api });
  }
})(typeof self !== "undefined" ? self : this, function (text) {
  "use strict";

  const t = text;

  // ---------- Регулярные выражения распознавания ----------

  // «# Вопрос 12. Текст» / «## Вопрос 12)» / «### Задача 3»
  const MD_Q_RE = /^(#{1,4})\s*(вопрос|билет|задача|задание|тема|question|problem)\s*№?\s*(\d{1,4})\s*[.):\-—]?\s*(.*)$/i;
  // «Вопрос 12. Текст» (без решётки)
  const PLAIN_Q_RE = /^(вопрос|билет|задача|задание|question|problem)\s*№?\s*(\d{1,4})\s*[.):\-—]?\s+(.*)$/i;
  // «12. Текст» / «12) Текст» / «12 — Текст»
  const NUM_Q_RE = /^\s*(\d{1,4})\s*[.)]\s*(?=\S)(.{2,}?)\s*$/;
  // Явный маркер ответа: «Ответ:», «Ответ.», «ОТВЕТ», «Answer:», «Решение:»
  const ANSWER_RE = /^\s*[*_>#\s]*(ответ|answer|решение|разбор)\s*[*_]*\s*[:.\-—]\s*(.*)$/i;
  // Явный маркер конца ответа/начала примечания: «Литература», «Источник»
  const ANSWER_ONLY_RE = /^\s*[*_>#\s]*(ответ|answer|решение|разбор)\s*[*_]*\s*$/i;
  const NOISE_LINE_RE = /^\s*(стр\.?\s*\d+|\d+\s*из\s*\d+|page\s*\d+(\s*of\s*\d+)?|\d{1,4})\s*$/i;

  const MAX_QUESTIONS = 2000;
  const TITLE_MAX = 240;

  function isBlank(s) {
    return !s || !s.trim();
  }

  /** Есть ли в строке буква (а не только цифры и знаки). */
  function hasLetter(s) {
    return /[A-Za-z\u0400-\u04FF\u00C0-\u024F]/.test(s);
  }

  /** Убирает разметку для подсчёта и для краткого заголовка. */
  function stripMarkup(s) {
    return String(s || "")
      .replace(/^#{1,4}\s*/, "")
      .replace(/^>\s*/, "")
      .replace(/\*\*|__|\/\/|`/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  /** Краткий заголовок вопроса: первая фраза, до 240 знаков. */
  function shortTitle(s) {
    const clean = stripMarkup(s)
      .replace(/^\s*(\d{1,4})\s*[.)]\s*/, "")
      .replace(/^\s*(вопрос|билет|задача|задание|question)\s*№?\s*\d{1,4}\s*[.):\-—]?\s*/i, "");
    if (!clean) return "";
    if (clean.length <= TITLE_MAX) return clean;
    // Обрезаем по границе предложения, если она близко, иначе по слову.
    const cut = clean.slice(0, TITLE_MAX);
    const dot = Math.max(cut.lastIndexOf(". "), cut.lastIndexOf("? "), cut.lastIndexOf("! "));
    if (dot > TITLE_MAX * 0.5) return cut.slice(0, dot + 1);
    const sp = cut.lastIndexOf(" ");
    return (sp > 0 ? cut.slice(0, sp) : cut) + "…";
  }

  // ---------- Сбор блоков ----------

  /**
   * Находит начала вопросов по заданному правилу.
   * Возвращает массив { line, number, rest } — номер строки, номер вопроса и остаток строки.
   */
  function findStarts(lines, rule) {
    const out = [];
    const RES = {
      md: [MD_Q_RE, 3, 4],
      plain: [PLAIN_Q_RE, 2, 3],
      num: [NUM_Q_RE, 1, 2]
    };
    const spec = RES[rule];
    if (!spec) return out;
    const re = spec[0];
    const numGroup = spec[1];
    const restGroup = spec[2];

    let lastNum = 0;
    let gaps = 0;
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      if (line.length > 600 && rule === "num") continue; // не маркер, а длинная строка
      const m = line.match(re);
      if (!m) continue;
      const rest = (m[restGroup] || "").trim();
      // Мусор: пустой остаток, только цифры/знаки, нет букв.
      if (!hasLetter(rest) || rest.length < 3) continue;
      // Строка «5. 6.» и подобные — нумерация списка, а не вопрос.
      if (/^\d{1,4}\s*[.)]?$/.test(rest)) continue;
      const num = parseInt(m[numGroup], 10);
      if (!isFinite(num) || num < 1) continue;
      if (rule === "num") {
        // Правило нумерации: новый вопрос — это либо следующий номер подряд,
        // либо (для второго перечня в файле) снова «1.» после пустой строки.
        // Пункты «1. …», «2. …» внутри ответа так отсекаются.
        let before = i - 1;
        while (before >= 0 && !lines[before].trim()) before--;
        const blankBefore = before !== i - 1;
        const isNext = out.length > 0 && num === lastNum + 1;
        const isRestart = out.length > 0 && num === 1 && blankBefore;
        // Файл начинается не с «1.» — первый пункт принимаем всегда.
        if (out.length > 0 && !isNext && !isRestart) {
          if (!(num === lastNum && blankBefore)) continue;
        }
        // Совсем мелкие номера в середине текста — точно не вопрос.
        if (out.length > 0 && num < 2 && !blankBefore) continue;
      }
      lastNum = num;
      out.push({ line: i, number: num, rest });
      if (out.length > MAX_QUESTIONS * 2) break;
    }
    return out;
  }

  /** Похоже ли на нумерованный список вопросов: номера идут подряд и их достаточно много. */
  function looksSequential(starts) {
    if (starts.length < 3) return false;
    let seq = 0;
    for (let i = 1; i < starts.length; i++) {
      if (starts[i].number === starts[i - 1].number + 1) seq++;
    }
    return seq / (starts.length - 1) >= 0.6;
  }

  /**
   * Самая длинная цепочка подряд идущих номеров (1, 2, 3 … 149).
   * Нумерованные пункты внутри ответа (1, 2, 3 — и снова 1, 2, 3) в неё не попадут:
   * перезапуск нумерации обрывает цепочку. Так «Все ответы» не путается с перечнем норм.
   */
  function longestSequentialRun(starts) {
    if (!starts.length) return [];
    let best = [];
    let run = [starts[0]];
    for (let i = 1; i < starts.length; i++) {
      const prev = run[run.length - 1];
      const cur = starts[i];
      if (cur.number === prev.number + 1 || (cur.number === prev.number && prev.number > 1)) {
        run.push(cur);
      } else {
        if (run.length > best.length) best = run;
        run = [cur];
      }
    }
    if (run.length > best.length) best = run;
    return best;
  }

  /** Есть ли в документе явные маркеры «Ответ:». */
  function hasAnswerMarkers(lines) {
    let n = 0;
    for (let i = 0; i < lines.length; i++) {
      if ((ANSWER_RE.test(lines[i]) && lines[i].trim().length < 400) || ANSWER_ONLY_RE.test(lines[i])) {
        n++;
        if (n >= 2) return true;
      }
    }
    return false;
  }

  /**
   * Разбирает блоки между началами вопросов.
   * blockLines — строки блока (без строки-маркера).
   */
  function splitQuestionAnswer(rest, blockLines, useAnswerMarker) {
    let question = rest;
    let answerLines = [];
    let seenAnswer = false;
    let firstParClosed = false;

    if (useAnswerMarker) {
      // Всё до маркера «Ответ:» — продолжение вопроса, всё после — ответ.
      for (let i = 0; i < blockLines.length; i++) {
        const ln = blockLines[i];
        const m = ANSWER_RE.exec(ln);
        if (!seenAnswer && (ANSWER_ONLY_RE.test(ln) || (m && ln.trim().length < 400))) {
          seenAnswer = true;
          const tail = (m && m[2] ? m[2] : "").trim();
          if (tail) answerLines.push(tail);
          continue;
        }
        if (!seenAnswer) {
          question += " " + ln.trim();
        } else {
          answerLines.push(ln);
        }
      }
    } else {
      // Без маркера: вопрос — первый абзац, ответ — остальное.
      for (let i = 0; i < blockLines.length; i++) {
        const ln = blockLines[i];
        if (!firstParClosed) {
          if (isBlank(ln)) {
            firstParClosed = true;
            continue;
          }
          // Строка-заголовок раздела («## 1. …») — уже не вопрос.
          if (/^#{2,4}\s/.test(ln) || /^>\s/.test(ln)) {
            firstParClosed = true;
            answerLines.push(ln);
            continue;
          }
          question += " " + ln.trim();
        } else {
          answerLines.push(ln);
        }
      }
    }

    // Вопрос мог «разрастись»: если он длиннее двух предложений и в блоке есть
    // абзацы, значит первый абзац — это уже начало ответа. Оставляем первую фразу.
    const qClean = question.replace(/[ \t]+/g, " ").trim();
    const answerClean = answerLines.join("\n").replace(/[ \t]+/g, " ").trim();
    return { question: qClean, answer: answerClean };
  }

  /**
   * Первый абзац блока — вопрос, остальное — ответ (формат «Все ответы»).
   * Заголовки разделов, определения и пункты перечня — уже начало ответа.
   */
  function splitFirstParagraph(rest, blockLines) {
    let question = rest;
    const answerLines = [];
    let closed = false;
    for (let i = 0; i < blockLines.length; i++) {
      const ln = blockLines[i];
      if (!closed) {
        if (isBlank(ln)) {
          closed = true;
          continue;
        }
        // «Ответ: …» — вопрос закончился, дальше идёт ответ.
        const am = ANSWER_RE.exec(ln);
        if (am || ANSWER_ONLY_RE.test(ln)) {
          closed = true;
          const tail = (am && am[2] ? am[2] : "").trim();
          if (tail) answerLines.push(tail);
          continue;
        }
        if (/^#{1,4}\s/.test(ln) || /^>/.test(ln) || /^[-*•]\s/.test(ln)) {
          closed = true;
          answerLines.push(ln);
          continue;
        }
        question += " " + ln.trim();
      } else {
        answerLines.push(ln);
      }
    }
    return {
      question: question.replace(/[ \t]+/g, " ").trim(),
      answer: answerLines.join("\n").replace(/[ \t]+/g, " ").trim()
    };
  }

  /**
   * Убирает мусор от PDF: одинокие номера страниц и повторяющиеся колонтитулы.
   * Важно не выбросить настоящую нумерацию («12. Вопрос»): номер без текста
   * отбрасывается только на отдельной строке и только в окружении пустых строк.
   */
  function cleanPdfNoise(lines) {
    const counts = new Map();
    for (const ln of lines) {
      const s = ln.trim();
      if (s.length > 0 && s.length < 90) counts.set(s, (counts.get(s) || 0) + 1);
    }
    const repeated = new Set();
    for (const [s, n] of counts) {
      if (n >= 4 && !hasLetter(s)) repeated.add(s);
    }
    return lines.map((ln, i) => {
      const s = ln.trim();
      const isolated =
        (i === 0 || !lines[i - 1].trim()) && (i === lines.length - 1 || !lines[i + 1].trim());
      if (NOISE_LINE_RE.test(s) && isolated) return "";
      if (repeated.has(s) && i > 0 && i < lines.length - 1) return "";
      return ln;
    });
  }

  /** Собирает вопросы из найденных начал. */
  function buildFromStarts(lines, starts, opts) {
    const questions = [];
    let listNo = 1;
    let prevNum = 0;
    for (let s = 0; s < starts.length; s++) {
      const cur = starts[s];
      const nextLine = s + 1 < starts.length ? starts[s + 1].line : lines.length;
      // Перезапуск нумерации → второй перечень в том же файле.
      if (s > 0 && cur.number <= prevNum && cur.number <= 2) listNo++;
      prevNum = cur.number;

      const block = lines.slice(cur.line + 1, nextLine);
      const pair =
        opts.split === "first-paragraph"
          ? splitFirstParagraph(cur.rest, block)
          : splitQuestionAnswer(cur.rest, block, opts.useAnswerMarker);
      questions.push(makeQuestion(cur.number, pair.question, pair.answer, listNo));
      if (questions.length >= MAX_QUESTIONS) break;
    }
    return questions;
  }

  /**
   * Файл на один вопрос: начало документа — вопрос, всё остальное — ответ.
   * Так устроены исходники ответов (по файлу на вопрос), и это же спасает,
   * когда весь файл — один вопрос с большим ответом.
   */
  function buildSingle(lines, start) {
    if (!start) return [];
    // Заголовок вида «# Вопрос 45. …» — номер и текст берём из него.
    const num = start.number || 1;
    let question = start.rest || "";
    let bodyStart = start.line + 1;

    // Вопрос может занимать несколько строк до первой пустой строки.
    let i = bodyStart;
    while (i < lines.length) {
      const ln = lines[i];
      if (isBlank(ln) || /^#{1,4}\s/.test(ln) || /^>/.test(ln) || /^[-*•]\s/.test(ln)) break;
      if (question.length > 400) break;
      question += " " + ln.trim();
      i++;
    }
    const answer = lines.slice(i).join("\n").replace(/[ \t]+/g, " ").trim();
    return [makeQuestion(num, question, answer, 1)];
  }

  /**
   * Правило 5: строки-вопросы, заканчивающиеся «?».
   * Ответ — строки до следующей строки-вопроса.
   */
  function buildFromQuestionLines(lines) {
    const starts = [];
    let lastQ = -1;
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;
      const isQ =
        /\?\s*$/.test(line) &&
        line.length <= 400 &&
        hasLetter(line) &&
        !/^(ответ|answer)\b/i.test(line);
      if (isQ) {
        // Склеиваем вопрос, если предыдущие строки не закончили предложение.
        let q = line;
        let j = i - 1;
        let from = i;
        while (j > lastQ && lines[j] && lines[j].trim() && !/[.!?;:]\s*$/.test(lines[j].trim())) {
          q = lines[j].trim() + " " + q;
          from = j;
          j--;
        }
        starts.push({ line: i, number: starts.length + 1, rest: q, from });
        lastQ = i;
      }
    }
    if (starts.length < 2) return [];
    const questions = [];
    for (let s = 0; s < starts.length; s++) {
      const cur = starts[s];
      const nextLine = s + 1 < starts.length ? starts[s + 1].from : lines.length;
      const block = lines.slice(cur.line + 1, nextLine);
      const pair = splitQuestionAnswer(cur.rest, block, false);
      questions.push(makeQuestion(cur.number, pair.question, pair.answer, 1));
      if (questions.length >= MAX_QUESTIONS) break;
    }
    return questions;
  }

  /**
   * Правило «перечень + ответы»: сначала перечень вопросов (1…N), затем те же
   * номера с ответами. Разделяем, когда нумерация начинается заново.
   */
  function buildFromNumberedRuns(lines, starts) {
    const runs = [];
    let cur = [starts[0]];
    for (let i = 1; i < starts.length; i++) {
      if (starts[i].number <= cur[cur.length - 1].number && starts[i].number <= 2) {
        runs.push(cur);
        cur = [starts[i]];
      } else {
        cur.push(starts[i]);
      }
    }
    runs.push(cur);
    if (runs.length < 2) return null;

    const questions = [];
    // Первый прогон — перечень, дальше — блоки ответов (их может быть больше одного:
    // «Все ответы» порциями по десять вопросов).
    for (let r = 1; r < runs.length; r++) {
      const run = runs[r];
      for (let i = 0; i < run.length; i++) {
        const c = run[i];
        const nextLine = i + 1 < run.length ? run[i + 1].line : lines.length;
        const block = lines.slice(c.line + 1, nextLine);
        const pair = splitFirstParagraph(c.rest, block);
        questions.push(makeQuestion(c.number, pair.question, pair.answer, r));
        if (questions.length >= MAX_QUESTIONS) break;
      }
    }
    return questions.length >= 2 ? questions : null;
  }

  /** Правило 6: абзацы. Чётные — вопрос (обычно с «?»), нечётные — ответ. */
  function buildFromParagraphs(paragraphs) {
    const questions = [];
    for (let i = 0; i < paragraphs.length; i += 2) {
      const q = paragraphs[i];
      const a = paragraphs[i + 1] || "";
      questions.push(makeQuestion(questions.length + 1, q, a, 1));
      if (questions.length >= MAX_QUESTIONS) break;
    }
    return questions;
  }

  /** Формирует объект вопроса со статистикой. */
  function makeQuestion(num, question, answer, listNo) {
    const q = t.collapseSpaces(question);
    const a = String(answer || "").trim();
    const qStat = t.analyze(stripMarkup(q), "wpm", 1);
    const aStat = t.analyze(a, "wpm", 1);
    const words = qStat.words + aStat.words;
    const chars = qStat.chars + aStat.chars;
    return {
      num: num,
      listNo: listNo || 1,
      question: q,
      answer: a,
      title: shortTitle(q) || "Вопрос " + num,
      hasAnswer: a.length > 0,
      qWords: qStat.words,
      aWords: aStat.words,
      qChars: qStat.chars,
      aChars: aStat.chars,
      charsWithSpaces: qStat.charsWithSpaces + aStat.charsWithSpaces,
      words: words,
      chars: chars,
      // Средняя сложность вопроса (доля ответа больше, он и определяет время).
      difficulty:
        aStat.words > 0
          ? (qStat.difficulty * qStat.words + aStat.difficulty * aStat.words) / Math.max(1, words)
          : qStat.difficulty,
      preview: t.truncate(stripMarkup(a) || stripMarkup(q), 200)
    };
  }

  /** Похожи ли «вопросы» из абзацного режима на настоящие вопросы. */
  function looksLikeQuestions(questions) {
    if (questions.length < 2) return false;
    let ok = 0;
    for (const q of questions) {
      if (/\?\s*$/.test(q.question) || q.qWords <= 40) ok++;
    }
    return ok / questions.length >= 0.5;
  }

  /** Весь файл — один вопрос (первый абзац) и один ответ (всё остальное). */
  function buildWholeDocument(lines) {
    const nonEmpty = lines.filter((l) => l.trim());
    if (!nonEmpty.length) return [];
    const first = nonEmpty[0].trim();
    const startLine = lines.findIndex((l) => l.trim() === first);
    const question = stripMarkup(first).slice(0, 400);
    const answer = lines.slice(startLine + 1).join("\n").replace(/[ \t]+/g, " ").trim();
    return [makeQuestion(1, question, answer, 1)];
  }

  /** Делит найденные начала на прогоны: 1…N, затем снова 1…M. */
  function splitRuns(starts) {
    if (!starts || !starts.length) return [];
    const runs = [[starts[0]]];
    for (let i = 1; i < starts.length; i++) {
      const cur = starts[i];
      const run = runs[runs.length - 1];
      const prev = run[run.length - 1];
      if (cur.number <= prev.number && cur.number <= 2) runs.push([cur]);
      else run.push(cur);
    }
    return runs;
  }

  /**
   * parseDocument(text, options)
   * options: { assumeAnswerWords } — если у вопросов нет ответов, можно оценить объём.
   * Возвращает { questions, strategy, warnings, ... }.
   */
  function parseDocument(rawText, options) {
    options = options || {};
    const warnings = [];
    const source = t.cleanText(rawText || "");
    const normalized = source.replace(/\f/g, "\n\n");
    let lines = normalized.split("\n");
    lines = cleanPdfNoise(lines);

    const nonEmpty = lines.filter((l) => l.trim()).length;
    if (nonEmpty === 0) {
      return {
        questions: [],
        strategy: "empty",
        warnings: [{ type: "empty", text: "В файле нет текста." }],
        count: 0,
        totalWords: 0,
        totalChars: 0,
        avgWords: 0,
        answeredCount: 0
      };
    }

    const answerMarkers = hasAnswerMarkers(lines);
    const mdStarts = findStarts(lines, "md");
    const plainStarts = findStarts(lines, "plain");
    const numStarts = findStarts(lines, "num");

    let questions = [];
    let strategy = "";

    // --- 1. Явные заголовки вопросов: «# Вопрос 12.» / «Вопрос 12.»
    const headingStarts = mdStarts.length >= 2 ? mdStarts : plainStarts.length >= 2 ? plainStarts : [];
    if (headingStarts.length >= 2) {
      questions = buildFromStarts(lines, headingStarts, {
        useAnswerMarker: answerMarkers,
        split: answerMarkers ? "answer-marker" : "first-paragraph"
      });
      strategy = mdStarts.length >= 2 ? "markdown-headings" : "question-headings";
    } else {
      // Один заголовок в начале файла — это файл на один вопрос (так устроены
      // исходники ответов: «# Вопрос 45. …» и далее весь ответ).
      const single = mdStarts[0] || plainStarts[0];
      if (single) {
        const linesBefore = lines.slice(0, single.line).filter((l) => l.trim()).length;
        if (linesBefore <= 2) {
          questions = buildSingle(lines, single);
          strategy = "single-question-file";
        }
      }
    }

    const keepSingle = strategy === "single-question-file";

    // --- 2. Перечень вопросов + ответы (двойная нумерация) либо просто список.
    if (!keepSingle && questions.length < 2 && numStarts.length >= 2) {
      const runs = splitRuns(numStarts);
      const biggest = runs.reduce((a, b) => (b.length > a.length ? b : a), runs[0]);
      if (runs.length >= 2 && biggest.length >= 3) {
        const paired = buildFromNumberedRuns(lines, numStarts);
        if (paired && paired.length >= 2) {
          questions = paired;
          strategy = "list-and-answers";
        }
      }
      if (questions.length < 2) {
        // Обычный нумерованный список: 1., 2., 3. … — каждый пункт = вопрос.
        const seq = longestSequentialRun(numStarts);
        // Если основная часть нумерации последовательна — берём все начала:
        // в файле может быть несколько перечней подряд.
        const chosen = seq.length >= 3 && seq.length > numStarts.length * 0.6 ? seq : numStarts;
        questions = buildFromStarts(lines, chosen, {
          useAnswerMarker: answerMarkers,
          split: answerMarkers ? "answer-marker" : "first-paragraph"
        });
        if (questions.length >= 2) {
          strategy = answerMarkers ? "numbered-with-answers" : "numbered-list";
        }
      }
    }

    // --- 3. Строки-вопросы с «?».
    if (!keepSingle && questions.length < 2) {
      const byQuestion = buildFromQuestionLines(lines);
      if (byQuestion.length >= 2) {
        questions = byQuestion;
        strategy = "question-lines";
      }
    }

    // --- 4. Абзацы (последняя попытка).
    if (!keepSingle && questions.length < 2) {
      const paragraphs = normalized
        .split(/\n\s*\n/)
        .map((p) => p.replace(/\s+/g, " ").trim())
        .filter((p) => p.length > 0);
      if (paragraphs.length >= 2) {
        questions = buildFromParagraphs(paragraphs);
        strategy = "paragraphs";
      }
    }

    // Проверка «абзацного» режима: если «вопросы» не похожи на вопросы,
    // значит формат не распознан — считаем весь файл одним вопросом с ответом.
    if (strategy === "paragraphs" && !looksLikeQuestions(questions)) {
      questions = buildWholeDocument(lines);
      strategy = "whole-document";
      warnings.push({
        type: "whole-document",
        text:
          "Формат не распознан однозначно: файл прочитан как один вопрос с ответом. " +
          "Если в нём несколько вопросов — проверьте нумерацию («1. …») или добавьте строки «Вопрос N»."
      });
    }

    if (!strategy) {
      // Совсем без структуры: лучше показать файл одним вопросом с ответом,
      // чем отказаться его принимать. Пользователь увидит предупреждение.
      questions = buildWholeDocument(lines);
      strategy = "whole-document";
      warnings.push({
        type: "whole-document",
        text:
          "В файле не нашлось нумерации вопросов — он прочитан как один вопрос с ответом. " +
          "Если вопросов несколько, добавьте строки вида «1. …» или «Вопрос 1. …»."
      });
    }

    // Оценка объёма, если ответов нет вовсе (только перечень вопросов).
    const withAnswers = questions.filter((q) => q.hasAnswer).length;
    if (questions.length > 0 && withAnswers === 0 && options.assumeAnswerWords > 0) {
      const assumed = Math.max(10, options.assumeAnswerWords);
      questions = questions.map((q) => estimateMissing(q, assumed));
      warnings.push({
        type: "no-answers",
        text:
          "В файле найдены только вопросы без ответов. Время посчитано по оценке объёма ответа " +
          "(" + assumed + " слов на вопрос) — её можно изменить в настройках дисциплины."
      });
    } else if (questions.length > 1 && withAnswers > 0 && withAnswers < questions.length) {
      const avg = avgAnswerWords(questions);
      questions = questions.map((q) => (q.hasAnswer ? q : estimateMissing(q, avg)));
      warnings.push({
        type: "partial-answers",
        text:
          "У " + (questions.length - withAnswers) + " из " + questions.length +
          " вопросов не найден ответ — они посчитаны по средней длине остальных."
      });
    }

    // Нумерованные подпункты внутри ответов («1. …», «2. …») неотличимы от
    // начала следующего вопроса. Если из-за этого вопросы остались без ответов,
    // честно предупреждаем: так файл можно поправить.
    if (answerMarkers && questions.length >= 3) {
      const emptyTail = questions.filter((q) => !q.hasAnswer).length;
      if (emptyTail >= 3 && emptyTail >= questions.length * 0.3) {
        warnings.push({
          type: "sublist-answers",
          text:
            "Похоже, внутри ответов есть нумерованные пункты — они приняты за новые вопросы. " +
            "Надёжнее оформить вопросы заголовками «Вопрос N. …» (или файлами по одному вопросу)."
        });
      }
    }

    // Проверки качества распознавания.
    if (questions.length === 0) {
      warnings.push({
        type: "not-recognized",
        text: "Не удалось найти ни одного вопроса. Проверьте, что в файле есть нумерация «1. …» или строки с «?»."
      });
    }
    const nums = new Set(questions.map((q) => q.num));
    if (questions.length > 5 && nums.size < questions.length * 0.9) {
      warnings.push({
        type: "duplicate-numbers",
        text: "В файле повторяются номера вопросов. Вопросы сохранены все, но нумерация может путать."
      });
    }

    let totalWords = 0;
    let totalChars = 0;
    let totalAnswerWords = 0;
    for (const q of questions) {
      totalWords += q.words;
      totalChars += q.chars;
      totalAnswerWords += q.aWords;
    }

    return {
      questions: questions,
      strategy: strategy,
      warnings: warnings,
      count: questions.length,
      answeredCount: withAnswers,
      totalWords: totalWords,
      totalChars: totalChars,
      totalAnswerWords: totalAnswerWords,
      avgWords: questions.length ? totalWords / questions.length : 0
    };
  }

  function avgAnswerWords(questions) {
    const withA = questions.filter((q) => q.aWords > 0);
    if (!withA.length) return 300;
    return Math.round(withA.reduce((s, q) => s + q.aWords, 0) / withA.length);
  }

  /** Вопрос без ответа: подставляет оценку объёма, чтобы время было осмысленным. */
  function estimateMissing(q, assumedWords) {
    const words = Math.max(10, Math.round(assumedWords));
    const chars = Math.round(words * 6.2);
    const answer = q.answer || "";
    const aStat = t.analyze(answer, "wpm", 1);
    const totalWords = q.qWords + (aStat.words || words);
    const totalChars = q.qChars + (aStat.chars || chars);
    return Object.assign({}, q, {
      aWords: aStat.words || words,
      aChars: aStat.chars || chars,
      words: totalWords,
      chars: totalChars,
      estimated: !q.hasAnswer,
      preview: q.preview || "Ответ не найден — время оценено по средней длине."
    });
  }

  /** Быстрый предпросмотр: первые N вопросов и общая статистика. */
  function preview(rawText, options) {
    const r = parseDocument(rawText, options);
    return Object.assign({}, r, {
      questions: r.questions.slice(0, 12).map((q) => ({
        num: q.num,
        title: q.title,
        words: q.words,
        chars: q.chars,
        hasAnswer: q.hasAnswer
      }))
    });
  }

  return {
    parseDocument,
    preview,
    findStarts,
    shortTitle,
    stripMarkup,
    hasAnswerMarkers,
    answerMarkers: ANSWER_RE,
    makeQuestion
  };
});
