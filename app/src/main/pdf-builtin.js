/*
 * pdf.js — извлечение текста из PDF без внешних программ.
 *
 * PDF — это контейнер с потоками. Текст в нём лежит в потоке содержимого
 * страницы командами Tj/TJ, часто со сжатием FlateDecode и шрифтами с
 * собственными таблицами символов (CID). Здесь реализовано чтение без
 * сторонних зависимостей:
 *   • разбор объектов и потоков (в том числе в object streams);
 *   • распаковка FlateDecode через встроенный zlib;
 *   • карты символов ToUnicode (CMap) для шрифтов с двухбайтовыми кодами;
 *   • сборка строк из Tj/TJ/'/" с учётом переводов строк (Td/TD/T*).
 *
 * Это резервный путь: основной разбор PDF делает pdf.js (см. pdf.js), который
 * точнее читает шрифты и таблицы. Здесь остаётся разбор на случай, если модуль
 * pdf.js недоступен. Сканы без текстового слоя не читаются ни тем, ни другим:
 * для них нужно распознавание, о чём приложение и предупреждает.
 */
"use strict";

const zlib = require("zlib");

// ---------- Разбор контейнера ----------

/** Находит все объекты вида «N G obj … endobj». */
function findObjects(buf) {
  const text = buf.toString("latin1");
  const objects = new Map();
  const re = /(\d+)\s+(\d+)\s+obj\b/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    const start = m.index + m[0].length;
    const end = text.indexOf("endobj", start);
    if (end === -1) break;
    const body = text.slice(start, end);
    objects.set(Number(m[1]), parseObjectBody(body));
  }
  return objects;
}

/** Разбирает тело объекта: словарь + возможный поток. */
function parseObjectBody(body) {
  const streamIdx = body.indexOf("stream");
  if (streamIdx === -1) {
    return { dict: body, stream: null };
  }
  const dict = body.slice(0, streamIdx);
  let dataStart = streamIdx + 6;
  if (body[dataStart] === "\r") dataStart++;
  if (body[dataStart] === "\n") dataStart++;
  let dataEnd = body.lastIndexOf("endstream");
  if (dataEnd === -1) dataEnd = body.length;
  const raw = body.slice(dataStart, dataEnd);
  return { dict: dict, stream: raw };
}

/** Достаёт число из словаря объекта. */
function dictNumber(dict, key) {
  const m = new RegExp("/" + key + "\\s+(\\d+)").exec(dict);
  return m ? Number(m[1]) : null;
}

/** Достаёт ссылку «/Key N 0 R». */
function dictRef(dict, key) {
  const m = new RegExp("/" + key + "\\s+(\\d+)\\s+\\d+\\s+R").exec(dict);
  return m ? Number(m[1]) : null;
}

/** Достаёт массив чисел «/Key [ … ]». */
function dictNumberArray(dict, key) {
  const m = new RegExp("/" + key + "\\s*\\[([^\\]]*)\\]").exec(dict);
  if (!m) return null;
  const nums = m[1].match(/-?\d+(\.\d+)?/g);
  return nums ? nums.map(Number) : null;
}

/** Распаковывает поток с учётом фильтров. */
function decodeStream(obj) {
  if (!obj || !obj.stream) return "";
  const dict = obj.dict || "";
  let data = Buffer.from(obj.stream, "latin1");
  if (/\/FlateDecode/.test(dict)) {
    try {
      data = zlib.inflateSync(data);
    } catch (e) {
      try {
        data = zlib.inflateRawSync(data);
      } catch (e2) {
        try {
          data = zlib.gunzipSync(data);
        } catch (e3) {
          return "";
        }
      }
    }
  } else if (/\/ASCIIHexDecode/.test(dict)) {
    const hex = data.toString("latin1").replace(/[^0-9a-f]/gi, "");
    data = Buffer.from(hex, "hex");
  } else if (/\/LZWDecode/.test(dict)) {
    data = lzwDecode(data);
  }
  // Предиктор PNG (используется в object streams и в xref-потоках).
  const predictor = dictNumber(dict, "Predictor");
  if (predictor && predictor >= 10) {
    const columns = dictNumber(dict, "Columns") || 1;
    data = pngUnpredict(data, columns);
  }
  return data.toString("latin1");
}

