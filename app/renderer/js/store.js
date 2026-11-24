/*
 * store.js — состояние приложения в интерфейсе.
 *
 * Здесь всё, что пользователь видит и меняет: дисциплины, планы, отметки о
 * прочтении, настройки. Состояние хранится в одном объекте и сохраняется в
 * файл с задержкой (чтобы не писать на диск на каждый клик).
 *
 * Формат (упрощённо):
 * {
 *   version: 2,
 *   settings: { wordsPerMinute, unit, reviewSpeedFactor, gapRatio, globalDailyMinutes, sound, ... },
 *   disciplines: [{
 *     id, name, fileName, textFile, importedAt,
 *     questions: [{ num, title, words, chars, difficulty, hasAnswer }],
 *     plan: { startDate, examDate, passes, mode, perDayQuestions, perDayMinutes, restDays, order },
 *     reads: { "0": ["2026-11-24"], … },   // индексы вопросов → даты прочтения
 *     notes: { "0": "…" },                 // личные заметки
 *     archived: false, accent: 0
 *   }],
 *   ui: { view, selectedDiscipline, skyHour, theme }
 * }
 */
(function (root) {
  "use strict";

  const STORAGE_VERSION = 2;
  const SAVE_DELAY = 450;

  const store = {
    state: null,
    listeners: [],
    saveTimer: null,
    dirty: false,
    lastSaveError: null
  };

  function uid(prefix) {
    return (prefix || "d") + "-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 7);
  }

  function defaults() {
    const planner = root.ExamCore.planner;
    const today = planner.todayStr();
    return {
      version: STORAGE_VERSION,
      createdAt: new Date().toISOString(),
      settings: {
        wordsPerMinute: 150,
        charsPerMinute: 900,
        unit: "wpm",
        reviewSpeedFactor: 1.5,
        gapRatio: 0.15,
        globalDailyMinutes: 60,
        dailyCapMinutes: 0,
        defaultPasses: 3,
        defaultMode: "even",
        defaultRestDays: [0],
        sound: true,
        soundVolume: 0.45,
        skyHour: null,
        reduceMotion: false,
        showAnsweredOnly: false
      },
      disciplines: [],
      ui: {
        view: "dashboard",
        selectedDiscipline: null,
        calendarMonth: null,
        dayView: null
      },
      stats: {
        streak: 0,
        lastActiveDay: null,
        totalChecks: 0,
        daysActive: []
      }
    };
  }

  /** Приводит загруженное состояние к текущей версии (миграции). */
  function migrate(state) {
    if (!state || typeof state !== "object") return defaults();
    const base = defaults();
    const out = Object.assign({}, base, state);
    out.settings = Object.assign({}, base.settings, state.settings || {});
    out.ui = Object.assign({}, base.ui, state.ui || {});
    out.stats = Object.assign({}, base.stats, state.stats || {});
    out.disciplines = Array.isArray(state.disciplines) ? state.disciplines : [];
    out.version = STORAGE_VERSION;
    out.disciplines = out.disciplines.map((d) => normalizeDiscipline(d));
    return out;
  }

  /** Приводит дисциплину к полному виду: все поля плана на месте. */
  function normalizeDiscipline(d) {
    const planner = root.ExamCore.planner;
    const today = planner.todayStr();
    const plan = Object.assign(planner.defaultPlan(today, planner.addDays(today, 30)), d.plan || {});
    plan.passes = Math.max(1, Math.min(12, Number(plan.passes) || 3));
    plan.mode = ["even", "questions", "minutes"].indexOf(plan.mode) === -1 ? "even" : plan.mode;
    plan.perDayQuestions = Math.max(1, Number(plan.perDayQuestions) || 10);
    plan.perDayMinutes = Math.max(5, Number(plan.perDayMinutes) || 45);
    plan.restDays = Array.isArray(plan.restDays) ? plan.restDays : [0];
    plan.order = plan.order === "mixed" ? "mixed" : "inOrder";
    return Object.assign(
      {
        id: uid(),
        name: "Без названия",
        fileName: "",
        filePath: "",
        textFile: "",
        importedAt: new Date().toISOString(),
        questions: [],
        reads: {},
        notes: {},
        highlights: {},
        archived: false,
        accent: 0,
        parsing: null
      },
      d,
      { plan: plan }
    );
  }

  // ---------- Загрузка и сохранение ----------

  async function load() {
    try {
      const api = root.api;
      if (!api || !api.loadState) {
        // Режим браузера (для проверки интерфейса): localStorage.
        const raw = localStorage.getItem("cloudPlanner");
        store.state = raw ? migrate(JSON.parse(raw)) : defaults();
        return { ok: true, browser: true };
      }
      const r = await api.loadState();
      store.state = migrate(r && r.state);
      return { ok: true, recovered: !!(r && r.recovered) };
    } catch (err) {
      store.state = defaults();
      return { ok: false, error: String(err.message || err) };
    }
  }

  function save(immediate) {
    store.dirty = true;
    if (store.saveTimer) clearTimeout(store.saveTimer);
    if (immediate) return flush();
    store.saveTimer = setTimeout(flush, SAVE_DELAY);
    return Promise.resolve({ ok: true, deferred: true });
  }

  async function flush() {
    if (store.saveTimer) {
      clearTimeout(store.saveTimer);
      store.saveTimer = null;
    }
    if (!store.dirty) return { ok: true, noop: true };
    store.dirty = false;
    try {
      const api = root.api;
      if (!api || !api.saveState) {
        localStorage.setItem("cloudPlanner", JSON.stringify(store.state));
        return { ok: true, browser: true };
      }
      const r = await api.saveState(store.state);
      if (!r || !r.ok) store.lastSaveError = r && r.error;
      return r;
    } catch (err) {
      store.dirty = true;
      store.lastSaveError = String(err.message || err);
      return { ok: false, error: store.lastSaveError };
    }
  }

  // ---------- Подписка ----------

  function subscribe(fn) {
    store.listeners.push(fn);
    return () => {
      const i = store.listeners.indexOf(fn);
      if (i >= 0) store.listeners.splice(i, 1);
    };
  }

  function emit(what) {
    for (const fn of store.listeners.slice()) {
      try {
        fn(store.state, what);
      } catch (e) {
        console.error("listener failed", e);
      }
    }
  }

  /** Изменение состояния: mutate(state) → сохранение → подписчики. */
  function update(mutator, opts) {
    const before = store.state;
    mutator(store.state);
    emit((opts && opts.what) || "update");
    if (!opts || opts.save !== false) save(opts && opts.immediate);
    return before;
  }

  // ---------- Дисциплины ----------

  function getDiscipline(id) {
    return (store.state.disciplines || []).find((d) => d.id === id) || null;
  }

  function activeDisciplines() {
    return (store.state.disciplines || []).filter((d) => !d.archived);
  }

  /** Добавляет дисциплину из разобранного файла. */
  function addDiscipline(payload) {
    const planner = root.ExamCore.planner;
    const today = planner.todayStr();
    const s = store.state.settings;
    const d = normalizeDiscipline({
      id: payload.id || uid("disc"),
      name: payload.name || "Дисциплина",
      fileName: payload.fileName || "",
      filePath: payload.filePath || "",
      textFile: payload.textFile || "",
      questions: payload.questions || [],
      reads: {},
      plan: Object.assign(planner.defaultPlan(today, planner.addDays(today, 30)), {
        passes: s.defaultPasses || 3,
        mode: s.defaultMode || "even",
        restDays: (s.defaultRestDays || [0]).slice()
      }),
      parsing: payload.parsing || null,
      accent: (store.state.disciplines.length % 6),
      importedAt: new Date().toISOString()
    });
    store.state.disciplines.push(d);
    save();
    emit("discipline-added");
    return d;
  }

  function removeDiscipline(id) {
    const i = store.state.disciplines.findIndex((d) => d.id === id);
    if (i < 0) return false;
    const [d] = store.state.disciplines.splice(i, 1);
    if (d && d.textFile && root.api && root.api.removeText) {
      root.api.removeText(d.textFile).catch(() => {});
    }
    if (store.state.ui.selectedDiscipline === id) store.state.ui.selectedDiscipline = null;
    save();
    emit("discipline-removed");
    return true;
  }

  // ---------- Отметки о прочтении ----------

  /** Отмечает вопрос прочитанным (или снимает отметку) на дату. */
  function setRead(discId, qIndex, date, read) {
    const d = getDiscipline(discId);
    if (!d) return null;
    if (!d.reads) d.reads = {};
    const key = String(qIndex);
    const list = Array.isArray(d.reads[key]) ? d.reads[key].slice() : [];
    const at = list.indexOf(date);
    if (read && at === -1) list.push(date);
    if (!read && at >= 0) list.splice(at, 1);
    list.sort();
    if (list.length) d.reads[key] = list;
    else delete d.reads[key];

    // Статистика серии дней.
    if (read) {
      const st = store.state.stats;
      st.totalChecks = (st.totalChecks || 0) + 1;
      if (!Array.isArray(st.daysActive)) st.daysActive = [];
      if (st.daysActive.indexOf(date) === -1) {
        st.daysActive.push(date);
        st.daysActive.sort();
        if (st.daysActive.length > 400) st.daysActive = st.daysActive.slice(-400);
      }
      st.lastActiveDay = date;
      st.streak = computeStreak(st.daysActive);
    }
    save();
    emit("reads-changed");
    return { reads: d.reads[key] || [] };
  }

  /** Сколько дней подряд (до сегодня) есть хотя бы одна отметка. */
  function computeStreak(days) {
    if (!days || !days.length) return 0;
    const planner = root.ExamCore.planner;
    const set = new Set(days);
    let cursor = planner.todayStr();
    // Если сегодня ещё ничего не отмечено, серия считается до вчера.
    if (!set.has(cursor)) cursor = planner.addDays(cursor, -1);
    let n = 0;
    let guard = 0;
    while (set.has(cursor) && guard < 2000) {
      n++;
      cursor = planner.addDays(cursor, -1);
      guard++;
    }
    return n;
  }

  /** Отметить сразу несколько вопросов на дату. */
  function setReadMany(discId, indices, date, read) {
    const d = getDiscipline(discId);
    if (!d) return;
    if (!d.reads) d.reads = {};
    for (const qi of indices) {
      const key = String(qi);
      const list = Array.isArray(d.reads[key]) ? d.reads[key].slice() : [];
      const at = list.indexOf(date);
      if (read && at === -1) list.push(date);
      if (!read && at >= 0) list.splice(at, 1);
      list.sort();
      if (list.length) d.reads[key] = list;
      else delete d.reads[key];
    }
    if (read && indices.length) {
      const st = store.state.stats;
      st.totalChecks = (st.totalChecks || 0) + indices.length;
      if (!Array.isArray(st.daysActive)) st.daysActive = [];
      if (st.daysActive.indexOf(date) === -1) {
        st.daysActive.push(date);
        st.daysActive.sort();
      }
      st.lastActiveDay = date;
      st.streak = computeStreak(st.daysActive);
    }
    save();
    emit("reads-changed");
  }

  /** Перенос даты прочтения (если отметили не тот день). */
  function moveRead(discId, qIndex, fromDate, toDate) {
    const d = getDiscipline(discId);
    if (!d || !d.reads) return;
    const key = String(qIndex);
    const list = Array.isArray(d.reads[key]) ? d.reads[key].slice() : [];
    const at = list.indexOf(fromDate);
    if (at < 0) return;
    list.splice(at, 1);
    if (list.indexOf(toDate) === -1) list.push(toDate);
    list.sort();
    d.reads[key] = list;
    save();
    emit("reads-changed");
  }

  root.Store = {
    STORAGE_VERSION,
    uid,
    defaults,
    migrate,
    normalizeDiscipline,
    load,
    save,
    flush,
    subscribe,
    emit,
    update,
    get state() {
      return store.state;
    },
    getDiscipline,
    activeDisciplines,
    addDiscipline,
    removeDiscipline,
    setRead,
    setReadMany,
    moveRead,
    computeStreak
  };
})(typeof window !== "undefined" ? window : globalThis);
