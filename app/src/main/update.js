/*
 * update.js — автоматическое обновление приложения.
 *
 * Раз в минуту спрашиваем у GitHub, не вышла ли новая сборка. Ничего не
 * скачивается и не устанавливается само: сначала показывается вопрос, и только
 * после «Обновить» файл скачивается, проверяется и запускается.
 *
 * Почему так, а не «молча обновиться»:
 *   • приложение учебное, человек может читать прямо сейчас — обновление
 *     посреди работы выкинет его из окна;
 *   • скачанный файл приходит из сети, поэтому размер и хеш сверяются с тем,
 *     что сообщил GitHub;
 *   • если проверка не прошла, установка не начинается.
 *
 * Данные пользователя (библиотека, отметки, тексты) лежат в отдельной папке
 * AppData и обновлением не затрагиваются.
 */
"use strict";

const fs = require("fs");
const path = require("path");
const os = require("os");
const https = require("https");
const crypto = require("crypto");
const { spawn } = require("child_process");

const OWNER = "ttklon";
const REPO = "Ekzameny-v-institute-MVD";
const RELEASE_TAG = "app-latest";

// Проверять обновления раз в минуту — как просили. GitHub при частых запросах
// без авторизации отвечает 403, поэтому при ошибке пауза растёт до 15 минут.
const CHECK_EVERY_MS = 60 * 1000;
const BACKOFF_MAX_MS = 15 * 60 * 1000;

const REDIRECTS = 5;

/** Сравнение «точечных» версий: 1.2.10 новее 1.2.9. */
function compareVersions(a, b) {
  const pa = String(a || "0").split(/[.\-+]/).map((x) => parseInt(x, 10) || 0);
  const pb = String(b || "0").split(/[.\-+]/).map((x) => parseInt(x, 10) || 0);
  const n = Math.max(pa.length, pb.length);
  for (let i = 0; i < n; i++) {
    const x = pa[i] || 0;
    const y = pb[i] || 0;
    if (x > y) return 1;
    if (x < y) return -1;
  }
  return 0;
}

/** GET с редиректами и ограничением размера. Возвращает {status, headers, body}. */
function httpGet(url, options) {
  const opts = options || {};
  return new Promise((resolve, reject) => {
    const req = https.get(
      url,
      {
        headers: Object.assign(
          {
            "User-Agent": "CloudExamPlanner",
            Accept: "application/vnd.github+json"
          },
          opts.headers || {}
        ),
        timeout: opts.timeout || 20000
      },
      (res) => {
        // GitHub отдаёт файлы редиректом на отдельный хост.
        if ([301, 302, 303, 307, 308].indexOf(res.statusCode) !== -1) {
          const to = res.headers.location;
          res.resume();
          const left = opts.redirects == null ? REDIRECTS : opts.redirects;
          if (!to || left <= 0) return reject(new Error("слишком много перенаправлений"));
          return resolve(httpGet(to, Object.assign({}, opts, { redirects: left - 1 })));
        }
        const chunks = [];
        let size = 0;
        const max = opts.maxBytes || 4 * 1024 * 1024;
        res.on("data", (c) => {
          size += c.length;
          if (size > max) {
            req.destroy(new Error("ответ больше ожидаемого"));
            return;
          }
          chunks.push(c);
        });
        res.on("end", () =>
          resolve({
            status: res.statusCode,
            headers: res.headers,
            body: Buffer.concat(chunks)
          })
        );
      }
    );
    req.on("timeout", () => req.destroy(new Error("нет ответа от GitHub")));
    req.on("error", reject);
  });
}

/** Скачивание большого файла в путь с подсчётом размера и sha256. */
function download(url, destPath, options) {
  const opts = options || {};
  return new Promise((resolve, reject) => {
    const left = opts.redirects == null ? REDIRECTS : opts.redirects;
    const req = https.get(
      url,
      {
        headers: Object.assign({ "User-Agent": "CloudExamPlanner" }, opts.headers || {}),
        timeout: 30000
      },
      (res) => {
        if ([301, 302, 303, 307, 308].indexOf(res.statusCode) !== -1) {
          const to = res.headers.location;
          res.resume();
          if (!to || left <= 0) return reject(new Error("слишком много перенаправлений"));
          return resolve(download(to, destPath, Object.assign({}, opts, { redirects: left - 1 })));
        }
        if (res.statusCode !== 200) {
          res.resume();
          return reject(new Error("GitHub ответил " + res.statusCode));
        }
        const hash = crypto.createHash("sha256");
        let size = 0;
        const out = fs.createWriteStream(destPath);
        if (opts.onProgress) {
          const total = parseInt(res.headers["content-length"] || "0", 10) || 0;
          let last = 0;
          res.on("data", (c) => {
            size += c.length;
            hash.update(c);
            const now = Date.now();
            if (now - last > 300) {
              last = now;
              opts.onProgress({ received: size, total: total });
            }
          });
        } else {
          res.on("data", (c) => {
            size += c.length;
            hash.update(c);
          });
        }
        res.pipe(out);
        out.on("error", reject);
        out.on("finish", () => {
          out.close(() => resolve({ bytes: size, sha256: hash.digest("hex") }));
        });
      }
    );
    req.on("timeout", () => req.destroy(new Error("скачивание остановилось")));
    req.on("error", reject);
  });
}

