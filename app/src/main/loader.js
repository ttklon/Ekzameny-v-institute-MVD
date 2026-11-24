/*
 * loader.js — приём файлов: определяет тип, читает, декодирует, разбирает.
 *
 * Поддерживаются: .txt, .md, .docx, .doc (как текст, если это XML/HTML),
 * .odt, .rtf, .pdf, .html/.htm, .csv/tsv и просто перетаскивание текста.
 */
"use strict";

const fs = require("fs");
const path = require("path");
const { decodeBuffer } = require("./decode");
const { extractDocxText, extractOdtText, extractRtfText } = require("./docx");
const { extractPdf } = require("./pdf");

const MAX_BYTES = 400 * 1024 * 1024; // 400 МБ — с запасом для больших сборников

/** HTML → текст: убираем скрипты и теги, сохраняем абзацы. */
function htmlToText(html) {
  let t = String(html || "");
  t = t.replace(/<script[\s\S]*?<\/script>/gi, "");
  t = t.replace(/<style[\s\S]*?<\/style>/gi, "");
  t = t.replace(/<head[\s\S]*?<\/head>/gi, "");
  t = t.replace(/<br\s*\/?>/gi, "\n");
  t = t.replace(/<\/(p|div|h[1-6]|li|tr|td)>/gi, "\n");
  t = t.replace(/<[^>]+>/g, "");
  t = t
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#(\d+);/g, (m, d) => String.fromCharCode(parseInt(d, 10)));
  return t.replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
}

/** Определяет формат по расширению и сигнатуре файла. */
function detectKind(filePath, buf) {
  const ext = path.extname(filePath || "").toLowerCase();
  const head = buf.slice(0, 4096);
  const asText = head.toString("latin1");

  if (ext === ".pdf" || asText.startsWith("%PDF-")) return "pdf";
  if (ext === ".docx" || (head[0] === 0x50 && head[1] === 0x4b && ext !== ".odt")) {
    if (buf.includes(Buffer.from("word/document.xml"))) return "docx";
    if (buf.includes(Buffer.from("content.xml"))) return "odt";
    if (ext === ".docx") return "docx";
  }
  if (ext === ".odt") return "odt";
  if (ext === ".rtf" || asText.startsWith("{\\rtf")) return "rtf";
  if (ext === ".html" || ext === ".htm" || /<html|<!doctype html/i.test(asText)) return "html";
  if (ext === ".doc") return "doc-legacy";
  return "text";
}

/**
 * readFile(filePath, opts)
 * Возвращает { ok, name, path, kind, text, bytes, encoding, warnings, pages }.
 */
async function readFile(filePath, opts) {
  opts = opts || {};
  const warnings = [];
  let buf;
  try {
    const st = fs.statSync(filePath);
    if (st.size > MAX_BYTES) {
      return {
        ok: false,
        error: "Файл больше 400 МБ — разделите его на части."
      };
    }
    buf = fs.readFileSync(filePath);
  } catch (err) {
    return { ok: false, error: "Не удалось прочитать файл: " + (err.message || err) };
  }

  const kind = detectKind(filePath, buf);
  const name = path.basename(filePath);
  let text = "";
  let encoding = "";
  let pages = 0;

  try {
    if (kind === "pdf") {
      const r = await extractPdf(buf, { pages: opts.maxPages });
      text = r.text;
      pages = r.pages;
      encoding = "pdf";
      for (const w of r.warnings) warnings.push(w);
    } else if (kind === "docx") {
      text = await extractDocxText(buf);
      encoding = "docx";
      if (!text.trim()) {
        warnings.push({
          type: "empty-docx",
          text: "В документе Word не найден текст. Возможно, он состоит из картинок."
        });
      }
    } else if (kind === "odt") {
      text = await extractOdtText(buf);
      encoding = "odt";
    } else if (kind === "rtf") {
      text = extractRtfText(buf);
      encoding = "rtf";
    } else if (kind === "html") {
      const dec = decodeBuffer(buf);
      text = htmlToText(dec.text);
      encoding = dec.encoding + "+html";
    } else if (kind === "doc-legacy") {
      // Старый .doc — двоичный формат. Пробуем вытащить текст: часто это HTML
      // или RTF, сохранённый с расширением .doc.
      const asText = buf.toString("latin1");
      if (asText.startsWith("{\\rtf")) {
        text = extractRtfText(buf);
        encoding = "rtf";
      } else if (/<html|charset/i.test(asText.slice(0, 4096))) {
        const dec = decodeBuffer(buf);
        text = htmlToText(dec.text);
        encoding = dec.encoding + "+html";
      } else {
        const dec = decodeBuffer(buf);
        // В бинарном .doc много нулевых байтов и служебных последовательностей.
        const printable = dec.text.replace(/[^\x09\x0a\x0d\x20-\x7e\u0400-\u04ff]/g, "").length;
        text = dec.text;
        encoding = dec.encoding;
        if (printable / Math.max(1, dec.text.length) < 0.7) {
          warnings.push({
            type: "doc-legacy",
            text:
              "Формат .doc (старый Word) прочитан приблизительно. Если текст получился нечитаемым, " +
              "откройте файл в Word и сохраните как .docx."
          });
        }
      }
    } else {
      const dec = decodeBuffer(buf);
      text = dec.text;
      encoding = dec.encoding;
      // Табличный текст (csv) — просто заменяем разделители на пробелы.
      if (/\.(csv|tsv)$/i.test(name)) {
        text = text.replace(/[\t;]+/g, " ").replace(/,(?=\S)/g, ", ");
      }
    }
  } catch (err) {
    return {
      ok: false,
      error: "Не удалось разобрать файл (" + kind + "): " + (err && err.message ? err.message : err)
    };
  }

  text = text.replace(/\u0000/g, "").trim();

  if (!text) {
    return {
      ok: false,
      error: "Файл прочитан, но текста в нём нет. Если это скан или картинки — нужен текстовый файл."
    };
  }

  return {
    ok: true,
    name: name,
    path: filePath,
    kind: kind,
    text: text,
    bytes: buf.length,
    encoding: encoding,
    pages: pages,
    warnings: warnings
  };
}

/** Имена файлов в папке — для «добавить всю папку». */
function listTextFiles(dir) {
  try {
    return fs
      .readdirSync(dir, { withFileTypes: true })
      .filter((e) => e.isFile())
      .map((e) => path.join(dir, e.name))
      .filter((p) => /\.(txt|md|docx|doc|odt|rtf|pdf|html?|csv|tsv)$/i.test(p));
  } catch (e) {
    return [];
  }
}

module.exports = { readFile, detectKind, htmlToText, listTextFiles };
