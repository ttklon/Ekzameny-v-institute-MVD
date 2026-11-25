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
  /** Порядок готовых дисциплин в комплекте. */
  const BUILTIN_ORDER = ["adp", "ugp", "upp", "tsp", "tp", "gpp", "krim"];

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
        globalDailyMinutes: 0,
        dailyCapMinutes: 0,
        defaultPasses: 3,
        defaultMode: "even",
        defaultRestDays: [0],
        sound: true,
        soundVolume: 0.45,
        skyHour: null,
        reduceMotion: false,
        showAnsweredOnly: false,
        // Напоминания, трей и запуск вместе с Windows — по одному переключателю,
        // без лишних полей. Трей включён: это удобно и не мешает.
        remind: { enabled: true, at: "19:00", days: null },
        tray: true,
        closeToTray: false,
        autostart: false
      },
      disciplines: [],
      ui: {
        view: "today",
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
    // Порядок готовых дисциплин из прошлых версий: раньше у них не было
    // номера в комплекте, и после добавления подробных ответов по
    // административной деятельности они вставали в конец списка. Расставляем
    // по порядку комплекта, чтобы «сначала подробный, потом краткий» работало
    // и у тех, кто уже пользуется программой.
    out.disciplines.forEach((d) => {
      if (!d.builtin) return;
      if (typeof d.builtinRank !== "number") {
        const i = BUILTIN_ORDER.indexOf(d.builtin);
        d.builtinRank = i === -1 ? 900 : i;
      }
      // Раньше административная деятельность была одним файлом с краткими
      // ответами. Теперь ответов два: подробный — для первого чтения,
      // краткий — для повторений. Отметки и план при этом остаются: вопрос
      // один и тот же, меняется только текст ответа.
      if (d.builtin === "adp2") {
        d.builtin = "adp";
        d.builtinRank = 0;
        if (/кратк/i.test(d.name)) d.name = "Административная деятельность полиции";
      }
    });
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
    plan.examStrict = plan.examStrict !== false;
    // Двухфайловая схема: { big, small } — сколько раз читать подробный и
    // краткий файл. null — обычные passes прогонов.
    if (plan.bigFirst && typeof plan.bigFirst === "object") {
      plan.bigFirst = {
        big: Math.max(1, Math.min(12, Math.round(Number(plan.bigFirst.big) || 1))),
        small: Math.max(1, Math.min(12, Math.round(Number(plan.bigFirst.small) || 1)))
      };
    } else {
      plan.bigFirst = null;
    }
    const variant = ["auto", "full", "short"].indexOf(d.answerVariant) === -1 ? "auto" : d.answerVariant;
    return Object.assign(
      {
        id: uid(),
        name: "Без названия",
        answerVariant: variant,
        hasShortAnswers: !!d.hasShortAnswers,
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
    // Порядок в списке — не случайный: готовые дисциплины идут в том порядке,
    // в каком они лежат в комплекте. Свои файлы — после них, как добавлены.
    const list = (store.state.disciplines || []).filter((d) => !d.archived);
    const key = (d, i) => (typeof d.builtinRank === "number" ? d.builtinRank : 1000 + i);
    return list
      .map((d, i) => ({ d: d, k: key(d, i) }))
      .sort((a, b) => a.k - b.k)
      .map((x) => x.d);
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

  /**
   * Добавляет готовую дисциплину из комплекта (файл уже внутри приложения).
   * В библиотеку кладутся только заголовки и объёмы — сам текст ответа
   * остаётся в файле комплекта и читается при открытии вопроса.
   * payload: {code, name, questions, strategy, answeredCount, totalWords, totalChars}
   */
  function addBuiltin(payload) {
    const existing = store.state.disciplines.find((d) => d.builtin === payload.code);
    if (existing) return existing;
    const d = addDiscipline({
      name: payload.name,
      fileName: payload.name + ".txt",
      questions: payload.questions,
      parsing: {
        strategy: payload.strategy || "markdown-headings",
        count: payload.questions.length,
        answeredCount: payload.answeredCount || payload.questions.length,
        totalWords: payload.totalWords || 0,
        totalChars: payload.totalChars || 0
      }
    });
    d.builtin = payload.code;
    // Место в комплекте: по нему список дисциплин держит порядок «сначала
    // подробный вариант, потом краткий», даже если человек добавил их вразнобой.
    if (typeof payload.rank === "number") d.builtinRank = payload.rank;
    if (payload.hasAlt) d.hasShortAnswers = true;
    d.fileName = payload.name + ".txt";
    // Дата экзамена из комплекта: у каждой дисциплины свой день (18.12 ТП,
    // 24.12 ГПП, 26.12 крим, 30.12 ТСП, 12.01 УПП, 15.01 УП, 19.01 АДП).
    // Это лишь значение по умолчанию — человек может поставить другое.
    if (payload.examDate && root.ExamCore && root.ExamCore.planner &&
        root.ExamCore.planner.isValidDate(payload.examDate)) {
      d.plan.examDate = payload.examDate;
      // Зачёт на последнем занятии: этот день тоже учебный. Экзамен — нет.
      d.plan.examStrict = payload.examKind !== "зачёт";
      d.examKind = payload.examKind || "";
    }
    // Схема чтения из комплекта: сначала большой файл, потом маленький.
    if (payload.bigFirst && typeof payload.bigFirst === "object") {
      d.plan.bigFirst = {
        big: Math.max(1, Math.min(12, Math.round(Number(payload.bigFirst.big) || 1))),
        small: Math.max(1, Math.min(12, Math.round(Number(payload.bigFirst.small) || 1)))
      };
    }
    save(true);
    return d;
  }

  /**
   * Обновляет объёмы вопросов готовой дисциплины по свежему разбору файла.
   *
   * Нужно, когда вариантов ответа стало два: у тех, кто пользуется программой
   * давно, объёмы записаны по краткому ответу, а первое чтение идёт по
   * подробному. Отметки, заметки и план при этом не трогаются — меняются
   * только числа объёма, по которым считается время.
   */
  function refreshBuiltinVolumes(code, questions) {
    const d = store.state.disciplines.find((x) => x.builtin === code);
    if (!d || !Array.isArray(questions) || !questions.length) return false;
    const byNum = {};
    for (const q of questions) byNum[q.num] = q;
    let changed = false;
    d.questions.forEach((q, i) => {
      const src = byNum[q.num] || questions[i];
      if (!src) return;
      for (const key of ["words", "chars", "aWords", "aChars", "qWords", "qChars", "charsWithSpaces", "altWords", "altChars"]) {
        if (src[key] != null && q[key] !== src[key]) {
          q[key] = src[key];
          changed = true;
        }
      }
    });
    if (d.parsing) {
      d.parsing.totalWords = questions.reduce((a, q) => a + (q.words || 0), 0);
      d.parsing.totalChars = questions.reduce((a, q) => a + (q.chars || 0), 0);
    }
    if (changed) save(true);
    return changed;
  }

  /**
   * Донести до уже добавленной дисциплины данные комплекта: дату экзамена,
   * что это зачёт или экзамен, и схему «сначала большой файл, потом маленький».
   *
   * Нужно тем, кто пользуется программой давно: дисциплины у них созданы
   * раньше, и без этого даты экзаменов и порядок чтения по административной
   * деятельности не появились бы сами.
   *
   * Экзамен, у которого дата уже прошла, не переносим вперёд: если человек
   * сдал и не удалил дисциплину, она не должна «оживать» каждый год.
   */
  function syncBuiltinPlan(code, item) {
    const d = store.state.disciplines.find((x) => x.builtin === code);
    if (!d || !item) return false;
    const planner = root.ExamCore.planner;
    let changed = false;
    if (item.examDate && planner && planner.isValidDate(item.examDate)) {
      const kind = item.examKind || "";
      if (d.examKind !== kind) {
        d.examKind = kind;
        changed = true;
      }
      const today = planner ? planner.todayStr() : "";
      const empty = !d.plan.examDate || typeof d.plan.examDate !== "string";
      // Экзамен уже прошёл — не трогаем: сдал, значит сдал.
      const alreadyPassed = !empty && today && d.plan.examDate < today;
      // Дату из комплекта ставим один раз (examFromPack): дальше это уже
      // выбор человека, и переписывать его при каждом запуске нельзя.
      const fromOwnChoice = d.examFromPack === true && !empty;
      if (!alreadyPassed && !fromOwnChoice && d.plan.examDate !== item.examDate) {
        d.plan.examDate = item.examDate;
        d.plan.examStrict = kind !== "зачёт";
        d.examFromPack = true;
        changed = true;
      }
    }
    if (item.bigFirst && typeof item.bigFirst === "object") {
      const want = {
        big: Math.max(1, Math.min(12, Math.round(Number(item.bigFirst.big) || 1))),
        small: Math.max(1, Math.min(12, Math.round(Number(item.bigFirst.small) || 1)))
      };
      const cur = d.plan.bigFirst || null;
      // Свой выбор человека не перебиваем: ставим схему только если её нет.
      if (!cur) {
        d.plan.bigFirst = want;
        changed = true;
      }
    }
    if (changed) save(true);
    return changed;
  }

  /**
   * Какие готовые дисциплины ещё не добавлены.
   *
   * Смотрим не только на код комплекта, но и на название: если человек уже
   * добавил свой файл «Уголовное право», второй такой же ему не нужен.
   */
  function missingBuiltin(items) {
    const codes = new Set(store.state.disciplines.map((d) => d.builtin).filter(Boolean));
    const names = new Set(
      store.state.disciplines.map((d) => normalizeName(d.name))
    );
    return (items || []).filter(
      (it) => !codes.has(it.code) && !names.has(normalizeName(it.name))
    );
  }

  /** Название для сравнения: без регистра, лишних пробелов и знаков. */
  function normalizeName(name) {
    return String(name || "")
      .toLowerCase()
      .replace(/[ё]/g, "е")
      .replace(/[^а-яa-z0-9]+/g, " ")
      .trim();
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

  /**
   * Снять все отметки за дату (или за дату по одной дисциплине).
   * Возвращает список снятых [{discId, qIndex}], чтобы их можно было вернуть
   * одной кнопкой «Отменить» — ошибиться и передумать может каждый.
   */
  function clearReadsOn(discId, date) {
    const out = [];
    const discs = discId ? [getDiscipline(discId)].filter(Boolean) : store.state.disciplines;
    for (const d of discs) {
      if (!d || !d.reads) continue;
      for (const key of Object.keys(d.reads)) {
        const list = Array.isArray(d.reads[key]) ? d.reads[key] : [];
        if (list.indexOf(date) === -1) continue;
        const rest = list.filter((x) => x !== date);
        if (rest.length) d.reads[key] = rest;
        else delete d.reads[key];
        out.push({ discId: d.id, qIndex: Number(key) });
      }
    }
    if (!out.length) return out;
    // День без отметок больше не считается активным: серия и календарь
    // должны отражать то, что есть на самом деле, а не то, что было.
    const st = store.state.stats;
    if (Array.isArray(st.daysActive)) st.daysActive = st.daysActive.filter((x) => x !== date);
    st.streak = computeStreak(st.daysActive || []);
    save();
    emit("reads-changed");
    return out;
  }

  /**
   * Вернуть снятые отметки: restoreReads([{discId, qIndex}], date).
   * Так работает «Отменить» после «Снять всё за сегодня».
   */
  function restoreReads(items, date) {
    const byDisc = new Map();
    for (const it of items || []) {
      if (!byDisc.has(it.discId)) byDisc.set(it.discId, []);
      byDisc.get(it.discId).push(it.qIndex);
    }
    for (const [id, list] of byDisc) setReadMany(id, list, date, true);
    return (items || []).length;
  }

  /** Все отметки за конкретный день — для списка «что уже отмечено». */
  function readsOn(date, discId) {
    const out = [];
    const discs = discId ? [getDiscipline(discId)].filter(Boolean) : store.state.disciplines;
    for (const d of discs) {
      if (!d || !d.reads) continue;
      for (const key of Object.keys(d.reads)) {
        const list = Array.isArray(d.reads[key]) ? d.reads[key] : [];
        if (list.indexOf(date) !== -1) out.push({ discId: d.id, qIndex: Number(key) });
      }
    }
    return out;
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
    addBuiltin,
    refreshBuiltinVolumes,
    syncBuiltinPlan,
    missingBuiltin,
    removeDiscipline,
    setRead,
    setReadMany,
    moveRead,
    clearReadsOn,
    restoreReads,
    readsOn,
    computeStreak
  };
})(typeof window !== "undefined" ? window : globalThis);
