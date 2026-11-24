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
  // «12. Текст» / «12) Текст». Не путать с подпунктами «1.1», «2.3.1» —
  // они относятся к структуре ответа, а не к нумерации вопросов.
  const NUM_Q_RE = /^\s*(\d{1,4})\s*[.)]\s*(?=\S)(?!\d+[.)])(.{2,}?)\s*$/;
  // «12.» отдельной строкой — так бывает, когда номер в своём абзаце.
  const NUM_ALONE_RE = /^\s*(\d{1,4})\s*[.)]?\s*$/;
  // Явный маркер ответа: «Ответ:», «Ответ.», «ОТВЕТ», «Answer:», «Решение:»
  const ANSWER_RE = /^\s*[*_>#\s]*(ответ|answer|решение|разбор)\s*[*_]*\s*[:.\-—]\s*(.*)$/i;
  // Заголовок раздела ответов: «ОТВЕТЫ», «Ответы на вопросы», «РАЗДЕЛ 2. ОТВЕТЫ».
  // \b после кириллицы в JS не работает, поэтому конец слова проверяем вручную.
  const ANSWERS_SECTION_RE =
    /^[\s*_#>\-—]*(раздел\s*\d+[.):]?\s*)?(ответы|answers)([\s*_#:.,]|$)[\s*_#:.,]*(на\s+вопросы|к\s+вопросам|на\s+экзамен)?[\s*_#:.,]*$/i;
  // «Ответ 12. Текст» / «Ответ № 12:» — блок ответов с собственной нумерацией.
  const ANSWER_NUM_RE = /^\s*[*_>#\s]*(ответ|answer)\s*№?\s*(\d{1,4})\s*[.):\-—]?\s*(.*)$/i;
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
  /** «**1. Вопрос**» → «1. Вопрос»: снимаем обёртку жирного/курсива. */
  function unwrapMarkup(s) {
    let t = String(s || "").trim();
    t = t.replace(/^\*\*(.+)\*\*$/, "$1").trim();
    t = t.replace(/^__(.+)__$/, "$1").trim();
    t = t.replace(/^\*(.+)\*$/, "$1").trim();
    t = t.replace(/^_(.+)_$/, "$1").trim();
    return t;
  }

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
    let skipQuestionLine = -1;
    for (let i = 0; i < lines.length; i++) {
      const rawLine = lines[i];
      // Строка без markdown-обёртки: «**1. Вопрос**» — это тоже нумерация.
      const line = unwrapMarkup(rawLine);
      if (line.length > 600 && rule === "num") continue; // не маркер, а длинная строка
      let m = line.match(re);
      if (!m && rule === "num") {
        // Номер отдельной строкой: вопрос — следующая непустая строка.
        const alone = line.match(NUM_ALONE_RE);
        if (alone) {
          let j = i + 1;
          while (j < lines.length && !lines[j].trim()) j++;
          if (j < lines.length) {
            const next = lines[j].trim();
            if (hasLetter(next) && next.length >= 3 && next.length <= 250) {
              m = [line, alone[1], next];
              // bodyStart — строка j, где начинается ТЕКСТ под номером.
              // Отдельная пометка: текст не в остатке строки, а ниже. Иначе
              // пары «перечень + ответы» дублировали бы первую строку ответа.
              skipQuestionLine = j;
            }
          }
        }
      }
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
        // Сравниваем с последним ПРИНЯТЫМ номером, а не с любым встреченным:
        // иначе блок ответов (1, 2, 3…) съедает нумерацию перечня и всё
        // после «1.» отбрасывается как «не по порядку».
        const lastAccepted = out.length ? out[out.length - 1].number : 0;
        const isNext = out.length > 0 && num === lastAccepted + 1;
        const isRestart = out.length > 0 && num === 1 && blankBefore;
        // Файл начинается не с «1.» — первый пункт принимаем всегда.
        // Разрыв нумерации назад (было 3, стало 1) — это новый перечень:
        // так начинается блок ответов с теми же номерами, и его нельзя терять.
        const isBackwards = out.length > 0 && num < lastAccepted;
        if (out.length > 0 && !isNext && !isRestart && !isBackwards) {
          if (!(num === lastAccepted && blankBefore)) continue;
        }
        // Совсем мелкие номера в середине текста — точно не вопрос.
        if (out.length > 0 && num < 2 && !blankBefore && isNext) continue;
      }
      lastNum = num;
      // bodyStart — точная строка начала текста (без «+1»: раньше из-за него
      // терялась первая строка ответа при номере отдельной строкой).
      out.push({
        line: i,
        number: num,
        rest,
        // true — текст под номером, а не в самой строке номера
        restIsNextLine: skipQuestionLine > i,
        bodyStart: skipQuestionLine > i ? skipQuestionLine : -1
      });
      skipQuestionLine = -1;
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
   * Первый абзац блока — вопрос, остальное — ответ.
   * Нужен для формата «перечень вопросов + ответы ниже», где вопрос и ответ
   * разделены пустой строкой.
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
   * Граница вопроса и ответа внутри блока.
   *
   * Так устроено большинство реальных файлов: вопрос — это строка-заголовок
   * (крупный шрифт в Word, поэтому в тексте она отдельной строкой), а сразу
   * за ней идёт ответ. Пустой строки между ними может не быть вовсе, и
   * следующий вопрос тоже начинается сразу после ответа.
   *
   * Правила, по которым узнаём вопрос:
   *   1) вопрос уже в строке-маркере («1. Понятие …») — остаток строки;
   *   2) вопрос занимает несколько строк до пустой строки (длинный заголовок);
   *   3) вопрос — короткая первая строка без точки в конце, а вторая строка
   *      длиннее и «рассказывает» — это уже ответ.
   */
  function splitByQuestionShape(rest, blockLines) {
    const first = (rest || "").trim();
    const lines = blockLines.slice();

    // 1. Маркер пустой («1.» отдельной строкой) — вопрос в первой непустой строке.
    if (!first) {
      let i = 0;
      while (i < lines.length && isBlank(lines[i])) i++;
      if (i >= lines.length) return { question: "", answer: "" };
      const q = lines[i].trim();
      const answer = lines.slice(i + 1).join("\n").trim();
      return { question: q, answer: answer };
    }

    // 2. «Ответ:» сразу в первой строке-маркере — дальше только ответ.
    if (ANSWER_RE.test(first) || ANSWER_ONLY_RE.test(first)) {
      return { question: "", answer: first };
    }

    // 3. Самая частая структура: маркер + вопрос в той же строке, ответ — блок.
    //    Отвечаем на вопрос: первая ли строка заголовком является целиком?
    //    Заголовок может состоять из двух фраз («Подготовка к обыску.
    //    Использование помощи специалистов…») — это всё ещё вопрос, если ниже
    //    лежит полноценный ответ. Делить по точке нужно только когда тела нет.
    const firstIsQuestion = looksLikeHeadingLine(first) || bodyLooksLikeAnswer(lines);

    if (!firstIsQuestion) {
      // Маркер и вопрос слиплись с ответом: «1. Понятие … Административным
      // правонарушением признаётся …» в одной строке. Разделяем по первому
      // предложению-заголовку.
      const split = splitHeadingFromRest(first);
      if (split) {
        const answer = [split.answer, ...lines].filter((x) => x && x.trim()).join("\n").trim();
        return { question: split.question, answer: answer };
      }
    }

    // 3.5. Вопрос и ответ слиты в одну строку через тире:
    //      «1. Понятие правонарушения — противоправное деяние, за которое…».
    //      Заголовок короткий и без точки, после «—» идёт длинный текст.
    const dash = first.match(/^(.{8,150}?)\s+[—–-]\s+(.{25,})$/);
    if (dash) {
      const head = dash[1].trim();
      const tail = dash[2].trim();
      // Заголовок не должен сам быть длинным текстом с точкой в конце.
      if (!/[.!?]$/.test(head) || head.length < 60) {
        const rest2 = [tail].concat(lines).filter((x) => x && x.trim()).join("\n").trim();
        return { question: head, answer: rest2 };
      }
    }

    // 4. Вопрос может занимать несколько строк до первой пустой (длинный
    //    заголовок в две-три строки). Но только если эти строки похожи на
    //    заголовок, а не на текст ответа.
    let end = 0;
    let qParts = [first];
    while (end < lines.length) {
      const ln = lines[end];
      if (isBlank(ln)) {
        end++;
        break; // пустая строка закрывает заголовок
      }
      // Явные признаки начала ответа.
      if (ANSWER_RE.test(ln) || ANSWER_ONLY_RE.test(ln)) break;
      if (/^#{1,4}\s/.test(ln) || /^>/.test(ln) || /^[-*•]\s/.test(ln)) break;
      const cur = ln.trim();
      const prev = qParts[qParts.length - 1];

      // Явные признаки начала ответа (заголовок раздела, цитата, перечень,
      // «Ответ:») — заголовок вопроса точно кончился.
      if (/^#/.test(cur) || /^>/.test(cur) || /^[-*•]\s/.test(cur) || /^\*\*/.test(cur)) break;
      if (ANSWER_RE.test(cur) || ANSWER_ONLY_RE.test(cur)) break;

      // Главный признак: длинная повествовательная строка — это ответ, а не
      // продолжение заголовка. Заголовки бывают многострочными, но каждая их
      // строка короткая.
      if (cur.length > 130) break;

      // Предыдущая строка закончилась точкой/вопросом/восклицанием — фраза
      // закрыта. Двоеточие и точка с запятой наоборот обещают продолжение
      // («Неправовые формы административной деятельности полиции:» /
      // «организационные действия и материально-технические операции.»).
      if (/[.?!]$/.test(prev) && cur.length >= 40) break;

      // Продолжение заголовка: короткая строчная строка, не новое предложение
      // с заглавной буквы и не служебный заголовок раздела.
      const continues =
        qParts.length < 4 &&
        cur.length < 120 &&
        (/^[а-яёa-z(«"\d—–-]/.test(cur) || !/[А-ЯЁ]/.test(cur));
      if (continues) {
        qParts.push(cur);
        end++;
        continue;
      }
      break;
    }

    const question = qParts.join(" ").replace(/[ \t]+/g, " ").trim();
    const answer = lines.slice(end).join("\n").replace(/[ \t]+/g, " ").trim();

    // Если ответа не осталось — возможно, мы забрали ответ в вопрос. Тогда
    // вопрос — только первая строка, остальное — ответ. Но только когда
    // продолжений не было: иначе это заголовок в несколько строк, и ответа
    // в файле просто нет (перечень вопросов без ответов).
    if (!answer && lines.length > 0 && qParts.length === 1) {
      return { question: first, answer: lines.join("\n").trim() };
    }
    return { question: question, answer: answer };
  }

  /**
   * Похож ли блок под заголовком на ответ: есть разметка (заголовок раздела,
   * цитата, перечень) или он начинается длинной повествовательной строкой.
   * Короткие строки-продолжения заголовка и продолжение перечня вопросов
   * ответом не считаются.
   */
  function bodyLooksLikeAnswer(lines) {
    let total = 0;
    let firstText = null;
    for (const ln of lines) {
      if (isBlank(ln)) continue;
      total += ln.trim().length;
      if (firstText === null) firstText = ln.trim();
      if (/^#{1,4}\s|^>|^[-*•]\s|^\*\*/.test(ln.trim())) return total >= 60;
    }
    if (total < 200) return false;
    return (firstText || "").length >= 90;
  }

  /**
   * Похожа ли строка на заголовок вопроса: короткая, без точки в конце,
   * не перечисление, не цитата, не начало длинного абзаца.
   */
  function looksLikeHeadingLine(s) {
    const t = String(s || "").trim();
    if (!t) return false;
    if (t.length > 200) return false;
    if (/^#{1,4}\s/.test(t) || /^>/.test(t) || /^[-*•]\s/.test(t)) return false;
    if (/[.!?;]$/.test(t) && t.length > 90) return false;
    // Больше двух предложений — это уже текст ответа.
    const sentences = (t.match(/[.!?](\s|$)/g) || []).length;
    if (sentences >= 2) return false;
    // Вопрос часто заканчивается на «?» — это точно заголовок.
    if (/\?$/.test(t)) return true;
    return t.length <= 150;
  }

  /**
   * «1. Понятие … Административным правонарушением признаётся …» — заголовок
   * слипся с ответом в одной строке. Отделяем первое предложение-заголовок.
   */
  function splitHeadingFromRest(s) {
    const t = String(s || "").trim();
    if (t.length < 60) return null;
    // Ищем конец первого предложения, после которого начинается объяснение.
    const m = t.match(/^(.{10,140}?[.?!])\s+(.{40,})$/);
    if (!m) return null;
    const head = m[1].trim();
    const tail = m[2].trim();
    // Заголовок не должен сам быть длинным текстом с двумя предложениями.
    if (!looksLikeHeadingLine(head)) return null;
    // Ответ должен быть заметно длиннее заголовка.
    if (tail.length < head.length * 0.6) return null;
    return { question: head, answer: tail };
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

  /**
   * Похож ли документ на перечень вопросов без ответов: под большинством
   * заголовков лежит не ответ, а продолжение самого заголовка.
   */
  function looksLikeQuestionOnlyList(lines, starts, opts) {
    if (opts.split !== "shape" || opts.useAnswerMarker) return false;
    if (!starts.length) return false;
    // Считаем «продолжением заголовка» короткие обрывочные строки: они не
    // начинаются с заглавной и заканчиваются точкой/без знака — так выглядит
    // вторая половина вопроса, разбитого переносом. Ответ же начинается как
    // самостоятельное предложение.
    let tails = 0;
    let answered = 0;
    const probe = starts.slice(0, 40);
    for (let s = 0; s < probe.length; s++) {
      const cur = probe[s];
      const nextLine = s + 1 < probe.length ? probe[s + 1].line : lines.length;
      const from = cur.bodyStart && cur.bodyStart > 0 ? cur.bodyStart : cur.line + 1;
      const block = lines.slice(from, Math.min(nextLine, lines.length)).filter((ln) => !isBlank(ln));
      if (!block.length) continue;
      if (bodyLooksLikeAnswer(block)) {
        answered++;
        continue;
      }
      const head = block[0].trim();
      // Обрывок: начинается со строчной или продолжает предлог/союз.
      if (/^[а-яё]/.test(head) || head.length < 60) tails++;
    }
    return tails >= answered && tails >= probe.length * 0.5;
  }

  /** Собирает вопросы из найденных начал. */
  function buildFromStarts(lines, starts, opts) {
    if (looksLikeQuestionOnlyList(lines, starts, opts)) {
      opts = Object.assign({}, opts, { split: "question-only" });
    }
    const questions = [];
    let listNo = 1;
    let prevNum = 0;
    for (let s = 0; s < starts.length; s++) {
      const cur = starts[s];
      const nextLine = s + 1 < starts.length ? starts[s + 1].line : lines.length;
      // Перезапуск нумерации → второй перечень в том же файле.
      if (s > 0 && cur.number <= prevNum && cur.number <= 2) listNo++;
      prevNum = cur.number;

      const from = cur.bodyStart && cur.bodyStart > 0 ? cur.bodyStart : cur.line + 1;
      const block = lines.slice(from, nextLine);
      let pair;
      if (opts.split === "question-only") {
        // Перечень вопросов без ответов: каждая строка блока — продолжение
        // заголовка, делить не на что.
        const tail = block.filter((ln) => !isBlank(ln)).map((ln) => ln.trim());
        pair = { question: [cur.rest, ...tail].join(" ").replace(/[ \t]+/g, " ").trim(), answer: "" };
      } else if (opts.split === "shape") pair = splitByQuestionShape(cur.rest, block);
      else if (opts.split === "first-paragraph") pair = splitFirstParagraph(cur.rest, block);
      else pair = splitQuestionAnswer(cur.rest, block, opts.useAnswerMarker);
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
    // Файл = один вопрос: «# Вопрос 45. Текст» и следом ответ. Делим тем же
    // правилом, что и остальные форматы — иначе заголовок съедал ответ.
    const num = start.number || 1;
    const body = lines.slice(start.line + 1);
    const split = splitByQuestionShape(start.rest || "", body);
    const question = (split.question || "").trim() || "Вопрос " + num;
    return [makeQuestion(num, question, (split.answer || "").trim(), 1)];
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
  /**
   * Самая частая структура настоящих файлов: СВЕРХУ перечень вопросов
   * («1. Понятие…», «2. Признаки…»), СНИЗУ — ответы с теми же номерами
   * (часто «1.» отдельной строкой, дальше текст).
   *
   * Отличаем перечень от ответов по виду: пункт перечня — одна короткая строка
   * без текста под ней; пункт ответа — либо номер отдельной строкой, либо
   * строка, под которой идёт абзац.
   */
  function pairListWithAnswers(lines, runs) {
    if (!runs || runs.length < 2) return null;

    // Слова-разделы, которые не являются ни вопросом, ни ответом:
    // «ОТВЕТЫ», «ВОПРОСЫ», «ПЕРЕЧЕНЬ», «СОДЕРЖАНИЕ», «ПРИЛОЖЕНИЕ».
    function isSectionWord(s) {
      const t = String(s || "").trim();
      return (
        /^[\s*_#>]*(ответы|вопросы|перечень|содержание|оглавление|приложение|раздел)(\s|$)/i.test(t) &&
        t.length <= 60
      );
    }

    // Что идёт под каждым пунктом прогона: пусто, «продолжение» или «текст».
    // inAnswerBlock — смотрим ли мы блок ответов (там текст может быть приклеен
    // к номеру, и это надо отличать от длинного заголовка вопроса).
    function natureOf(run, idx, inAnswerBlock) {
      const c = run[idx];
      const nextLine = idx + 1 < run.length ? run[idx + 1].line : lines.length;
      const from = c.bodyStart && c.bodyStart > 0 ? c.bodyStart : c.line + 1;
      // Под пунктом перечня может лежать сразу и «ОТВЕТЫ», и блок ответов.
      // Смотрим только до первого признака ответа — иначе перечень никогда
      // не выглядел бы перечнем.
      const block = [];
      for (let i = from; i < nextLine; i++) {
        const ln = lines[i];
        if (!ln.trim()) continue;
        if (isSectionWord(ln)) continue;
        if (NUM_ALONE_RE.test(ln) || /^\s*\d{1,4}\s*[.)]\s/.test(ln)) break;
        if (ANSWER_NUM_RE.test(ln) || ANSWER_RE.test(ln) || ANSWER_ONLY_RE.test(ln)) break;
        block.push(ln);
      }
      // Текст может быть приклеен прямо к номеру: «1. Административным …».
      // Это тоже ответ, и по нему отличаем блок ответов от второго перечня.
      if (inAnswerBlock && !c.restIsNextLine && (c.rest || "").trim().length >= 40) return "body";
      if (!block.length) return "empty";
      const first = block[0].trim();
      // Номер отдельной строкой — под ним всегда текст ответа.
      if (c.bodyStart && c.bodyStart > 0) return "body";
      // Длинный абзац под короткой строкой — это ответ.
      if (first.length >= 90) return "body";
      if (block.length >= 2) return "body";
      // Короткая строчная строка — продолжение заголовка вопроса.
      if (/^[а-яё]/.test(first) && first.length < 90) return "tail";
      return "body";
    }

    // Прогон-перечень: пункты короткие, под ними в основном пусто.
    function looksLikeList(run) {
      let empty = 0;
      let body = 0;
      run.forEach((c, i) => {
        const n = natureOf(run, i);
        if (n === "empty" || n === "tail") empty++;
        else body++;
      });
      return empty > body;
    }

    // Ищем перечень, за которым идёт блок ответов с теми же номерами.
    for (let li = 0; li < runs.length - 1; li++) {
      const list = runs[li];
      if (list.length < 2 || !looksLikeList(list)) continue;

      // Собираем ответы из всех следующих прогонов: номера должны совпадать
      // с номерами перечня, иначе это не ответы к нему.
      const byNumber = new Map();
      for (let ri = li + 1; ri < runs.length; ri++) {
        for (const c of runs[ri]) {
          if (!byNumber.has(c.number)) byNumber.set(c.number, []);
          byNumber.get(c.number).push(c);
        }
      }

      const matched = list.filter((c) => byNumber.has(c.number)).length;
      if (matched < 2 || matched < list.length * 0.7) continue;

      // Проверка «это правда ответы»: у блока ответов под номером есть текст.
      // Два перечня вопросов подряд тоже совпадают по номерам, но текста под
      // номерами нет — такой файл надо разбирать как два перечня.
      let answerBodies = 0;
      let answerItems = 0;
      for (let ri = li + 1; ri < runs.length; ri++) {
        for (let k = 0; k < runs[ri].length; k++) {
          answerItems++;
          if (natureOf(runs[ri], k, true) === "body") answerBodies++;
        }
      }
      if (!answerItems || answerBodies < answerItems * 0.5) continue;

      // Порядок ответов: собираем по строкам, а не по номерам, чтобы не
      // перепутать, если файл идёт не по порядку.
      const answerStarts = [];
      for (let ri = li + 1; ri < runs.length; ri++) {
        for (const c of runs[ri]) if (byNumber.has(c.number)) answerStarts.push(c);
      }
      answerStarts.sort((a, b) => a.line - b.line);

      const out = [];
      for (let k = 0; k < list.length; k++) {
        const q = list[k];
        let answer = "";
        const cand = byNumber.get(q.number);
        if (cand && cand.length) {
          const c = cand[0];
          const nextLine = nextLineOf(c, answerStarts);
          // Два вида ответа:
          //   • «1.» отдельной строкой → текст начинается со следующей строки;
          //   • «1. текст ответа» → текст уже в остатке строки, а следующие
          //     строки — продолжение ответа.
          // «1. текст» — текст в остатке строки; «1.» — текст ниже строки номера.
          const inline = !c.restIsNextLine;
          const head = inline ? (c.rest || "").trim() : "";
          let from = inline ? c.line + 1 : (c.bodyStart && c.bodyStart > 0 ? c.bodyStart : c.line + 1);
          while (from < nextLine && !lines[from].trim()) from++;
          const tail = lines
            .slice(from, nextLine)
            .join("\n")
            .replace(/[ \t]+/g, " ")
            .trim();
          answer = (inline ? head + (tail ? "\n" + tail : "") : tail).trim();
        }
        // У вопроса из перечня под ним может быть продолжение заголовка.
        // Но только если это правда продолжение: короткая строчная строка без
        // признаков ответа. Иначе в вопрос попадал заголовок «ОТВЕТЫ» и начало
        // первого ответа.
        let question = q.rest;
        const qNext = k + 1 < list.length ? list[k + 1].line : answerStarts.length ? answerStarts[0].line : lines.length;
        const qBlock = lines
          .slice(q.line + 1, Math.max(q.line + 1, qNext))
          .filter((l) => l.trim())
          .map((l) => l.trim());
        const tailOk =
          qBlock.length === 1 &&
          qBlock[0].length < 90 &&
          !isSectionWord(qBlock[0]) &&
          !/[.!?]$/.test(question) &&
          /^[а-яё(«"]/.test(qBlock[0]) &&
          !ANSWER_RE.test(qBlock[0]) &&
          !ANSWER_ONLY_RE.test(qBlock[0]);
        if (tailOk) question = (question + " " + qBlock[0]).replace(/\s+/g, " ").trim();
        out.push(makeQuestion(q.number, question, answer, 1));
        if (out.length >= MAX_QUESTIONS) break;
      }

      const withAnswer = out.filter((x) => x.hasAnswer).length;
      if (out.length >= 2 && withAnswer >= Math.max(2, out.length * 0.5)) return out;
    }
    return null;

    /** Строка, где начинается следующий ответ (или конец файла). */
    function nextLineOf(c, sorted) {
      for (const other of sorted) if (other.line > c.line) return other.line;
      return lines.length;
    }
  }

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

  /**
   * Схема без номеров у ответов: сверху список вопросов «1. …», ниже заголовок
   * «ОТВЕТЫ» или «Ответы на вопросы», под ним — ответы обычными абзацами
   * в том же порядке. Номеров у ответов нет, поэтому связываем по порядку.
   *
   * Так устроены выгрузки из Word и PDF: вопросы нумеруются, ответы — просто
   * абзацы под заголовком раздела.
   */
  function pairListWithPlainAnswers(lines, questionStarts) {
    if (!questionStarts || questionStarts.length < 2) return null;

    // Где начинается раздел ответов.
    let sectionAt = -1;
    for (let i = 0; i < lines.length; i++) {
      const ln = lines[i].trim();
      if (!ln || ln.length > 80) continue;
      if (ANSWERS_SECTION_RE.test(ln)) {
        // Заголовок раздела должен стоять после вопросов.
        if (i > questionStarts[0].line) {
          sectionAt = i;
          break;
        }
      }
    }
    if (sectionAt < 0) return null;

    // Вопросы — только те, что стоят выше раздела ответов.
    const qs = questionStarts.filter((q) => q.line < sectionAt);
    if (qs.length < 2) return null;

    // Абзацы после раздела — ответы. Пустая строка закрывает абзац, но её
    // может и не быть: в Word ответы часто идут подряд, каждый с новой строки.
    // Поэтому новый абзац начинается и там, где строка похожа на начало
    // ответа: с большой буквы, а предыдущая закончилась точкой.
    const paras = [];
    let cur = [];
    let prevText = "";
    for (let i = sectionAt + 1; i < lines.length; i++) {
      const ln = lines[i];
      if (!ln.trim()) {
        if (cur.length) {
          paras.push(cur.join("\n").trim());
          cur = [];
          prevText = "";
        }
        continue;
      }
      const text = ln.trim();
      // Следующий перечень вопросов или новый раздел обрывает ответы.
      // «Вопрос 3. …» внутри блока — это начало ответа, а не новый вопрос.
      if (PLAIN_Q_RE.test(text) || MD_Q_RE.test(text)) {
        // заголовок вопроса в блоке ответов — оставляем как текст ответа
      } else if (NUM_ALONE_RE.test(ln) || /^\s*\d{1,4}\s*[.)]\s/.test(ln)) {
        break;
      }
      if (ANSWERS_SECTION_RE.test(text)) break;
      const startsNew =
        cur.length > 0 &&
        /^[А-ЯЁA-Z«"]/.test(text) &&
        /[.!?;]$/.test(prevText) &&
        text.length >= 30;
      if (startsNew) {
        paras.push(cur.join("\n").trim());
        cur = [];
      }
      cur.push(ln);
      prevText = text;
    }
    if (cur.length) paras.push(cur.join("\n").trim());

    // Строки-подзаголовки («1. Общая характеристика») ответом не считаем.
    const usable = paras.filter((p) => p.length >= 40);
    if (usable.length < 2) return null;

    // Ответов должно быть примерно столько же, сколько вопросов. Если их
    // заметно меньше, доверять такой схеме нельзя — вернём null и пусть
    // сработает обычный разбор с честной оценкой объёма.
    if (usable.length < qs.length * 0.75) return null;

    const out = [];
    for (let k = 0; k < qs.length; k++) {
      const q = qs[k];
      const answer = usable[k] || "";
      out.push(makeQuestion(q.number, q.rest, answer, 1));
      if (out.length >= MAX_QUESTIONS) break;
    }
    const withAnswer = out.filter((x) => x.hasAnswer).length;
    return withAnswer >= Math.max(2, out.length * 0.75) ? out : null;
  }

  /**
   * Схема «Вопрос 1.» … сверху, «Ответ 1.» … снизу: номера связывают
   * вопрос с ответом, порядок в файле может быть любым.
   */
  function pairHeadingsWithNumberedAnswers(lines, questionStarts) {
    const answers = [];
    for (let i = 0; i < lines.length; i++) {
      const m = lines[i].match(ANSWER_NUM_RE);
      if (!m) continue;
      const num = parseInt(m[2], 10);
      if (!isFinite(num) || num < 1) continue;
      const rest = (m[3] || "").trim();
      if (!hasLetter(rest) || rest.length < 3) {
        let j = i + 1;
        while (j < lines.length && !lines[j].trim()) j++;
        if (j >= lines.length) continue;
        answers.push({ num: num, line: i, rest: "", textFrom: j });
      } else {
        answers.push({ num: num, line: i, rest: rest, textFrom: i });
      }
    }
    if (answers.length < 2) return null;

    const byNum = new Map();
    for (const a of answers) if (!byNum.has(a.num)) byNum.set(a.num, a);

    const matched = questionStarts.filter((q) => byNum.has(q.number)).length;
    if (matched < 2 || matched < questionStarts.length * 0.7) return null;

    const answerLines = answers.map((a) => a.line).sort((x, y) => x - y);
    const out = [];
    for (const q of questionStarts) {
      const a = byNum.get(q.number);
      let answer = "";
      if (a) {
        let next = lines.length;
        for (const ln of answerLines) {
          if (ln > a.line) {
            next = ln;
            break;
          }
        }
        let from = a.textFrom;
        while (from < next && !lines[from].trim()) from++;
        const tail = lines
          .slice(a.rest ? a.textFrom + 1 : from, next)
          .join("\n")
          .replace(/[ \t]+/g, " ")
          .trim();
        answer = (a.rest ? a.rest + (tail ? "\n" + tail : "") : tail).trim();
      }
      out.push(makeQuestion(q.number, q.rest, answer, 1));
      if (out.length >= MAX_QUESTIONS) break;
    }
    return out.filter((x) => x.hasAnswer).length >= 2 ? out : null;
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
      // Новый перечень начинается там, где нумерация обрывается: номер
      // уменьшился или пропустил вперёд. Раньше проверялось «≤ 2», из-за чего
      // перечень вопросов и блок ответов с теми же номерами сливались в один.
      if (cur.number <= prev.number) runs.push([cur]);
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

    // --- 0. Ответы без номеров под заголовком «ОТВЕТЫ» или «Ответы на вопросы».
    // Частая выгрузка из Word: сверху нумерованный перечень, ниже раздел
    // «ОТВЕТЫ», под ним ответы обычными абзацами в том же порядке.
    // Проверяем раньше заголовков: в блоке ответов тоже бывает «Вопрос 3.»,
    // и общий разбор принял бы его за новый вопрос.
    {
      // Только когда сверху действительно перечень: два и больше начала.
      // Файл на один вопрос («# Вопрос 45.» + ответ) сюда попадать не должен —
      // у него заголовок один, и разбирается он отдельным правилом.
      const partsStarts = numStarts.length >= 2 ? numStarts : plainStarts.length >= 2 ? plainStarts : [];
      const plainAnswers = pairListWithPlainAnswers(lines, partsStarts);
      if (plainAnswers && plainAnswers.length >= 2) {
        questions = plainAnswers;
        strategy = "list-and-plain-answers";
      }
    }

    // --- 1. Явные заголовки вопросов: «# Вопрос 12.» / «Вопрос 12.»
    const headingStarts = mdStarts.length >= 2 ? mdStarts : plainStarts.length >= 2 ? plainStarts : [];

    // «Вопрос N.» сверху + «Ответ N.» снизу — проверяем ДО общего разбора
    // заголовков, иначе ответы прилипали бы к последнему вопросу.
    if (headingStarts.length >= 2) {
      const pairedHeadings = pairHeadingsWithNumberedAnswers(lines, headingStarts);
      if (pairedHeadings && pairedHeadings.length >= 2) {
        questions = pairedHeadings;
        strategy = "questions-and-answers";
      }
    }

    if (strategy) {
      // уже разобрано по схеме «вопросы + ответы»
    } else if (headingStarts.length >= 2) {
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

    // Файл на один вопрос разобран целиком — общий разбор к нему не применяем.
    const keepSingle = strategy === "single-question-file";

    // --- 2. Перечень вопросов + ответы (двойная нумерация) либо просто список.
    if (!keepSingle && questions.length < 2 && (numStarts.length >= 2 || plainStarts.length >= 2)) {
      const runs = questions.length >= 2 ? [] : splitRuns(numStarts);
      // Двойная нумерация: перечень вопросов и блок ответов. Ограничения «не
      // меньше трёх пунктов» нет — хватает и двух, а решение принимает
      // pairListWithAnswers по совпадению номеров и виду блоков.
      if (runs.length >= 2) {
        const paired = pairListWithAnswers(lines, runs);
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
          split: answerMarkers ? "answer-marker" : "shape"
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
