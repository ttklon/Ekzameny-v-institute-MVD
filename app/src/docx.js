/*
 * docx.js — извлечение текста из Word .docx (zip + XML).
 * Используется в главном процессе (Node). Возвращает читаемый текст,
 * пригодный для подачи в парсер вопрос-ответ.
 */
const JSZip = require("jszip");

function xmlToText(xml) {
  let t = xml;
  // Табуляции и разрывы строк внутри Word.
  t = t.replace(/<w:tab\s*\/?>/g, "\t");
  t = t.replace(/<w:br\s*\/?>/g, "\n");
  t = t.replace(/<w:cr\s*\/?>/g, "\n");
  // Конец абзаца — новая строка.
  t = t.replace(/<\/w:p>/g, "\n");
  // Вырезаем всё, кроме текстовых узлов <w:t>. Сначала достаём текст из <w:t>...</w:t>.
  t = t.replace(/<w:t[^>]*>([\s\S]*?)<\/w:t>/g, "$1\n");
  // Удаляем остальные теги.
  t = t.replace(/<[^>]+>/g, "");
  // Декодируем сущности XML.
  t = t
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&#(\d+);/g, (m, c) => String.fromCharCode(parseInt(c, 10)))
    .replace(/&amp;/g, "&");
  // Схлопываем лишние пустые строки.
  t = t.replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n");
  return t.trim();
}

async function extractDocxText(buffer) {
  const zip = await JSZip.loadAsync(buffer);
  const file = zip.file("word/document.xml");
  if (!file) return "";
  const xml = await file.async("string");
  return xmlToText(xml);
}

module.exports = { extractDocxText, xmlToText };
