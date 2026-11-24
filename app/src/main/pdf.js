/*
 * pdf.js — извлечение текста из PDF.
 *
 * Основной путь — pdf.js (pdfjs-dist): он правильно читает шрифты с картами
 * символов, поэтому русский текст из юридических PDF получается связным.
 * Если модуль недоступен (например, его не включили в сборку), используется
 * собственный разбор из pdf-builtin.js.
 *
 * Скачанные PDF сохраняются целиком: pdf.js читает их из памяти, ничего не
 * записывая на диск, и это работает в том числе для файлов на 100 МБ.
 */
"use strict";

let pdfjsPromise = null;

function loadPdfjs() {
  if (!pdfjsPromise) {
    pdfjsPromise = import("pdfjs-dist/legacy/build/pdf.mjs").catch((err) => {
      pdfjsPromise = null;
      throw err;
    });
  }
  return pdfjsPromise;
}

/** Собирает текст страницы из элементов pdf.js, сохраняя строки и абзацы. */
function pageTextFromItems(items) {
  let out = "";
  let lastY = null;
  let lastX = null;
  for (const item of items) {
    if (typeof item.str !== "string") continue;
    const tr = item.transform || [1, 0, 0, 1, 0, 0];
    const x = tr[4];
    const y = tr[5];
    if (lastY !== null && Math.abs(y - lastY) > 2) {
      // Новая строка. Большой вертикальный разрыв — пустая строка (абзац).
      out += Math.abs(y - lastY) > 14 ? "\n\n" : "\n";
    } else if (lastX !== null && x - lastX > 2 && out && !/[\s\n]$/.test(out)) {
      out += " ";
    }
    out += item.str;
    lastY = y;
    lastX = x + (item.width || 0);
    if (item.hasEOL) {
      out += "\n";
      lastY = null;
      lastX = null;
    }
  }
  return out;
}

/**
 * extractPdf(buffer, opts)
 * opts.pages — ограничение числа страниц (по умолчанию все).
 * Возвращает { text, pages, hasText, engine, warnings }.
 */
async function extractPdf(buffer, opts) {
  opts = opts || {};
  const warnings = [];
  let text = "";
  let pages = 0;
  let engine = "pdfjs";

  try {
    const pdfjs = await loadPdfjs();
    const data = new Uint8Array(buffer);
    const doc = await pdfjs.getDocument({
      data: data,
      // Отключаем всё, что требует файловой системы или сети.
      isEvalSupported: false,
      disableFontFace: true,
      useSystemFonts: false,
      verbosity: 0
    }).promise;

    pages = doc.numPages;
    const limit = opts.pages ? Math.min(opts.pages, pages) : pages;
    const chunks = [];
    for (let p = 1; p <= limit; p++) {
      const page = await doc.getPage(p);
      const content = await page.getTextContent();
      const t = pageTextFromItems(content.items);
      if (t.trim()) chunks.push(t.trim());
      page.cleanup();
    }
    text = chunks.join("\n\n");
    try {
      doc.destroy();
    } catch (e) {
      /* ничего */
    }
  } catch (err) {
    engine = "builtin";
    warnings.push({
      type: "pdf-fallback",
      text: "Основной разбор PDF недоступен (" + (err && err.message ? err.message : err) + "), использован резервный."
    });
    try {
      const builtin = require("./pdf-builtin").extractPdfText(buffer);
      text = builtin.text;
      pages = builtin.pages;
    } catch (e2) {
      text = "";
    }
  }

  text = tidyPdfText(text);
  const cyr = (text.match(/[\u0400-\u04ff]/g) || []).length;
  const letters = (text.match(/[A-Za-z\u0400-\u04ff]/g) || []).length;
  const hasText = letters > 200 && cyr / Math.max(1, letters) > 0.15;

  if (!hasText) {
    warnings.push({
      type: "pdf-no-text",
      text:
        "В PDF не найден текстовый слой — похоже, это скан или фотография. " +
        "Сохраните файл как .txt (или .docx) либо распознайте его, иначе вопросы не разобрать."
    });
  }

  return { text: text, pages: pages, hasText: hasText, engine: engine, warnings: warnings };
}

/** Чистка типичных артефактов PDF: переносы, разреженные пробелы, колонтитулы. */
function tidyPdfText(text) {
  let t = String(text || "")
    .replace(/\r\n?/g, "\n")
    // Мягкие переносы слов на границе строки: «уго-\nловно» → «уголовно».
    .replace(/([а-яёa-z])-\s*\n\s*([а-яёa-z])/gi, "$1$2")
    // Разрывы внутри слова, появившиеся из-за кернинга: «административн о-правовой».
    .replace(/([а-яёa-z])\s+([а-яёa-z])\s*\n/gi, "$1$2\n")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/ *\n */g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  // Повторяющиеся колонтитулы: одинаковая короткая строка на многих страницах.
  const lines = t.split("\n");
  const counts = new Map();
  for (const ln of lines) {
    const s = ln.trim();
    if (s.length > 3 && s.length < 80) counts.set(s, (counts.get(s) || 0) + 1);
  }
  const repeated = new Set();
  for (const [s, n] of counts) if (n >= 4) repeated.add(s);
  if (repeated.size) {
    const kept = [];
    for (let i = 0; i < lines.length; i++) {
      const s = lines[i].trim();
      const atEdge = i < 3 || i > lines.length - 4;
      if (repeated.has(s) && (atEdge || /^\d+$/.test(s) || /^[-–—\s]*\d+[-–—\s]*$/.test(s))) continue;
      kept.push(lines[i]);
    }
    t = kept.join("\n").replace(/\n{3,}/g, "\n\n").trim();
  }
  return t;
}

module.exports = { extractPdf, tidyPdfText };