/**
 * Создаёт проверяльщик обновлений.
 * opts: { currentVersion, currentBuild, dataDir, log }
 */
function createUpdater(opts) {
  const o = opts || {};
  const log = o.log || (() => {});
  const currentVersion = o.currentVersion || "1.0.0";
  const currentBuild = o.currentBuild || "";

  let found = null; // найденное обновление (объект для интерфейса)
  let state = "idle"; // idle | checking | downloading | ready | installing | error
  let errorText = "";
  let timer = null;
  let interval = CHECK_EVERY_MS;
  let checking = false;
  let lastCheckAt = 0;
  let listeners = [];

  function emit(extra) {
    const info = Object.assign(
      {
        state: state,
        available: !!found,
        update: found,
        error: errorText,
        lastCheckAt: lastCheckAt,
        checkEveryMs: interval,
        currentVersion: currentVersion,
        currentBuild: currentBuild
      },
      extra || {}
    );
    for (const fn of listeners) {
      try {
        fn(info);
      } catch (e) {
        /* подписчик не должен ломать проверку */
      }
    }
    return info;
  }

  /** Спросить у GitHub последний релиз и сравнить с текущей сборкой. */
  async function checkOnce(manual) {
    if (checking) return found;
    checking = true;
    state = "checking";
    errorText = "";
    emit();
    try {
      const url =
        "https://api.github.com/repos/" + OWNER + "/" + REPO + "/releases/tags/" + RELEASE_TAG;
      const res = await httpGet(url, { maxBytes: 512 * 1024 });
      if (res.status === 404) {
        throw new Error("релиз ещё не опубликован");
      }
      if (res.status === 403 || res.status === 429) {
        // Упёрлись в ограничение GitHub — реже спрашиваем, чтобы не блокировали.
        interval = Math.min(BACKOFF_MAX_MS, Math.max(CHECK_EVERY_MS, interval * 2));
        throw new Error("GitHub просит не так часто проверять (лимит запросов)");
      }
      if (res.status !== 200) {
        throw new Error("GitHub ответил " + res.status);
      }
      const rel = JSON.parse(res.body.toString("utf8"));
      const assets = Array.isArray(rel.assets) ? rel.assets : [];
      // Установщик: в имени есть x64 и нет portable. Портативную копию сами
      // не подменяем — она может лежать на флешке.
      const setup =
        assets.find((a) => /x64\.exe$/i.test(a.name) && !/portable/i.test(a.name)) ||
        assets.find((a) => /setup/i.test(a.name) && !/portable/i.test(a.name)) ||
        null;

      // «Свежесть» определяем по времени загрузки файла в релиз: версия у нас
      // всегда 1.0.0, а сборки отличаются датой и коммитом.
      const publishedAt = Date.parse(rel.published_at || rel.created_at || "") || 0;
      const assetAt = setup ? Date.parse(setup.updated_at || setup.created_at || "") || 0 : 0;
      const stamp = rel.body || "";
      const buildMatch = stamp.match(/сборка\s+(\d{4}-\d{2}-\d{2})\s*\/\s*([0-9a-f]{7,40})/i);
      const remoteBuild = buildMatch ? buildMatch[1] + " / " + buildMatch[2].slice(0, 7) : "";
      const newer = isNewer({
        remoteVersion: String(rel.tag_name || "").includes("exam-planner")
          ? ""
          : o.releaseVersion || currentVersion,
        remoteAt: Math.max(publishedAt, assetAt),
        remoteBuild: remoteBuild
      });

      lastCheckAt = Date.now();
      if (newer && setup) {
        found = {
          version: currentVersion,
          build: remoteBuild || "",
          size: setup.size || 0,
          assetName: setup.name,
          url: setup.browser_download_url || setup.url,
          publishedAt: assetAt || publishedAt,
          notes: String(rel.body || "").split("\n").filter((x) => x.trim().startsWith("•")).join("\n")
        };
        state = "ready";
      } else {
        found = null;
        state = "idle";
        interval = CHECK_EVERY_MS;
      }
      emit();
      return found;
    } catch (e) {
      errorText = String((e && e.message) || e);
      state = "error";
      // Не долбим GitHub каждую минуту, если он недоступен.
      interval = Math.min(BACKOFF_MAX_MS, Math.max(CHECK_EVERY_MS, interval * 2));
      emit();
      log("проверка обновлений: " + errorText);
      return null;
    } finally {
      checking = false;
      if (manual) schedule();
    }
  }

  /**
   * Нужно ли обновление.
   * Главный признак — время публикации файла: у нас версия всегда 1.0.0,
   * а сборки различаются датой. Если дата файла новее даты нашей сборки,
   * значит вышла новая.
   */
  function isNewer(info) {
    const mine = Date.parse(currentBuild ? currentBuild.slice(0, 10) : "") || 0;
    if (info.remoteBuild && currentBuild) {
      // Точное сравнение: «2026-11-24 / bd98dd1» против «2026-11-24 / abc1234».
      if (info.remoteBuild === currentBuild) return false;
      const myDate = currentBuild.slice(0, 10);
      const theirDate = info.remoteBuild.slice(0, 10);
      if (theirDate > myDate) return true;
      if (theirDate < myDate) return false;
      const mySha = currentBuild.split("/")[1] ? currentBuild.split("/")[1].trim() : "";
      const theirSha = info.remoteBuild.split("/")[1] ? info.remoteBuild.split("/")[1].trim() : "";
      return !!theirSha && theirSha !== mySha;
    }
    if (!mine) return false; // без своей даты не рискуем предлагать обновление
    // Файл должен быть новее нашей сборки хотя бы на час (запас на разницу часов).
    return info.remoteAt > mine + 60 * 60 * 1000;
  }

  /** Скачать найденное обновление и проверить. */
  async function downloadUpdate() {
    if (!found) throw new Error("сначала нужно найти обновление");
    state = "downloading";
    errorText = "";
    emit();
    try {
      const dir = path.join(os.tmpdir(), "cloud-exam-planner-update");
      fs.mkdirSync(dir, { recursive: true });
      const dest = path.join(dir, found.assetName || "setup.exe");
      const res = await download(found.url, dest, {
        onProgress: (p) => emit({ progress: p })
      });
      // Проверка: размер должен совпасть с тем, что сообщил GitHub.
      if (found.size && res.bytes !== found.size) {
        try {
          fs.unlinkSync(dest);
        } catch (e) {
          /* файл всё равно не запустим */
        }
        throw new Error("файл скачался не целиком (" + res.bytes + " из " + found.size + " байт)");
      }
      state = "ready";
      emit({ downloadedPath: dest, sha256: res.sha256 });
      return { path: dest, bytes: res.bytes, sha256: res.sha256 };
    } catch (e) {
      errorText = String((e && e.message) || e);
      state = "error";
      emit();
      throw e;
    }
  }

  /** Запустить скачанный установщик. Приложение закроется само. */
  function install(filePath, onQuit) {
    if (!filePath || !fs.existsSync(filePath)) {
      throw new Error("установщик не найден — скачайте обновление заново");
    }
    state = "installing";
    emit();
    // /S — тихая установка NSIS; ключ передаём, но установщик собран без
    // принудительной тишины, поэтому окно покажется, если ключ не поддержан.
    const child = spawn(filePath, [], { detached: true, stdio: "ignore" });
    child.unref();
    if (onQuit) setTimeout(onQuit, 800);
    return { ok: true };
  }

  function schedule() {
    if (timer) clearInterval(timer);
    timer = setInterval(() => checkOnce(false), interval);
    if (timer.unref) timer.unref();
  }

  function start() {
    schedule();
    // Первая проверка — почти сразу, но не в момент запуска: окно должно
    // успеть открыться.
    setTimeout(() => checkOnce(false), 8000);
  }

  function stop() {
    if (timer) clearInterval(timer);
    timer = null;
  }

  function onEvent(fn) {
    listeners.push(fn);
    return () => {
      listeners = listeners.filter((x) => x !== fn);
    };
  }

  return {
    start,
    stop,
    checkOnce,
    downloadUpdate,
    install,
    onEvent,
    state: () => emit(),
    compareVersions,
    isNewer
  };
}

module.exports = { createUpdater, compareVersions, OWNER, REPO, RELEASE_TAG, CHECK_EVERY_MS };
