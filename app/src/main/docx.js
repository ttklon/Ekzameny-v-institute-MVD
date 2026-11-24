/*
 * docx.js — извлечение текста из Word (.docx) и OpenDocument (.odt).
 *
 * .docx — это zip с XML. Нам нужен word/document.xml, где текст лежит в <w:t>.
 * Важно сохранить структуру абзацев: парсер ищет границы вопросов по строкам
 * и абзацам, поэтому конец абзаца превращаем в перевод строки, а <w:br> и
 * <w:tab> — в перевод строки и табуляцию.
 */
"use strict";

const JSZip = require("jszip");

function decodeXmlEntities(s) {
  return s
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&#x([0-9a-f]+);/gi, (m, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (m, d) => String.fromCodePoint(parseInt(d, 10)))
    .replace(/&amp;/g, "&");
}

/** XML одного документа Word → текст с переводами строк на границах абзацев. */
function wordXmlToText(xml) {
  let t = String(xml || "");
  // Удаляем служебные блоки, в которых нет видимого текста.
  t = t.replace(/<w:instrText[\s\S]*?<\/w:instrText>/g, "");
  t = t.replace(/<w:delText[\s\S]*?<\/w:delText>/g, "");
  // Разрывы строк и табуляции.
  t = t.replace(/<w:tab\b[^>]*\/>/g, "\t");
  t = t.replace(/<w:br\b[^>]*\/>/g, "\n");
  t = t.replace(/<w:cr\b[^>]*\/>/g, "\n");
  // Конец абзаца и конца ячейки таблицы — перевод строки.
  t = t.replace(/<\/w:p>/g, "\n");
  t = t.replace(/<\/w:tc>/g, "\n");
  // Текст берём только из <w:t>; внутри может быть несколько прогонов подряд.
  let out = "";
  const re = /<w:t(?:\s[^>]*)?>([\s\S]*?)<\/w:t>|<(\/?)(?:w:p|w:tc)\b[^>]*>|\n/g;
  let m;
  while ((m = re.exec(t)) !== null) {
    if (m[1] !== undefined) out += decodeXmlEntities(m[1]);
    else if (m[2] === "/") out += "\n";
    else if (m[0] === "\n") out += "\n";
  }
  return tidy(out);
}

/** ODT: content.xml, текст в <text:p> и <text:h>. */
function odtXmlToText(xml) {
  let t = String(xml || "");
  t = t.replace(/<text:tab\b[^>]*\/>/g, "\t");
  t = t.replace(/<text:line-break\b[^>]*\/>/g, "\n");
  t = t.replace(/<\/text:(p|h)>/g, "\n");
  t = t.replace(/<text:s\b[^>]*\/>/g, " ");
  t = t.replace(/<[^>]+>/g, "");
  return tidy(decodeXmlEntities(t));
}

function tidy(s) {
  return s
    .replace(/\r\n?/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/** Текст .docx из буфера. */
async function extractDocxText(buffer) {
  const zip = await JSZip.loadAsync(buffer);
  const file = zip.file("word/document.xml");
  if (!file) return "";
  const xml = await file.async("string");
  return wordXmlToText(xml);
}

/** Текст .odt из буфера. */
async function extractOdtText(buffer) {
  const zip = await JSZip.loadAsync(buffer);
  const file = zip.file("content.xml");
  if (!file) return "";
  const xml = await file.async("string");
  return odtXmlToText(xml);
}

/** Текст RTF: минимальная поддержка (\\par, \\tab, \\uN, \\'hh в cp1251). */
function extractRtfText(buffer) {
  let s = buffer.toString("latin1");
  const out = [];
  let i = 0;
  const stack = [];
  let skip = false;
  while (i < s.length) {
    const ch = s[i];
    if (ch === "{") {
      stack.push(skip);
      i++;
      continue;
    }
    if (ch === "}") {
      skip = stack.pop() || false;
      i++;
      continue;
    }
    if (ch === "\\") {
      const m = /^\\([a-z]+)(-?\d+)? ?/i.exec(s.slice(i));
      if (m) {
        const word = m[1];
        if (word === "par" || word === "line") out.push("\n");
        else if (word === "tab") out.push("\t");
        else if (word === "u") out.push(String.fromCharCode((parseInt(m[2], 10) + 65536) % 65536));
        else if (word === "fonttbl" || word === "colortbl" || word === "stylesheet" || word === "pict") skip = true;
        else if (word === "ansicpg") { /* кодировка — по умолчанию 1251 */ }
        i += m[0].length;
        continue;
      }
      const hex = /^\\'([0-9a-f]{2})/i.exec(s.slice(i));
      if (hex) {
        out.push(Buffer.from([parseInt(hex[1], 16)]).toString("latin1"));
        i += 4;
        continue;
      }
      i += 2;
      continue;
    }
    if (!skip && ch !== "\n" && ch !== "\r") out.push(ch);
    i++;
  }
  // Байты cp1251 → юникод.
  const raw = Buffer.from(out.join(""), "latin1");
  const iconv = require("iconv-lite");
  return tidy(iconv.decode(raw, "win1251"));
}

module.exports = { extractDocxText, extractOdtText, extractRtfText, wordXmlToText, odtXmlToText };
