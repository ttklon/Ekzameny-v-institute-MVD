/*
 * remind.js — напоминание о чтении и работа в трее.
 *
 * Задача простая и полезная: пока приложение запущено, раз в минуту проверяем,
 * есть ли на сегодня непрочитанные вопросы. Если есть и время подошло —
 * показываем уведомление Windows и значок в трее с числом.
 *
 * Что специально НЕ делается:
 *   • нет будильников, которые звенят в полночь;
 *   • нет навязчивых окон поверх других программ;
 *   • если на сегодня ничего не запланировано — молчим.
 *
 * Расписание напоминаний хранится в настройках (remind.at, remind.enabled,
 * remind.days) и меняется без перезапуска.
 */
"use strict";

const path = require("path");
const { Tray, Menu, Notification, nativeImage, app } = require("electron");

const CHECK_EVERY_MS = 60 * 1000; // раз в минуту, как и проверка обновлений
const MIN_GAP_MS = 30 * 60 * 1000; // не чаще раза в полчаса

/**
 * opts: {
 *   getTodayInfo: () => { minutes, tasks, total } — сколько на сегодня осталось,
 *   onOpen: () => void — показать окно,
 *   onOpenToday: () => void — открыть экран «Сегодня»,
 *   onQuit: () => void,
 *   iconPath: string
 * }
 */
function createReminder(opts) {
  const o = opts || {};
  let tray = null;
  let timer = null;
  let lastShownAt = 0;
  let lastKey = ""; // чтобы не повторять одно и то же напоминание
  let enabled = true;
  let at = "19:00";
  let days = null; // null — каждый день, иначе массив 0..6 (0 — воскресенье)
  let trayNumber = 0;

  /** Пора ли напоминать прямо сейчас. */
  function dueNow(date) {
    if (!enabled) return false;
    const d = date || new Date();
    if (Array.isArray(days) && days.length && days.indexOf(d.getDay()) === -1) return false;
    const m = String(at || "19:00").match(/^(\d{1,2}):(\d{2})$/);
    if (!m) return false;
    const target = parseInt(m[1], 10) * 60 + parseInt(m[2], 10);
    const now = d.getHours() * 60 + d.getMinutes();
    // Окно в 10 минут: приложение могло быть свёрнуто и проснуться позже.
    return now >= target && now < target + 10;
  }

  function info() {
    try {
      return o.getTodayInfo ? o.getTodayInfo() : null;
    } catch (e) {
      return null;
    }
  }

  /** Обновить подсказку в трее: «Сегодня: 12 вопросов · 34 мин». */
  function refreshTray() {
    if (!tray) return;
    const t = info();
    const count = t && t.tasks ? t.tasks : 0;
    trayNumber = count;
    const summary = count
      ? "Сегодня: " + count + " " + plural(count, "вопрос", "вопроса", "вопросов") +
        (t.minutes ? " · " + Math.round(t.minutes) + " мин" : "")
      : "На сегодня всё сделано";
    tray.setToolTip("Планировщик экзаменов\n" + summary);
    tray.setContextMenu(
      Menu.buildFromTemplate([
        { label: summary, enabled: false },
        { type: "separator" },
        { label: "Открыть «Сегодня»", click: () => o.onOpenToday && o.onOpenToday() },
        { label: "Показать окно", click: () => o.onOpen && o.onOpen() },
        { type: "separator" },
        { label: "Выход", click: () => o.onQuit && o.onQuit() }
      ])
    );
  }

  function plural(n, one, few, many) {
    const a = Math.abs(n) % 100;
    const b = a % 10;
    if (a > 10 && a < 20) return many;
    if (b > 1 && b < 5) return few;
    if (b === 1) return one;
    return many;
  }

  /** Показать уведомление Windows. */
  function notify() {
    const t = info();
    if (!t || !t.tasks) return false;
    const body =
      t.tasks + " " + plural(t.tasks, "вопрос", "вопроса", "вопросов") +
      (t.minutes ? " · примерно " + Math.round(t.minutes) + " мин чтения" : "") +
      ". Нажмите, чтобы открыть список.";
    try {
      if (!Notification.isSupported()) return false;
      const n = new Notification({
        title: "Пора заниматься",
        body: body,
        silent: false
      });
      n.on("click", () => o.onOpenToday && o.onOpenToday());
      n.show();
      return true;
    } catch (e) {
      return false;
    }
  }

  /** Проверка «раз в минуту»: уведомление и число в трее. */
  function tick() {
    refreshTray();
    // Обновляем «последнее напоминание» не чаще раза в полчаса, иначе
    // в течение 10-минутного окна прилетело бы 10 уведомлений.
    if (!dueNow()) return;
    const key = new Date().toISOString().slice(0, 10) + "|" + (info() || {}).tasks;
    if (key === lastKey) return;
    if (Date.now() - lastShownAt < MIN_GAP_MS) return;
    if (notify()) {
      lastShownAt = Date.now();
      lastKey = key;
    }
  }

  function start() {
    if (timer) clearInterval(timer);
    timer = setInterval(tick, CHECK_EVERY_MS);
    if (timer.unref) timer.unref();
    tick();
  }

  function stop() {
    if (timer) clearInterval(timer);
    timer = null;
  }

  /** Создать значок в трее (без него уведомления всё равно работают). */
  function attachTray() {
    if (tray) return tray;
    let img = null;
    try {
      img = nativeImage.createFromPath(o.iconPath);
      if (img.isEmpty()) img = null;
    } catch (e) {
      img = null;
    }
    if (!img) {
      // Запасная иконка: пустая картинка нужного размера.
      img = nativeImage.createEmpty();
      if (img.isEmpty() && process.platform === "win32") return null;
    }
    try {
      tray = new Tray(img);
      tray.on("click", () => o.onOpen && o.onOpen());
      refreshTray();
      return tray;
    } catch (e) {
      tray = null;
      return null;
    }
  }

  function configure(settings) {
    const s = settings || {};
    const r = s.remind || {};
    enabled = r.enabled !== false;
    at = typeof r.at === "string" ? r.at : "19:00";
    days = Array.isArray(r.days) ? r.days : null;
    if (s.tray === false && tray) {
      tray.destroy();
      tray = null;
    } else if (s.tray !== false && !tray) {
      attachTray();
    }
    refreshTray();
  }

  return {
    start,
    stop,
    attachTray,
    configure,
    refreshTray,
    notify,
    dueNow,
    get tray() {
      return tray;
    }
  };
}

module.exports = { createReminder, CHECK_EVERY_MS, MIN_GAP_MS };