function lzwDecode(buf) {
  const out = [];
  let dict = [];
  for (let i = 0; i < 256; i++) dict.push(String.fromCharCode(i));
  let codeLen = 9;
  let prev = null;
  let bitBuf = 0;
  let bitCnt = 0;
  dict.push(null);
  dict.push(null);
  for (let i = 0; i < buf.length; i++) {
    bitBuf = (bitBuf << 8) | buf[i];
    bitCnt += 8;
    while (bitCnt >= codeLen) {
      const code = (bitBuf >> (bitCnt - codeLen)) & ((1 << codeLen) - 1);
      bitCnt -= codeLen;
      if (code === 256) {
        dict = dict.slice(0, 258);
        codeLen = 9;
        prev = null;
        continue;
      }
      if (code === 257) return Buffer.from(out.join(""), "latin1");
      let entry;
      if (code < dict.length && dict[code] != null) entry = dict[code];
      else if (prev != null) entry = prev + prev[0];
      else entry = "";
      out.push(entry);
      if (prev != null) dict.push(prev + entry[0]);
      prev = entry;
      if (dict.length + 1 >= 1 << codeLen && codeLen < 12) codeLen++;
    }
  }
  return Buffer.from(out.join(""), "latin1");
}

function pngUnpredict(data, columns) {
  const rowLen = columns + 1;
  const out = Buffer.alloc(Math.floor(data.length / rowLen) * columns);
  let prev = Buffer.alloc(columns);
  let o = 0;
  for (let p = 0; p + rowLen <= data.length; p += rowLen) {
    const type = data[p];
    const row = data.slice(p + 1, p + rowLen);
    for (let i = 0; i < columns; i++) {
      const left = i > 0 ? row[i - 1] : 0;
      const up = prev[i];
      const upLeft = i > 0 ? prev[i - 1] : 0;
      let v = row[i];
      if (type === 1) v = (v + left) & 0xff;
      else if (type === 2) v = (v + up) & 0xff;
      else if (type === 3) v = (v + ((left + up) >> 1)) & 0xff;
      else if (type === 4) {
        const pa = Math.abs(up - upLeft);
        const pb = Math.abs(left - upLeft);
        const pc = Math.abs(left + up - 2 * upLeft);
        const pred = pa <= pb && pa <= pc ? left : pb <= pc ? up : upLeft;
        v = (v + pred) & 0xff;
      }
      row[i] = v;
    }
    row.copy(out, o);
    o += columns;
    prev = row;
  }
  return out;
}

// ---------- Разбор CMap (ToUnicode) ----------

/**
 * Строит карту «код → строка» из CMap.
 * Поддерживает bfchar/bfrange и коды переменной длины.
 */
