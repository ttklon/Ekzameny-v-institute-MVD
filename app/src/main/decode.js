/*
 * decode.js — чтение текстовых файлов с автоматическим определением кодировки.
 *
 * Русские файлы с вопросами встречаются в UTF-8, Windows-1251, UTF-16 (так
 * сохраняет «Блокнот» в Windows) и в виде «кракозябр» из PDF. Здесь всё это
 * приводится к нормальному тексту, чтобы парсер работал одинаково.
 */
"use strict";

const iconv = require("iconv-lite");

/** Оценка «русскости» текста: доля кириллицы среди букв. */
function cyrillicScore(s) {
  let cyr = 0;
  let lat = 0;
  for (let i = 0; i < s.length && i < 60000; i++) {
    const c = s.charCodeAt(i);
    if (c >= 0x0400 && c <= 0x04ff) cyr++;
    else if ((c >= 0x41 && c <= 0x5a) || (c >= 0x61 && c <= 0x7a)) lat++;
  }
  const letters = cyr + lat;
  return letters ? cyr / letters : 0;
}

/** Доля «мусорных» символов — признак неверной кодировки. */
function garbageScore(s) {
  let bad = 0;
  const n = Math.min(s.length, 60000);
  for (let i = 0; i < n; i++) {
    const c = s.charCodeAt(i);
    if (c === 0xfffd || (c >= 0x80 && c <= 0x9f) || c === 0) bad++;
  }
  return n ? bad / n : 0;
}

/** Пробует раскодировать буфер как строгий UTF-8. */
function tryUtf8(buf) {
  try {
    const dec = new TextDecoder("utf-8", { fatal: true });
    return dec.decode(buf);
  } catch (e) {
    return null;
  }
}

/**
 * Декодирует буфер в строку, выбирая лучшую из кодировок по качеству текста.
 * Возвращает { text, encoding }.
 */
function decodeBuffer(buf, hint) {
  if (!buf || buf.length === 0) return { text: "", encoding: "utf-8" };

  // BOM.
  if (buf.length >= 3 && buf[0] === 0xef && buf[1] === 0xbb && buf[2] === 0xbf) {
    return { text: iconv.decode(buf.slice(3), "utf-8"), encoding: "utf-8-bom" };
  }
  if (buf.length >= 2 && buf[0] === 0xff && buf[1] === 0xfe) {
    return { text: iconv.decode(buf.slice(2), "utf-16le"), encoding: "utf-16le" };
  }
  if (buf.length >= 2 && buf[0] === 0xfe && buf[1] === 0xff) {
    return { text: iconv.decode(buf.slice(2), "utf-16be"), encoding: "utf-16be" };
  }

  // UTF-16 без BOM: много нулевых байтов в чётных позициях.
  let zerosEven = 0;
  let zerosOdd = 0;
  const probe = Math.min(buf.length, 4000);
  for (let i = 0; i < probe; i++) {
    if (buf[i] === 0) (i % 2 === 0 ? zerosEven++ : zerosOdd++);
  }
  if (probe > 20 && zerosEven > probe * 0.2 && zerosOdd < probe * 0.05) {
    return { text: iconv.decode(buf, "utf-16le"), encoding: "utf-16le" };
  }
  if (probe > 20 && zerosOdd > probe * 0.2 && zerosEven < probe * 0.05) {
    return { text: iconv.decode(buf, "utf-16be"), encoding: "utf-16be" };
  }

  const candidates = [];
  const utf8 = tryUtf8(buf);
  if (utf8 !== null) candidates.push({ text: utf8, encoding: "utf-8" });
  candidates.push({ text: iconv.decode(buf, "win1251"), encoding: "windows-1251" });
  candidates.push({ text: iconv.decode(buf, "koi8-r"), encoding: "koi8-r" });
  if (hint === "win1251" || hint === "koi8-r") {
    candidates.sort((a, b) => (a.encoding === hint ? -1 : b.encoding === hint ? 1 : 0));
  }

  let best = candidates[0];
  let bestScore = -1;
  for (const c of candidates) {
    const score = cyrillicScore(c.text) * 2 - garbageScore(c.text) * 4 + (c.encoding === "utf-8" ? 0.15 : 0);
    if (score > bestScore) {
      bestScore = score;
      best = c;
    }
  }
  return best;
}

module.exports = { decodeBuffer, cyrillicScore, garbageScore, tryUtf8 };
