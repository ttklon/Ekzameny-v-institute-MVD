/*
 * builtin.js — готовые ответы, которые идут вместе с приложением.
 *
 * В комплекте семь файлов: по одному на дисциплину, в каждом весь перечень
 * вопросов экзамена с ответами (всего 627 вопросов). Формат простой: заголовок
 * «# Вопрос 12. …», под ним ответ — так же, как в файлах, которые человек
 * добавляет сам, поэтому разбор общий.
 *
 * Важно: текст ответов НЕ кладётся в библиотеку (library.json). Там остаются
 * только заголовки, объёмы и имена файлов — иначе сохранение при каждой
 * отметке прочитанного переписывало бы двадцать мегабайт. Полный ответ
 * подгружается из файла только когда вопрос действительно открыли.
 */
"use strict";

const fs = require("fs");
const path = require("path");

/** Папка с готовыми ответами. В сборке это resources/answers. */
function answersDir(opts) {
  const o = opts || {};
  const candidates = [];
  if (o.dir) candidates.push(o.dir);
  // Разработка: app/answers рядом с main.js.
  candidates.push(path.join(__dirname, "..", "..", "answers"));
  // Собранное приложение: рядом с asar, в resources/answers.
  if (process.resourcesPath) candidates.push(path.join(process.resourcesPath, "answers"));
  for (const dir of candidates) {
    try {
      if (fs.existsSync(path.join(dir, "index.json"))) return dir;
    } catch (e) {
      /* следующий вариант */
    }
  }
  return null;
}

/** Список готовых дисциплин: [{code, name, count, bytes, words, file}]. */
function list(opts) {
  const dir = answersDir(opts);
  if (!dir) return [];
  try {
    const raw = fs.readFileSync(path.join(dir, "index.json"), "utf-8");
    const items = JSON.parse(raw);
    if (!Array.isArray(items)) return [];
    return items
      .filter((it) => it && it.code && it.name)
      .map((it) =>
        Object.assign({}, it, {
          file: path.join(dir, it.code + ".txt"),
          source: "builtin"
        })
      )
      .filter((it) => {
        try {
          return fs.existsSync(it.file);
        } catch (e) {
          return false;
        }
      });
  } catch (e) {
    return [];
  }
}

/** Текст одной дисциплины целиком. null — если файла нет. */
function read(code, opts) {
  const item = list(opts).find((x) => x.code === code);
  if (!item) return null;
  try {
    return fs.readFileSync(item.file, "utf-8");
  } catch (e) {
    return null;
  }
}

module.exports = { list, read, answersDir };