function parseCMap(cmapText) {
  const map = new Map();
  const hexToStr = (hex) => {
    const clean = hex.replace(/[^0-9a-f]/gi, "");
    let s = "";
    for (let i = 0; i + 3 < clean.length + 1; i += 4) {
      s += String.fromCharCode(parseInt(clean.slice(i, i + 4), 16));
    }
    return s;
  };

  const charRe = /beginbfchar([\s\S]*?)endbfchar/g;
  let m;
  while ((m = charRe.exec(cmapText)) !== null) {
    const body = m[1];
    const pairRe = /<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]*)>/g;
    let p;
    while ((p = pairRe.exec(body)) !== null) {
      map.set(parseInt(p[1], 16), hexToStr(p[2]));
    }
  }

  const rangeRe = /beginbfrange([\s\S]*?)endbfrange/g;
  while ((m = rangeRe.exec(cmapText)) !== null) {
    const body = m[1];
    const rRe = /<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>\s*(<([0-9a-fA-F]*)>|\[([^\]]*)\])/g;
    let r;
    while ((r = rRe.exec(body)) !== null) {
      const lo = parseInt(r[1], 16);
      const hi = parseInt(r[2], 16);
      if (r[4] !== undefined) {
        const base = r[4];
        for (let c = lo; c <= hi && c - lo < 65536; c++) {
          // Приращение к последнему коду строки.
          const inc = c - lo;
          const clean = base.replace(/[^0-9a-f]/gi, "");
          const lastHex = clean.slice(-4);
          const last = parseInt(lastHex, 16) + inc;
          const prefix = clean.slice(0, -4);
          map.set(c, hexToStr(prefix + last.toString(16).padStart(4, "0")));
        }
      } else if (r[5] !== undefined) {
        const items = r[5].match(/<([0-9a-fA-F]*)>/g) || [];
        items.forEach((it, i) => {
          map.set(lo + i, hexToStr(it.replace(/[<>]/g, "")));
        });
      }
    }
  }
  return map;
}

// ---------- Извлечение текста со страниц ----------

/** Достаёт строку «(…)» из литерала PDF с обработкой escape-последовательностей. */
function readLiteralString(src, start) {
  let i = start + 1;
  let depth = 1;
  let out = "";
  while (i < src.length) {
    const ch = src[i];
    if (ch === "\\") {
      const nx = src[i + 1];
      if (nx === "n") out += "\n";
      else if (nx === "r") out += "\r";
      else if (nx === "t") out += "\t";
      else if (nx === "b") out += "\b";
      else if (nx === "f") out += "\f";
      else if (nx === "(") out += "(";
      else if (nx === ")") out += ")";
      else if (nx === "\\") out += "\\";
      else if (/[0-7]/.test(nx)) {
        const oct = /^[0-7]{1,3}/.exec(src.slice(i + 1))[0];
        out += String.fromCharCode(parseInt(oct, 8));
        i += oct.length;
        continue;
      } else if (nx === "\n") {
        /* перенос строки внутри строки — игнорируется */
      } else out += nx;
      i += 2;
      continue;
    }
    if (ch === "(") depth++;
    if (ch === ")") {
      depth--;
      if (depth === 0) return { value: out, end: i + 1 };
    }
    out += ch;
    i++;
  }
  return { value: out, end: i };
}

/**
 * Разбирает поток содержимого страницы и собирает текст.
 * fontMaps — карта «имя ресурса шрифта → CMap».
 */
