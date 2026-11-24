/*
 * text.js — статистика текста и нормализация.
 *
 * Ядро приложения. Не зависит ни от Node, ни от браузера: только чистые функции,
 * поэтому один и тот же код работает в главном процессе, в интерфейсе и в тестах.
 *
 * Единицы измерения, принятые в приложении:
 *   слова        — последовательности букв и цифр (кириллица + латиница);
 *   символы      — знаки без пробелов (как в Word «знаков без пробелов»);
 *   символы с пробелами — длина строки после нормализации;
 *   время чтения — минуты, дробное число (не округляем до целых, иначе на 150
 *                  вопросах накапливается ошибка в часы).
 */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof window !== "undefined") {
    window.ExamCore = Object.assign(window.ExamCore || {}, { text: api });
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // Слово: буквы (кириллица, латиница, украинские/белорусские знаки) и цифры.
  // Дефис внутри слова считается частью слова («административно-правовой» — одно слово),
  // как считает Word в русской локали.
  const WORD_RE = /[0-9A-Za-z\u00C0-\u024F\u0400-\u04FF]+(?:[-'\u2019][0-9A-Za-z\u00C0-\u024F\u0400-\u04FF]+)*/g;

  // Служебные слова, которые в устной речи «проглатываются»: они не добавляют
  // времени при чтении вслух и почти не добавляют при чтении про себя.
  const FUNCTION_WORDS = new Set([
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то",
    "все", "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за",
    "бы", "по", "только", "ее", "мне", "было", "вот", "от", "меня", "еще",
    "нет", "о", "об", "из", "ему", "теперь", "когда", "даже", "ну", "вдруг",
    "ли", "если", "уже", "или", "ни", "быть", "был", "него", "до", "вас",
    "нибудь", "опять", "уж", "вам", "ведь", "там", "потом", "себя", "ничего",
    "ей", "может", "они", "тут", "где", "есть", "надо", "ней", "для", "мы",
    "тебя", "их", "чем", "была", "сам", "чтоб", "без", "будто", "чего", "раз",
    "тоже", "себе", "под", "будет", "ж", "тогда", "кто", "этот", "того",
    "потому", "этого", "какой", "совсем", "ним", "здесь", "этом", "один",
    "почти", "мой", "тем", "чтобы", "нее", "были", "куда", "зачем", "всех",
    "никогда", "можно", "при", "наконец", "два", "the", "of", "and",
    "to", "a", "in", "is", "it", "that", "as", "for", "with", "on"
  ]);

  /** Нормализация переводов строк (Windows/старый Mac → \n). */
  function normalizeNewlines(text) {
    return String(text == null ? "" : text).replace(/\r\n?/g, "\n");
  }

  /** Убирает мягкие переносы, неразрывные пробелы и прочий типографский мусор. */
  function cleanText(text) {
    return normalizeNewlines(text)
      .replace(/\uFEFF/g, "")
      .replace(/\u00AD/g, "")
      .replace(/[\u00A0\u2007\u202F]/g, " ")
      .replace(/[\u2018\u2019\u02BC]/g, "'")
      .replace(/\u2014/g, "—")
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n{3,}/g, "\n\n");
  }

  /** Схлопывает все пробельные последовательности в один пробел. */
  function collapseSpaces(text) {
    return String(text == null ? "" : text).replace(/\s+/g, " ").trim();
  }

  /** Число слов. */
  function countWords(text) {
    if (!text) return 0;
    const m = String(text).match(WORD_RE);
    return m ? m.length : 0;
  }

  /** Символы. includeSpaces=false — «знаков без пробелов», как в Word. */
  function countChars(text, includeSpaces) {
    if (!text) return 0;
    const s = String(text);
    return includeSpaces ? s.length : s.replace(/\s/g, "").length;
  }

  /** Знаки препинания — косвенный признак сложности текста (длинные нормы, перечни). */
  function countPunctuation(text) {
    if (!text) return 0;
    const m = String(text).match(/[.,;:!?()«»"—–]/g);
    return m ? m.length : 0;
  }

  /** Доля служебных слов (0..1) — чем выше, тем «легче» текст. */
  function functionWordRatio(text) {
    const words = (String(text || "").toLowerCase().match(WORD_RE) || []);
    if (words.length === 0) return 0;
    let n = 0;
    for (const w of words) if (FUNCTION_WORDS.has(w)) n++;
    return n / words.length;
  }

  /**
   * Индекс сложности текста (1.0 — обычный юридический текст).
   * Нужен, чтобы длинные нормы с перечнями не считались «быстрым чтением»:
   * на них реальная скорость падает.
   */
  function difficultyIndex(text) {
    const wordsArr = (String(text || "").match(WORD_RE) || []);
    const words = wordsArr.length;
    if (words === 0) return 1;
    const chars = countChars(text, false);
    const avgWordLen = chars / words;
    const punct = countPunctuation(text);
    const fnRatio = functionWordRatio(text);
    // Длина слова: 5.5 знака — норма; каждые 0.5 знака сверх — +6% времени.
    const lengthFactor = 1 + Math.max(0, avgWordLen - 5.5) * 0.12;
    // Плотность знаков препинания: 0.10 на слово — норма.
    const punctFactor = 1 + Math.max(0, punct / Math.max(1, words) - 0.1) * 0.8;
    // Мало служебных слов → текст плотный, «терминологический».
    const densityFactor = 1 + Math.max(0, 0.4 - fnRatio) * 0.5;
    return Math.min(2.2, Math.max(0.8, lengthFactor * punctFactor * densityFactor));
  }

  /**
   * Минуты чтения.
   *   rate — выбранная пользователем скорость (слов/мин или знаков/мин);
   *   opts.difficulty — индекс сложности (по умолчанию 1);
   *   opts.speedFactor — множитель скорости для прогона (повтор читается быстрее).
   */
  function readingMinutes(words, chars, unit, rate, opts) {
    opts = opts || {};
    const speed = Math.max(1, rate || 1) * Math.max(0.05, opts.speedFactor || 1);
    const difficulty = opts.difficulty || 1;
    const base = unit === "cpm" ? (chars || 0) / speed : (words || 0) / speed;
    return (base * difficulty) / Math.max(0.4, opts.ease || 1);
  }

  /** Полная статистика блока текста. */
  function analyze(text, unit, rate, opts) {
    const s = cleanText(text);
    const words = countWords(s);
    const chars = countChars(s, false);
    const charsWithSpaces = countChars(s, true);
    const difficulty = difficultyIndex(s);
    const minutes = readingMinutes(words, chars, unit, rate, Object.assign({ difficulty }, opts));
    return {
      words,
      chars,
      charsWithSpaces,
      difficulty,
      punctuation: countPunctuation(s),
      minutes
    };
  }

  /** Человекочитаемая длительность: «2 ч 15 мин», «45 мин», «40 сек». */
  function humanDuration(minutes, opts) {
    opts = opts || {};
    const compact = opts.compact === true;
    if (!isFinite(minutes) || minutes <= 0) return compact ? "0 мин" : "0 мин";
    const totalMin = Math.round(minutes);
    if (totalMin < 1) return "меньше минуты";
    const h = Math.floor(totalMin / 60);
    const m = totalMin % 60;
    if (h > 0 && m > 0) return h + " ч " + m + " мин";
    if (h > 0) return compact ? h + " ч" : h + " ч 0 мин";
    return m + " мин";
  }

  /** «2 ч 15 мин» без нулевых минут — для компактных подписей. */
  function humanDurationShort(minutes) {
    if (!isFinite(minutes) || minutes <= 0) return "0 мин";
    const totalMin = Math.round(minutes);
    if (totalMin < 1) return "<1 мин";
    const h = Math.floor(totalMin / 60);
    const m = totalMin % 60;
    if (h > 0 && m > 0) return h + " ч " + m + " мин";
    if (h > 0) return h + " ч";
    return m + " мин";
  }

  /** «1 234 567» — разряды через неразрывный пробел. */
  function humanNumber(n) {
    const v = Math.round(Number(n) || 0);
    return String(v).replace(/\B(?=(\d{3})+(?!\d))/g, "\u202F");
  }

  /** «1500 слов» / «15 слов» — с правильным падежом. */
  function plural(n, one, few, many) {
    const abs = Math.abs(Math.round(n)) % 100;
    const last = abs % 10;
    if (abs > 10 && abs < 20) return many;
    if (last === 1) return one;
    if (last >= 2 && last <= 4) return few;
    return many;
  }

  /** Обрезка по границе слова. */
  function truncate(text, max) {
    const s = collapseSpaces(text);
    if (s.length <= max) return s;
    const cut = s.slice(0, max);
    const sp = cut.lastIndexOf(" ");
    return (sp > max * 0.6 ? cut.slice(0, sp) : cut).replace(/[,;:.\-—]+$/, "") + "…";
  }

  return {
    WORD_RE,
    FUNCTION_WORDS,
    normalizeNewlines,
    cleanText,
    collapseSpaces,
    countWords,
    countChars,
    countPunctuation,
    functionWordRatio,
    difficultyIndex,
    readingMinutes,
    analyze,
    humanDuration,
    humanDurationShort,
    humanNumber,
    plural,
    truncate
  };
});
