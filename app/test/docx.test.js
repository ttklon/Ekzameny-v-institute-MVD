/*
 * docx.test.js — проверка извлечения текста из .docx и последующего парсинга.
 * Собираем минимальный валидный .docx через JSZip и прогоняем через docx + parser.
 */
const JSZip = require("jszip");
const docx = require("../src/docx");
const parser = require("../src/core/parser");

const CONTENT_TYPES =
  '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +
  '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
  '<Default Extension="xml" ContentType="application/xml"/>' +
  '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>';
const RELS =
  '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
  '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>';
const DOCUMENT =
  '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' +
  "<w:p><w:r><w:t>1. Понятие административной деятельности полиции?</w:t></w:r></w:p>" +
  "<w:p><w:r><w:t>Ответ: это вид государственной деятельности, осуществляемый полицией.</w:t></w:r></w:p>" +
  "<w:p><w:r><w:t>2. Формы и методы административной деятельности.</w:t></w:r></w:p>" +
  "<w:p><w:r><w:t>Ответ: убеждение и принуждение, административные регламенты.</w:t></w:r></w:p>" +
  "</w:body></w:document>";

async function buildDocx() {
  const zip = new JSZip();
  zip.file("[Content_Types].xml", CONTENT_TYPES);
  zip.folder("_rels").file(".rels", RELS);
  zip.folder("word").file("document.xml", DOCUMENT);
  return zip.generateAsync({ type: "nodebuffer" });
}

(async () => {
  const buf = await buildDocx();
  const text = await docx.extractDocxText(buf);
  const errors = [];

  if (!/1\. Понятие административной/.test(text)) errors.push("текст вопроса 1 не извлечён");
  if (!/Ответ: это вид/.test(text)) errors.push("текст ответа не извлечён");
  if (/<w:t>/.test(text)) errors.push("в тексте остались XML-теги");

  const parsed = parser.parseDocument(text, { unit: "wpm", rate: 250, assumeAnswerWords: 0 });
  if (parsed.count < 2) errors.push("парсер не нашёл ≥2 вопросов (нашёл " + parsed.count + ")");
  const q1 = parsed.questions[0];
  if (!q1.answer || !/это вид/.test(q1.answer)) errors.push("ответ не отделён от вопроса у Q1");

  if (errors.length) {
    console.log("❌ ОШИБКИ docx:");
    errors.forEach((e) => console.log("  - " + e));
    process.exit(1);
  }
  console.log("✅ docx: текст из Word извлечён, XML очищен, найдено вопросов:", parsed.count, ", Q1 имеет ответ:", JSON.stringify(q1.answer));
  process.exit(0);
})();