function contentToText(content, fontMaps) {
  const out = [];
  let currentMap = null;
  let pendingNewline = false;
  let lineY = null;
  let i = 0;
  const n = content.length;

  const pushText = (bytes) => {
    let s = "";
    if (currentMap && currentMap.size) {
      // Двухбайтовые коды (CID-шрифты) — обычное дело в русских PDF.
      for (let k = 0; k + 1 < bytes.length; k += 2) {
        const code = (bytes.charCodeAt(k) << 8) | bytes.charCodeAt(k + 1);
        if (currentMap.has(code)) {
          s += currentMap.get(code);
        } else {
          const single = bytes.charCodeAt(k);
          if (currentMap.has(single)) s += currentMap.get(single);
        }
      }
      if (!s) {
        for (let k = 0; k < bytes.length; k++) {
          const c = bytes.charCodeAt(k);
          if (currentMap.has(c)) s += currentMap.get(c);
        }
      }
    }
    if (!s) {
      // Без CMap считаем байты однобайтовой кодировкой.
      s = bytes;
      if (/[\u0080-\u00ff]/.test(s)) {
        const win = Buffer.from(s, "latin1").toString("latin1");
        s = winToUnicode(win);
      }
    }
    if (!s) return;
    if (pendingNewline && out.length) out.push("\n");
    pendingNewline = false;
    out.push(s);
  };

  while (i < n) {
    const ch = content[i];
    if (ch === "(") {
      const r = readLiteralString(content, i);
      pushText(r.value);
      i = r.end;
      continue;
    }
    if (ch === "<" && content[i + 1] !== "<") {
      const end = content.indexOf(">", i);
      if (end === -1) break;
      const hex = content.slice(i + 1, end).replace(/[^0-9a-f]/gi, "");
      // Чётные пары — байты.
      let bytes = "";
      for (let k = 0; k + 1 < hex.length; k += 2) {
        bytes += String.fromCharCode(parseInt(hex.slice(k, k + 2), 16));
      }
      pushText(bytes);
      i = end + 1;
      continue;
    }
    if (ch === "[") {
      // Массив строк для TJ — обычно с кернингом; разбираем по одной.
      i++;
      continue;
    }
    if (ch === "T" && /^T[dD]\b/.test(content.slice(i))) {
      pendingNewline = true;
      i += 2;
      continue;
    }
    if (ch === "T" && /^T\*/.test(content.slice(i))) {
      pendingNewline = true;
      i += 2;
      continue;
    }
    if (ch === "T" && /^Tf\b/.test(content.slice(i))) {
      // Смена шрифта: «/F1 12 Tf» — запоминаем карту.
      const back = content.slice(Math.max(0, i - 40), i);
      const fm = /\/([A-Za-z0-9_.+-]+)\s+[\d.]+\s*$/.exec(back);
      if (fm) currentMap = fontMaps.get(fm[1]) || null;
      i += 2;
      continue;
    }
    if (ch === "T" && /^TJ\b/.test(content.slice(i))) {
      i += 2;
      continue;
    }
    if (ch === "'" || ch === '"') {
      pendingNewline = true;
      i++;
      continue;
    }
    if (ch === "E" && /^ET\b/.test(content.slice(i))) {
      i += 2;
      continue;
    }
    i++;
  }
  return out.join("").replace(/[ \t]{2,}/g, " ").replace(/\n{3,}/g, "\n\n").trim();
}

/** cp1251 → юникод для PDF без ToUnicode. */
function winToUnicode(s) {
  const iconv = require("iconv-lite");
  return iconv.decode(Buffer.from(s, "latin1"), "win1251");
}

/**
 * Основная функция: извлекает текст из PDF-буфера.
 * Возвращает { text, pages, hasText }.
 */
