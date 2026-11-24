/*
 * textstats.js — статистика текста (слова, символы, время чтения).
 * Чистый модуль: работает и в Node, и в renderer (через UMD-обёртку).
 */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof window !== "undefined") window.ExamCore = Object.assign(window.ExamCore || {}, { textstats: api });
})(typeof self !== "undefined" ? self : this, function () {
  // Слово = последовательность букв (кириллица + латиница) и цифр.
  const WORD_RE = /[A-Za-zА-Яа-яЁё0-9]+/g;

  function countWords(text) {
    if (!text) return 0;
    const m = text.match(WORD_RE);
    return m ? m.length : 0;
  }

  function countChars(text, includeSpaces) {
    if (!text) return 0;
    if (includeSpaces) return text.length;
    // Символы без пробелов и переводов строк.
    return text.replace(/\s/g, "").length;
  }

  // Время чтения в минутах.
  // unit: 'wpm' (слов/мин) или 'cpm' (знаков/мин).
  function readingMinutes(words, chars, unit, rate) {
    if (unit === "cpm") {
      return chars / Math.max(1, rate);
    }
    return words / Math.max(1, rate);
  }

  // Полная статистика блока текста.
  function analyze(text, unit, rate) {
    const words = countWords(text);
    const chars = countChars(text, false);
    const charsWithSpaces = countChars(text, true);
    const minutes = readingMinutes(words, chars, unit, rate);
    return { words, chars, charsWithSpaces, minutes };
  }

  // Краткая человекочитаемая длительность: "1 ч 25 мин", "40 мин", "12 сек".
  function humanDuration(minutes) {
    if (!isFinite(minutes) || minutes <= 0) return "0 мин";
    const totalSec = Math.round(minutes * 60);
    const h = Math.floor(totalSec / 3600);
    const m = Math.floor((totalSec % 3600) / 60);
    const s = totalSec % 60;
    if (h > 0) return `${h} ч ${m} мин`;
    if (m > 0) return `${m} мин`;
    return `${s} сек`;
  }

  return { countWords, countChars, readingMinutes, analyze, humanDuration, WORD_RE };
});
