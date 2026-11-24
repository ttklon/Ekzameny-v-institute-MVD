/*
 * parser.js — универсальный приёмник файлов вопрос-ответ.
 * Распознаёт вопросы и ответы в разных форматах:
 *   A) Нумерованный список: "1. Вопрос" ... "2. Вопрос"
 *   B) "Вопрос 1" / "Question 1" ... "Ответ:" / "Answer:"
 *   C) Вопросительные строки ("...?") как вопросы, следующие строки — ответ.
 * Автоматически отбрасывает мусор от PDF (одиночные номера страниц и т.п.).
 */
(function (root, factory) {
  const deps =
    typeof module !== "undefined" && module.exports
      ? { textstats: require("./textstats") }
      : { textstats: root.ExamCore && root.ExamCore.textstats };
  const api = factory(deps.textstats);
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof window !== "undefined") window.ExamCore = Object.assign(window.ExamCore || {}, { parser: api });
})(typeof self !== "undefined" ? self : this, function (textstats) {
  // Маркер нумерованного вопроса: "12." или "12)" в начале строки + текст.
  // Обязательно должен быть текст после маркера (иначе это мусор/номер страницы).
  const NUM_RE = /^\s*(\d{1,4})[\.\)]\s+(.+)$/;
  // Маркер "Вопрос N" / "Question N".
  const VOPROS_RE = /^\s*(вопрос|question)\s*(\d{0,4})[.:)]\s*(.*)$/i;
  // Явный маркер ответа.
  const ANSWER_RE = /^\s*(ответ|отв\.?|решение|answer|а)\s*[:.)]?\s*(.*)$/i;
  // Строка, заканчивающаяся вопросительным знаком.
  const ENDS_Q = (s) => /\?\s*$/.test(s.trim());

  function isBlank(s) {
    return s.trim().length === 0;
  }

  // Ищем стартовые индексы вопросов и тип маркера.
  function findQuestionStarts(lines) {
    const starts = [];
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const mNum = line.match(NUM_RE);
      if (mNum) {
        starts.push({ idx: i, type: "num", num: parseInt(mNum[1], 10), text: mNum[2] });
        continue;
      }
      const mV = line.match(VOPROS_RE);
      if (mV) {
        starts.push({ idx: i, type: "vopros", num: mV[2] ? parseInt(mV[2], 10) : null, text: mV[3] });
      }
    }
    return starts;
  }

  // Построение вопросов из стартовых маркеров.
  function buildFromStarts(lines, starts, unit, rate, assumeAnswerWords) {
    const questions = [];
    for (let s = 0; s < starts.length; s++) {
      const cur = starts[s];
      const nextIdx = s + 1 < starts.length ? starts[s + 1].idx : lines.length;
      const restLines = lines.slice(cur.idx + 1, nextIdx);

      let questionRaw = cur.text || "";
      let answerRaw = "";

      for (const ln of restLines) {
        const aMatch = ln.match(ANSWER_RE);
        if (aMatch && answerRaw === "") {
          // Явный маркер ответа: с этого момента — ответ.
          answerRaw = (aMatch[2] || "").trim();
          continue;
        }
        if (answerRaw !== "") {
          answerRaw += (answerRaw && !isBlank(ln) ? "\n" : "") + ln;
        } else {
          // Продолжение вопроса (перенос строки), пока не встретился ответ.
          questionRaw += " " + ln;
        }
      }

      questionRaw = questionRaw.replace(/\s+/g, " ").trim();
      answerRaw = answerRaw.replace(/\s+/g, " ").trim();

      // Если ответа нет, но есть предполагаемая длина ответа — используем для оценки.
      const qStat = textstats.analyze(questionRaw, unit, rate);
      let aStat;
      if (answerRaw) {
        aStat = textstats.analyze(answerRaw, unit, rate);
      } else {
        const assumedWords = assumeAnswerWords || 0;
        const assumedChars = Math.round(assumedWords * 6.5);
        const minutes = textstats.readingMinutes(
          assumedWords,
          assumedChars,
          unit,
          rate
        );
        aStat = { words: assumedWords, chars: assumedChars, charsWithSpaces: assumedChars, minutes };
      }

      questions.push({
        num: cur.num,
        question: questionRaw,
        answer: answerRaw,
        qWords: qStat.words,
        aWords: answerRaw ? aStat.words : 0,
        qChars: qStat.chars,
        aChars: answerRaw ? aStat.chars : 0,
        minutes: qStat.minutes + aStat.minutes,
        preview: questionRaw.slice(0, 140)
      });
    }
    return questions;
  }

  // Fallback: нет явной нумерации. Ищем вопросы по "?" / "Вопрос", ответы — до следующего вопроса.
  function buildFallback(lines, unit, rate, assumeAnswerWords) {
    const questions = [];
    let i = 0;
    while (i < lines.length) {
      if (isBlank(lines[i])) {
        i++;
        continue;
      }
      const qLine = lines[i].trim();
      // Одинокая строка-ответ без вопроса — пропускаем.
      if (ANSWER_RE.test(qLine)) {
        i++;
        continue;
      }
      let j = i + 1;
      const answer = [];
      while (j < lines.length && !isBlank(lines[j])) {
        const ln = lines[j].trim();
        if (ANSWER_RE.test(ln)) {
          answer.push(lines[j]);
          j++;
          continue;
        }
        if (ENDS_Q(ln) || /^(вопрос|question)\b/i.test(ln) || /^\d{1,4}[\.\)]\s/.test(ln)) break;
        answer.push(lines[j]);
        j++;
      }
      const answerText = answer.join(" ").replace(/\s+/g, " ").trim();
      const qStat = textstats.analyze(qLine, unit, rate);
      let aStat;
      if (answerText) {
        aStat = textstats.analyze(answerText, unit, rate);
      } else {
        const assumedWords = assumeAnswerWords || 0;
        const assumedChars = Math.round(assumedWords * 6.5);
        aStat = { words: assumedWords, chars: assumedChars, minutes: textstats.readingMinutes(assumedWords, assumedChars, unit, rate) };
      }
      questions.push({
        num: questions.length + 1,
        question: qLine,
        answer: answerText,
        qWords: qStat.words,
        aWords: answerText ? aStat.words : 0,
        qChars: qStat.chars,
        aChars: answerText ? aStat.chars : 0,
        minutes: qStat.minutes + aStat.minutes,
        preview: qLine.slice(0, 140)
      });
      i = j;
    }
    return questions;
  }

  /*
   * parseDocument(text, options)
   * options: { unit: 'wpm'|'cpm', rate: Number, assumeAnswerWords: Number }
   * Возвращает { questions, strategy, count, totalWords, totalChars, totalMinutes }.
   */
  function parseDocument(text, options) {
    options = options || {};
    const unit = options.unit || "wpm";
    const rate = options.rate || 250;
    const assumeAnswerWords = options.assumeAnswerWords || 0;

    const normalized = (text || "").replace(/\r\n?/g, "\n");
    const lines = normalized.split("\n");

    const starts = findQuestionStarts(lines);
    let questions, strategy;
    if (starts.length >= 2) {
      questions = buildFromStarts(lines, starts, unit, rate, assumeAnswerWords);
      strategy = starts[0].type === "vopros" ? "vopros-otvet" : "numbered";
    } else {
      questions = buildFallback(lines, unit, rate, assumeAnswerWords);
      strategy = "fallback-q";
    }

    let totalWords = 0, totalChars = 0, totalMinutes = 0;
    for (const q of questions) {
      totalWords += q.qWords + q.aWords;
      totalChars += q.qChars + q.aChars;
      totalMinutes += q.minutes;
    }

    return {
      questions,
      strategy,
      count: questions.length,
      totalWords,
      totalChars,
      totalMinutes
    };
  }

  return { parseDocument, NUM_RE, VOPROS_RE, ANSWER_RE };
});