function extractPdfText(buffer) {
  const objects = findObjects(buffer);

  // Object streams: объекты, упакованные внутрь потоков ObjStm.
  for (const [num, obj] of objects) {
    if (obj.stream && /\/ObjStm/.test(obj.dict)) {
      const content = decodeStream(obj);
      const first = dictNumber(obj.dict, "First") || 0;
      const count = dictNumber(obj.dict, "N") || 0;
      const head = content.slice(0, first).trim().split(/\s+/);
      for (let k = 0; k + 1 < head.length && k / 2 < count; k += 2) {
        const onum = Number(head[k]);
        const off = Number(head[k + 1]);
        const nextOff = Number(head[k + 3] || content.length - first);
        const bodyStart = first + off;
        const bodyEnd = k + 3 < head.length ? first + nextOff : content.length;
        if (!objects.has(onum)) {
          objects.set(onum, parseObjectBody(content.slice(bodyStart, bodyEnd)));
        }
      }
    }
  }

  // Шрифты и их карты символов.
  const fontMaps = new Map(); // имя ресурса → CMap
  const fontRefMaps = new Map(); // номер объекта шрифта → CMap
  for (const [num, obj] of objects) {
    if (!/\/Type\s*\/Font/.test(obj.dict)) continue;
    const tuRef = dictRef(obj.dict, "ToUnicode");
    let cmap = null;
    if (tuRef && objects.has(tuRef)) {
      cmap = parseCMap(decodeStream(objects.get(tuRef)));
    }
    fontRefMaps.set(num, cmap);
    const nameM = /\/BaseFont\s*\/([^\s/>]+)/.exec(obj.dict);
    if (nameM && cmap) fontMaps.set(nameM[1], cmap);
  }

  // Ресурсы страниц: соответствие «/F1 → объект шрифта».
  const pageFonts = new Map(); // номер объекта страницы → Map(имя → cmap)
  for (const [num, obj] of objects) {
    if (!/\/Type\s*\/Page\b/.test(obj.dict) || /\/Pages\b/.test(obj.dict)) continue;
    const resRef = dictRef(obj.dict, "Resources");
    let resDict = obj.dict;
    if (resRef && objects.has(resRef)) resDict = objects.get(resRef).dict;
    const fontDictRef = dictRef(resDict, "Font");
    let fontDict = resDict;
    if (fontDictRef && objects.has(fontDictRef)) fontDict = objects.get(fontDictRef).dict;
    const map = new Map();
    const fontRe = /\/([A-Za-z0-9_.+-]+)\s+(\d+)\s+\d+\s+R/g;
    const fontSection = (() => {
      const idx = fontDict.indexOf("/Font");
      return idx >= 0 ? fontDict.slice(idx) : fontDict;
    })();
    let fm;
    while ((fm = fontRe.exec(fontSection)) !== null) {
      const refNum = Number(fm[2]);
      if (fontRefMaps.has(refNum)) map.set(fm[1], fontRefMaps.get(refNum));
      else if (fontMaps.has(fm[1])) map.set(fm[1], fontMaps.get(fm[1]));
    }
    pageFonts.set(num, map);
  }

  // Страницы в порядке дерева /Pages.
  const order = pageOrder(buffer, objects);
  const texts = [];
  for (const pageNum of order) {
    const page = objects.get(pageNum);
    if (!page) continue;
    let contents = [];
    const contentRef = dictRef(page.dict, "Contents");
    if (contentRef != null && objects.has(contentRef)) {
      const c = objects.get(contentRef);
      if (/\/Type\s*\/XObject|\[\s*\d+\s+\d+\s+R/.test(c.dict) && !/stream/.test(page.dict)) {
        // Массив ссылок на потоки.
        const refs = (c.dict.match(/\d+\s+\d+\s+R/g) || []).map((r) => Number(r.split(/\s+/)[0]));
        contents = refs.map((r) => objects.get(r)).filter(Boolean);
      } else {
        contents = [c];
      }
    } else {
      const arr = page.dict.match(/\/Contents\s*\[([^\]]*)\]/);
      if (arr) {
        const refs = (arr[1].match(/(\d+)\s+\d+\s+R/g) || []).map((r) => Number(r.split(/\s+/)[0]));
        contents = refs.map((r) => objects.get(r)).filter(Boolean);
      }
    }
    const stream = contents.map((c) => decodeStream(c)).join("\n");
    if (!stream) continue;
    texts.push(contentToText(stream, pageFonts.get(pageNum) || new Map()));
  }

  let text = texts.join("\n\n").replace(/\n{3,}/g, "\n\n").trim();

  // Если текст получился «битым» — пробуем однобайтовую интерпретацию целиком.
  const cyr = (text.match(/[\u0400-\u04ff]/g) || []).length;
  const letters = (text.match(/[A-Za-z\u0400-\u04ff]/g) || []).length;
  const hasText = letters > 50 && cyr / Math.max(1, letters) > 0.2;

  return { text: text, pages: texts.length, hasText: hasText };
}

/** Порядок страниц по дереву /Pages; если не вышло — по номерам объектов. */
function pageOrder(buffer, objects) {
  const nums = [];
  for (const [num, obj] of objects) {
    if (/\/Type\s*\/Page\b/.test(obj.dict) && !/\/Type\s*\/Pages\b/.test(obj.dict)) nums.push(num);
  }
  nums.sort((a, b) => a - b);
  return nums;
}

module.exports = { extractPdfText, parseCMap, contentToText };
