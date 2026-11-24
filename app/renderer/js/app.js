/*
 * app.js — основной контроллер интерфейса «Облачный планировщик экзаменов».
 */
(function () {
  "use strict";

  const C = window.ExamCore;
  const P = C.planner;
  const T = C.textstats;
  const ESC = (s) =>
    String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");

  // ---------- Состояние ----------
  const today = () => P.fmtDate(new Date());
  let state = defaultState();
  let plan = null;
  let currentView = "dashboard";
  let todayCursor = today(); // для навигации по дням в «Сегодня»
  let detailId = null; // какая дисциплина открыта в деталях
  let pending = []; // ожидающие импорта файлы

  function defaultState() {
    return {
      version: 1,
      settings: {
        speedUnit: "wpm",
        wordsPerMinute: 250,
        charsPerMinute: 1500,
        restDays: [],
        soundEnabled: true,
        global: { dailyMinutes: 60 }
      },
      disciplines: []
    };
  }

  function defaultPlan(start) {
    start = start || today();
    return {
      startDate: start,
      examDate: P.addDays(start, 30),
      passes: 3,
      mode: "questions",
      perDayQuestions: 10,
      perDayMinutes: 20,
      assumeAnswerWords: 200,
      restDays: [],
      reviewSpeedFactor: 1.3
    };
  }

  function uuid() {
    return "d_" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
  }

  // ---------- Загрузка/сохранение ----------
  let saveTimer = null;
  function save() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      window.api.saveState(state).catch(() => {});
    }, 350);
  }
  function refresh() {
    plan = P.computeAll(state, today());
  }

  async function boot() {
    try {
      const loaded = await window.api.loadState();
      if (loaded && loaded.settings && Array.isArray(loaded.disciplines)) {
        state = Object.assign(defaultState(), loaded);
        state.settings = Object.assign(defaultState().settings, loaded.settings);
        state.settings.global = Object.assign(defaultState().settings.global, loaded.settings.global || {});
      }
    } catch (e) {}
    window.ExamAudio.setEnabled(state.settings.soundEnabled);
    refresh();
    document.getElementById("soundBtn").textContent = state.settings.soundEnabled ? "🔊" : "🔇";
    window.ExamClouds.start();
    bindGlobal();
    setView("dashboard");
    setTimeout(() => window.ExamAudio.open(), 300);
  }

  // ---------- Утилиты рендера ----------
  function ringSVG(pct, opts) {
    opts = opts || {};
    const r = opts.r || 54;
    const c = 2 * Math.PI * r;
    const off = c * (1 - Math.max(0, Math.min(1, pct)));
    const color = opts.color || "var(--accent)";
    const size = (r + 9) * 2;
    const sw = opts.sw || 11;
    return `<svg viewBox="0 0 ${size} ${size}" style="width:${size}px;height:${size}px;transform:rotate(-90deg)">
      <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="rgba(255,255,255,0.12)" stroke-width="${sw}"/>
      <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="${color}" stroke-width="${sw}" stroke-linecap="round"
        stroke-dasharray="${c.toFixed(2)}" stroke-dashoffset="${off.toFixed(2)}" style="transition:stroke-dashoffset 1.1s cubic-bezier(0.22,1,0.36,1)"/>
    </svg>`;
  }
  const fmt = (n) => (n == null ? "0" : Math.round(n).toLocaleString("ru-RU"));
  const dur = (m) => T.humanDuration(m);
  const WEEK = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"];
  const MONTHS = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];
  function prettyDate(s) {
    const d = P.parseDate(s);
    return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
  }

  // Процент готовности дисциплины (0..1).
  function discCompletion(disc) {
    return P.completion(disc, state.settings);
  }
  function discTotals(disc) {
    let q = 0,
      w = 0,
      ch = 0,
      m = 0;
    disc.questions.forEach((x) => {
      q++;
      w += x.qWords + x.aWords;
      ch += x.qChars + x.aChars;
      m += x.minutes;
    });
    return { q, w, ch, m1: m, mAll: m * (disc.plan.passes || 1) };
  }

  function toast(msg) {
    const t = document.getElementById("toast");
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(t._t);
    t._t = setTimeout(() => t.classList.remove("show"), 2600);
  }

  // ---------- Навигация ----------
  function bindGlobal() {
    document.querySelectorAll(".nav-item").forEach((b) => {
      b.addEventListener("click", () => {
        const v = b.dataset.view;
        if (v === currentView) return;
        if (v === "disciplines") detailId = null; // переход по меню — к списку, а не к старой детали
        window.ExamAudio.nav();
        setView(v);
      });
    });
    document.getElementById("soundBtn").addEventListener("click", () => {
      state.settings.soundEnabled = !state.settings.soundEnabled;
      window.ExamAudio.setEnabled(state.settings.soundEnabled);
      document.getElementById("soundBtn").textContent = state.settings.soundEnabled ? "🔊" : "🔇";
      save();
      if (state.settings.soundEnabled) window.ExamAudio.chime();
    });
  }

  function setView(v) {
    currentView = v;
    document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === v));
    const titles = {
      dashboard: ["Обзор", "Ваша подготовка в одном облаке"],
      import: ["Импорт", "Загрузите файлы с вопросами и ответами"],
      disciplines: ["Дисциплины", "Управляйте каждой учебной дисциплиной"],
      today: ["Сегодня", "Что читать прямо сейчас"],
      stats: ["Статистика", "Объёмы, время и распределение"],
      tips: ["Советы", "Как готовиться эффективно — по науке"],
      settings: ["Настройки", "Скорость чтения, выходные, звук"]
    };
    document.getElementById("viewTitle").textContent = titles[v][0];
    document.getElementById("viewSub").textContent = titles[v][1];
    render();
  }

  function render() {
    const view = document.getElementById("view");
    view.classList.remove("view-enter");
    void view.offsetWidth;
    view.classList.add("view-enter");
    let html = "";
    if (currentView === "dashboard") html = viewDashboard();
    else if (currentView === "import") html = viewImport();
    else if (currentView === "disciplines") html = viewDisciplines();
    else if (currentView === "today") html = viewToday();
    else if (currentView === "stats") html = viewStats();
    else if (currentView === "tips") html = viewTips();
    else if (currentView === "settings") html = viewSettings();
    view.innerHTML = html;
    updateTopbar();
    if (currentView === "dashboard") wireDashboard();
    else if (currentView === "import") wireImport();
    else if (currentView === "disciplines") wireDisciplines();
    else if (currentView === "today") wireToday();
    else if (currentView === "stats") wireStats();
    else if (currentView === "settings") wireSettings();
  }

  function updateTopbar() {
    // Сегодня
    document.getElementById("todayPill").textContent = "Сегодня: " + prettyDate(today());
    // Общий прогресс (по единицам)
    let total = 0,
      done = 0;
    state.disciplines.forEach((d) => {
      const units = P.buildUnits(d, state.settings);
      const doneSet = P.doneSet(d);
      total += units.length;
      done += units.filter((u) => doneSet.has(P.unitKey(u))).length;
    });
    const pct = total ? done / total : 0;
    document.getElementById("sideRingLabel").textContent = Math.round(pct * 100) + "%";
    const fg = document.querySelector("#sideRing .r-fg");
    if (fg) {
      const c = 2 * Math.PI * 16;
      fg.style.strokeDasharray = c.toFixed(2);
      fg.style.strokeDashoffset = (c * (1 - pct)).toFixed(2);
    }
  }

  // ============================================================
  //  ОБЗОР
  // ============================================================
  function viewDashboard() {
    if (state.disciplines.length === 0) {
      return emptyState(
        "🗂️",
        "Пока нет дисциплин",
        "Импортируйте файл с вопросами и ответами, и мы построим план подготовки к экзамену.",
        "Перейти к импорту",
        () => setView("import")
      );
    }
    let total = 0,
      done = 0;
    state.disciplines.forEach((d) => {
      const units = P.buildUnits(d, state.settings);
      const ds = P.doneSet(d);
      total += units.length;
      done += units.filter((u) => ds.has(P.unitKey(u))).length;
    });
    const pct = total ? done / total : 0;

    let cards = state.disciplines
      .map((d) => {
        const dp = discCompletion(d);
        const t = discTotals(d);
        const r = (plan.perDisc[d.id] && plan.perDisc[d.id].stats) || {};
        const daysLeft = Math.max(0, P.daysBetween(today(), d.plan.examDate));
        const modeTxt =
          d.plan.mode === "questions"
            ? `${r.perDayTarget || d.plan.perDayQuestions} вопр./день`
            : d.plan.mode === "minutes"
            ? `${d.plan.perDayMinutes} мин/день`
            : `в общем бюджете`;
        return `<div class="card disc-card hoverable" data-disc="${d.id}" style="cursor:pointer">
          <div class="bar" style="background:${d.color}"></div>
          <div class="row spread center">
            <div class="row center" style="gap:12px">
              <div class="disc-icon" style="font-size:24px">${ESC(d.icon || "📘")}</div>
              <div>
                <div class="disc-name">${ESC(d.name)}</div>
                <div class="disc-meta">${t.q} вопросов · ${d.plan.passes} прогона · до ${prettyDate(d.plan.examDate)}</div>
              </div>
            </div>
            <div class="ring" style="width:74px;height:74px">
              ${ringSVG(dp, { r: 32, sw: 8, color: d.color })}
              <div class="r-label" style="font-size:15px">${Math.round(dp * 100)}%</div>
            </div>
          </div>
          <div class="row spread" style="margin-top:12px">
            <span class="pill">⏳ ${daysLeft} дн. до экзамена</span>
            <span class="pill">📅 ${modeTxt}</span>
          </div>
        </div>`;
      })
      .join("");

    const todayTasks = (plan.todayTasks || []).length;
    let todayMin = 0;
    (plan.todayTasks || []).forEach((u) => (todayMin += u.minutes));

    let warns = "";
    if (plan.warnings && plan.warnings.length) {
      warns = `<div class="stack" style="margin-top:16px">${plan.warnings
        .map((w) => {
          const cls = w.type === "behind" || w.type === "global-short" || w.type === "overloaded" || w.type === "examBeforeStart" || w.type === "noActiveDays" ? "bad" : w.type === "adjusted" ? "warn" : "info";
          return `<div class="warn-box ${cls}"><span>${w.type === "adjusted" ? "⚠️" : w.type === "behind" || w.type === "global-short" ? "🚨" : "ℹ️"}</span><span>${ESC(w.text)}</span></div>`;
        })
        .join("")}</div>`;
    }

    return `
      <div class="stack">
        <div class="card row spread center" style="gap:20px">
          <div style="flex:1">
            <div class="small muted">${greeting()}, готовьтесь спокойно ☁️</div>
            <h2 class="sec" style="margin-top:6px">Общий прогресс подготовки</h2>
            <div class="muted small">Прочитано ${fmt(done)} из ${fmt(total)} «прогонов вопроса» по всем дисциплинам.</div>
            <div class="row" style="margin-top:14px;gap:10px;flex-wrap:wrap">
              <button class="btn primary" data-go="today">✅ Что читать сегодня (${todayTasks})</button>
              <button class="btn" data-go="import">📥 Добавить материал</button>
            </div>
          </div>
          <div class="ring" style="width:150px;height:150px">
            ${ringSVG(pct, { r: 68, sw: 13, color: "var(--gold)" })}
            <div class="r-label">${Math.round(pct * 100)}%<div class="r-sub">готово</div></div>
          </div>
        </div>

        <div class="grid grid-3">
          <div class="card"><div class="muted small">Сегодня запланировано</div><div class="big-num">${todayTasks}</div><div class="muted small">единиц чтения</div></div>
          <div class="card"><div class="muted small">Время на сегодня</div><div class="big-num">${dur(todayMin)}</div><div class="muted small">по текущей скорости</div></div>
          <div class="card"><div class="muted small">Дисциплин в работе</div><div class="big-num">${state.disciplines.length}</div><div class="muted small">активных задач</div></div>
        </div>

        ${warns}

        <div class="stack" style="margin-top:4px">
          <h2 class="sec">📚 Дисциплины</h2>
          <div class="grid grid-auto stagger">${cards}</div>
        </div>
      </div>`;
  }

  function greeting() {
    const h = new Date().getHours();
    if (h < 6) return "Доброй ночи";
    if (h < 12) return "Доброе утро";
    if (h < 18) return "Добрый день";
    return "Добрый вечер";
  }

  function emptyState(ic, title, sub, btn, onClick) {
    return `<div class="card empty"><div class="e-ic">${ic}</div><div class="e-title">${ESC(title)}</div><div class="e-sub">${ESC(sub)}</div><div style="margin-top:20px"><button class="btn primary" id="emptyCta">${ESC(btn)}</button></div></div>`;
  }

  function wireDashboard() {
    document.querySelectorAll("[data-disc]").forEach((c) =>
      c.addEventListener("click", () => {
        detailId = c.dataset.disc;
        setView("disciplines");
      })
    );
    document.querySelectorAll("[data-go]").forEach((b) =>
      b.addEventListener("click", () => setView(b.dataset.go))
    );
    const ec = document.getElementById("emptyCta");
    if (ec) ec.addEventListener("click", () => setView("import"));
  }

  // ============================================================
  //  ИМПОРТ
  // ============================================================
  function viewImport() {
    let previews = pending
      .map(
        (p, i) => `
      <div class="card" data-pidx="${i}">
        <div class="row spread center">
          <div class="row center" style="gap:10px">
            <div class="disc-icon" style="font-size:22px">${ESC(p.disc.icon || "📘")}</div>
            <div><div class="disc-name">${ESC(p.disc.name)}</div><div class="disc-meta">${ESC(p.fileName)} · ${p.parsed.count} вопр.</div></div>
          </div>
          <button class="ghost-btn danger" data-rm="${i}" title="Убрать">✕</button>
        </div>
        <div class="grid grid-3" style="margin-top:14px">
          <div class="field"><label>Название дисциплины</label><input type="text" data-f="name" data-i="${i}" value="${ESC(p.disc.name)}"></div>
          <div class="field"><label>Иконка (эмодзи)</label><input type="text" data-f="icon" data-i="${i}" value="${ESC(p.disc.icon || "📘")}" maxlength="4"></div>
          <div class="field"><label>Цвет</label><input type="color" data-f="color" data-i="${i}" value="${ESC(p.disc.color)}"></div>
          <div class="field"><label>Начать с</label><input type="date" data-f="startDate" data-i="${i}" value="${ESC(p.disc.plan.startDate)}"></div>
          <div class="field"><label>Экзамен (цель)</label><input type="date" data-f="examDate" data-i="${i}" value="${ESC(p.disc.plan.examDate)}"></div>
          <div class="field"><label>Прогонов (прочитать N раз)</label><input type="number" min="1" max="10" data-f="passes" data-i="${i}" value="${p.disc.plan.passes}"></div>
          <div class="field"><label>Режим нагрузки</label>
            <select data-f="mode" data-i="${i}">
              <option value="questions" ${p.disc.plan.mode === "questions" ? "selected" : ""}>По N вопросов/день</option>
              <option value="minutes" ${p.disc.plan.mode === "minutes" ? "selected" : ""}>По минутам/день</option>
              <option value="global" ${p.disc.plan.mode === "global" ? "selected" : ""}>В общем бюджете</option>
            </select>
          </div>
          <div class="field" data-dep="questions" data-i="${i}" style="${p.disc.plan.mode === "questions" ? "" : "display:none"}"><label>Вопросов в день</label><input type="number" min="1" data-f="perDayQuestions" data-i="${i}" value="${p.disc.plan.perDayQuestions}"></div>
          <div class="field" data-dep="minutes" data-i="${i}" style="${p.disc.plan.mode === "minutes" ? "" : "display:none"}"><label>Минут в день</label><input type="number" min="1" data-f="perDayMinutes" data-i="${i}" value="${p.disc.plan.perDayMinutes}"></div>
          <div class="field"><label>Слов в ответе (если нет в файле)</label><input type="number" min="0" data-f="assumeAnswerWords" data-i="${i}" value="${p.disc.plan.assumeAnswerWords}"></div>
        </div>
        <div class="row" style="margin-top:14px;gap:18px;flex-wrap:wrap">
          <span class="pill">📝 ${fmt(p.parsed.totalWords)} слов</span>
          <span class="pill">🔤 ${fmt(p.parsed.totalChars)} знаков</span>
          <span class="pill">⏱️ ${dur(p.parsed.totalMinutes)} на 1 прогон</span>
          <span class="pill">⏱️ ${dur(p.parsed.totalMinutes * p.disc.plan.passes)} на все прогоны</span>
        </div>
        <div class="preview-q">
          ${p.parsed.questions
            .slice(0, 8)
            .map((q) => `<div class="pq"><b>${ESC(q.num != null ? q.num + ". " : "")}</b>${ESC(q.preview)}…</div>`)
            .join("")}
          ${p.parsed.count > 8 ? `<div class="pq faint">…и ещё ${p.parsed.count - 8} вопрос(ов)</div>` : ""}
        </div>
        <div class="row" style="margin-top:14px">
          <button class="btn primary" data-add="${i}">✅ Добавить дисциплину</button>
        </div>
      </div>`
      )
      .join("");

    return `
      <div class="stack">
        <div class="card">
          <div class="dropzone" id="drop">
            <div class="dz-icon">☁️</div>
            <div class="dz-title">Перетащите файлы сюда</div>
            <div class="dz-sub">или нажмите, чтобы выбрать (.txt, .md, .docx). Вопросы и ответы определяются автоматически, включая Word-документы «Все ответы».</div>
          </div>
        </div>
        ${pending.length ? `<div class="stack">${previews}</div>` : ""}
      </div>`;
  }

  function wireImport() {
    const drop = document.getElementById("drop");
    if (!drop) return;
    drop.addEventListener("click", pickFiles);
    ["dragover", "dragenter"].forEach((ev) =>
      drop.addEventListener(ev, (e) => {
        e.preventDefault();
        drop.classList.add("drag");
      })
    );
    ["dragleave", "drop"].forEach((ev) =>
      drop.addEventListener(ev, (e) => {
        e.preventDefault();
        drop.classList.remove("drag");
      })
    );
    drop.addEventListener("drop", (e) => {
      const files = Array.from(e.dataTransfer.files || []).map((f) => f.path);
      if (files.length) ingestPaths(files);
    });

    document.querySelectorAll("[data-rm]").forEach((b) =>
      b.addEventListener("click", () => {
        pending.splice(+b.dataset.rm, 1);
        render();
      })
    );
    document.querySelectorAll("[data-add]").forEach((b) =>
      b.addEventListener("click", () => {
        const i = +b.dataset.add;
        commitPending(i);
      })
    );
    // Изменения полей превью
    document.querySelectorAll("[data-f]").forEach((inp) => {
      inp.addEventListener("input", () => {
        const i = +inp.dataset.i;
        const f = inp.dataset.f;
        let v = inp.value;
        if (["passes", "perDayQuestions", "perDayMinutes", "assumeAnswerWords"].includes(f)) v = parseInt(v, 10) || 0;
        const target = ["name", "icon", "color"].includes(f) ? pending[i].disc : pending[i].disc.plan;
        target[f] = v;
        // пересчёт длительности при смене assumeAnswerWords / passes
        if (f === "assumeAnswerWords" || f === "passes") rePreviewParse(i);
        if (f === "mode") render();
      });
    });
  }

  function rePreviewParse(i) {
    const p = pending[i];
    const rate = state.settings.speedUnit === "cpm" ? state.settings.charsPerMinute : state.settings.wordsPerMinute;
    p.parsed = C.parser.parseDocument(p.rawText, {
      unit: state.settings.speedUnit,
      rate,
      assumeAnswerWords: p.disc.plan.assumeAnswerWords
    });
    // не перерисовываем всё (чтобы не терять фокус), обновим только пиллы
    const card = document.querySelector(`[data-pidx="${i}"]`);
    if (card) {
      const pills = card.querySelectorAll(".pill");
      if (pills[0]) pills[0].textContent = "📝 " + fmt(p.parsed.totalWords) + " слов";
      if (pills[1]) pills[1].textContent = "🔤 " + fmt(p.parsed.totalChars) + " знаков";
      if (pills[2]) pills[2].textContent = "⏱️ " + dur(p.parsed.totalMinutes) + " на 1 прогон";
      if (pills[3]) pills[3].textContent = "⏱️ " + dur(p.parsed.totalMinutes * p.disc.plan.passes) + " на все прогоны";
    }
  }

  async function pickFiles() {
    const paths = await window.api.openFiles();
    if (paths && paths.length) ingestPaths(paths);
  }

  async function ingestPaths(paths) {
    for (const p of paths) {
      const res = await window.api.readFile(p);
      if (!res.ok) {
        toast("Не удалось прочитать файл: " + res.error);
        continue;
      }
      const rate = state.settings.speedUnit === "cpm" ? state.settings.charsPerMinute : state.settings.wordsPerMinute;
      const parsed = C.parser.parseDocument(res.text, {
        unit: state.settings.speedUnit,
        rate,
        assumeAnswerWords: 200
      });
      if (parsed.count === 0) {
        toast("В файле не найдено вопросов: " + res.name);
        continue;
      }
      const name = res.name.replace(/\.[^.]+$/, "");
      const colors = ["#6db3f2", "#ffd479", "#7be3a3", "#ff9eb1", "#b79bff", "#67e8e0"];
      pending.push({
        fileName: res.name,
        rawText: res.text,
        parsed,
        disc: {
          id: uuid(),
          name: name || "Дисциплина",
          color: colors[pending.length % colors.length],
          icon: "📘",
          questions: parsed.questions,
          plan: defaultPlan(today()),
          progress: {},
          importedAt: new Date().toISOString()
        }
      });
    }
    render();
  }

  function commitPending(i) {
    const p = pending[i];
    // обновляем questions из последнего parse (на случай смены assumeAnswerWords)
    p.disc.questions = p.parsed.questions;
    state.disciplines.push(p.disc);
    pending.splice(i, 1);
    save();
    refresh();
    window.ExamAudio.sparkle();
    toast("Дисциплина добавлена: " + p.disc.name);
    render();
  }

  // ============================================================
  //  ДИСЦИПЛИНЫ
  // ============================================================
  function viewDisciplines() {
    if (detailId) {
      const d = state.disciplines.find((x) => x.id === detailId);
      if (d) return discDetail(d);
      detailId = null;
    }
    if (state.disciplines.length === 0) {
      return emptyState("📚", "Нет дисциплин", "Сначала импортируйте материалы в разделе «Импорт».", "Импортировать", () => setView("import"));
    }
    const cards = state.disciplines
      .map(
        (d) => `<div class="card disc-card hoverable" data-disc="${d.id}" style="cursor:pointer">
        <div class="bar" style="background:${d.color}"></div>
        <div class="row center" style="gap:12px">
          <div class="disc-icon">${ESC(d.icon || "📘")}</div>
          <div style="flex:1"><div class="disc-name">${ESC(d.name)}</div>
          <div class="disc-meta">${d.questions.length} вопросов · ${d.plan.passes} прогона</div></div>
          <div class="ring" style="width:64px;height:64px">${ringSVG(discCompletion(d), { r: 27, sw: 7, color: d.color })}<div class="r-label" style="font-size:13px">${Math.round(discCompletion(d) * 100)}%</div></div>
        </div>
      </div>`
      )
      .join("");
    return `<div class="stack"><h2 class="sec">📚 Ваши дисциплины</h2><div class="grid grid-auto stagger">${cards}</div></div>`;
  }

  function discDetail(d) {
    const t = discTotals(d);
    const r = (plan.perDisc[d.id] && plan.perDisc[d.id].stats) || {};
    const modeOpts = {
      questions: "По N вопросов/день",
      minutes: "По минутам/день",
      global: "В общем бюджете"
    };
    const restNames = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
    return `
      <div class="stack">
        <div class="row spread center">
          <button class="btn ghost" data-back>← К дисциплинам</button>
          <button class="btn danger" data-del="${d.id}">🗑 Удалить</button>
        </div>
        <div class="card row spread center" style="gap:18px">
          <div class="row center" style="gap:14px">
            <div class="disc-icon" style="font-size:30px;width:60px;height:60px">${ESC(d.icon || "📘")}</div>
            <div><div class="disc-name" style="font-size:18px">${ESC(d.name)}</div>
            <div class="disc-meta">${t.q} вопросов · ${fmt(t.w)} слов · ${fmt(t.ch)} знаков</div></div>
          </div>
          <div class="ring" style="width:130px;height:130px">${ringSVG(discCompletion(d), { r: 58, sw: 12, color: d.color })}<div class="r-label">${Math.round(discCompletion(d) * 100)}%<div class="r-sub">готово</div></div></div>
        </div>

        <div class="card">
          <h2 class="sec">🎯 Параметры плана</h2>
          <div class="grid grid-3" style="margin-top:8px">
            <div class="field"><label>Начать с</label><input type="date" id="f_start" value="${ESC(d.plan.startDate)}"></div>
            <div class="field"><label>Экзамен (цель)</label><input type="date" id="f_exam" value="${ESC(d.plan.examDate)}"></div>
            <div class="field"><label>Прогонов (прочитать N раз)</label><input type="number" id="f_passes" min="1" max="10" value="${d.plan.passes}"></div>
            <div class="field"><label>Режим нагрузки</label><select id="f_mode">${Object.keys(modeOpts).map((m) => `<option value="${m}" ${d.plan.mode === m ? "selected" : ""}>${modeOpts[m]}</option>`).join("")}</select></div>
            <div class="field" id="dep_questions" style="${d.plan.mode === "questions" ? "" : "display:none"}"><label>Вопросов в день</label><input type="number" id="f_pdq" min="1" value="${d.plan.perDayQuestions}"></div>
            <div class="field" id="dep_minutes" style="${d.plan.mode === "minutes" ? "" : "display:none"}"><label>Минут в день</label><input type="number" id="f_pdm" min="1" value="${d.plan.perDayMinutes}"></div>
            <div class="field"><label>Слов в ответе (если нет в файле)</label><input type="number" id="f_assume" min="0" value="${d.plan.assumeAnswerWords}"></div>
            <div class="field"><label>Коэф. скорости повторения (×)</label><input type="number" id="f_rf" min="1" max="5" step="0.1" value="${d.plan.reviewSpeedFactor}"></div>
            <div class="field" style="grid-column:span 3"><label>Выходные дни (не учитываются)</label>
              <div class="chip-row" id="f_rest">${restNames.map((n, idx) => `<span class="chip ${d.plan.restDays.includes(idx + 1) ? "active" : ""}" data-rd="${idx + 1}">${n}</span>`).join("")}</div>
            </div>
          </div>
          <div class="row" style="margin-top:14px;gap:18px;flex-wrap:wrap">
            <span class="pill good">✅ ${fmt(r.doneUnits || 0)} / ${fmt(r.totalUnits || 0)} прогонов сделано</span>
            <span class="pill">📅 нужно ~${r.perDayTarget || d.plan.perDayQuestions} в день</span>
            <span class="pill">⏱️ ${dur(t.mAll)} всего на чтение</span>
          </div>
        </div>

        <div class="card">
          <h2 class="sec">📝 Вопросы (${d.questions.length})</h2>
          <div class="muted small">Нажмите на вопрос, чтобы отметить все его прогоны прочитанными / снять отметку.</div>
          <div class="preview-q" style="max-height:300px;margin-top:10px">
            ${d.questions
              .map((q, qi) => {
                const allDone = Array.from({ length: d.plan.passes }, (_, p) => P.unitKey({ qIndex: qi, pass: p + 1 })).every((k) => d.progress[k] && d.progress[k].done);
                return `<div class="pq ${allDone ? "done" : ""}" data-qtoggle="${qi}" style="cursor:pointer;border-left-color:${allDone ? "var(--good)" : d.color}"><b>${ESC(q.num != null ? q.num + "." : qi + 1 + ".")}</b> ${ESC(q.question)} <span class="faint small">· ${q.qWords + q.aWords} сл. · ${dur(q.minutes)}</span></div>`;
              })
              .join("")}
          </div>
        </div>
      </div>`;
  }

  function wireDisciplines() {
    document.querySelectorAll("[data-disc]").forEach((c) =>
      c.addEventListener("click", () => {
        detailId = c.dataset.disc;
        setView("disciplines");
      })
    );
    const ec = document.getElementById("emptyCta");
    if (ec) ec.addEventListener("click", () => setView("import"));

    // Детальная страница
    const back = document.querySelector("[data-back]");
    if (back)
      back.addEventListener("click", () => {
        detailId = null;
        render();
      });
    const del = document.querySelector("[data-del]");
    if (del)
      del.addEventListener("click", () => {
        if (!confirm("Удалить дисциплину и весь прогресс по ней?")) return;
        state.disciplines = state.disciplines.filter((x) => x.id !== del.dataset.del);
        if (detailId === del.dataset.del) detailId = null;
        save();
        refresh();
        render();
      });

    if (detailId) {
      const disc = state.disciplines.find((x) => x.id === detailId);
      if (disc) bindDiscForm(disc);
    }
  }

  function bindDiscForm(disc) {
    const upd = (rerender) => {
      save();
      refresh();
      if (rerender && detailId) render();
      else updateTopbar();
    };
    const set = (id, key, cast) => {
      const elx = document.getElementById(id);
      if (!elx) return;
      elx.addEventListener("change", () => {
        disc.plan[key] = cast ? cast(elx.value) : elx.value;
        upd(true); // перерисовываем деталь, чтобы обновить кольцо/пиллы
      });
    };
    set("f_start", "startDate");
    set("f_exam", "examDate");
    set("f_passes", "passes", (v) => Math.max(1, parseInt(v, 10) || 1));
    set("f_pdq", "perDayQuestions", (v) => Math.max(1, parseInt(v, 10) || 1));
    set("f_pdm", "perDayMinutes", (v) => Math.max(1, parseInt(v, 10) || 1));
    set("f_assume", "assumeAnswerWords", (v) => Math.max(0, parseInt(v, 10) || 0));
    set("f_rf", "reviewSpeedFactor", (v) => Math.max(1, parseFloat(v) || 1));
    const mode = document.getElementById("f_mode");
    if (mode)
      mode.addEventListener("change", () => {
        disc.plan.mode = mode.value;
        document.getElementById("dep_questions").style.display = mode.value === "questions" ? "" : "none";
        document.getElementById("dep_minutes").style.display = mode.value === "minutes" ? "" : "none";
        upd(true);
      });
    document.querySelectorAll("#f_rest .chip").forEach((c) =>
      c.addEventListener("click", () => {
        const rd = parseInt(c.dataset.rd, 10);
        const arr = disc.plan.restDays;
        const ix = arr.indexOf(rd);
        if (ix >= 0) arr.splice(ix, 1);
        else arr.push(rd);
        c.classList.toggle("active");
        upd(true);
      })
    );
    document.querySelectorAll("[data-qtoggle]").forEach((q) =>
      q.addEventListener("click", () => {
        const qi = +q.dataset.qtoggle;
        const allDone = Array.from({ length: disc.plan.passes }, (_, p) => P.unitKey({ qIndex: qi, pass: p + 1 })).every((k) => disc.progress[k] && disc.progress[k].done);
        for (let p = 1; p <= disc.plan.passes; p++) {
          const k = P.unitKey({ qIndex: qi, pass: p });
          if (allDone) delete disc.progress[k];
          else disc.progress[k] = { done: true, date: today() };
        }
        window.ExamAudio.chime();
        save();
        refresh();
        render();
      })
    );
  }

  // ============================================================
  //  СЕГОДНЯ
  // ============================================================
  function viewToday() {
    const date = todayCursor;
    const isToday = date === today();
    const units = (plan.combined && plan.combined[date]) || [];
    // Сгруппируем по дисциплине
    const byDisc = {};
    units.forEach((u) => {
      (byDisc[u.discId] = byDisc[u.discId] || []).push(u);
    });

    let groups = "";
    const discIds = Object.keys(byDisc);
    if (discIds.length === 0) {
      groups = `<div class="card empty"><div class="e-ic">🌥️</div><div class="e-title">На ${prettyDate(date)} ничего не запланировано</div><div class="e-sub">Возможно, материал уже прочитан или день — выходной.</div></div>`;
    } else {
      groups = discIds
        .map((id) => {
          const d = state.disciplines.find((x) => x.id === id);
          const us = byDisc[id];
          let mins = 0;
          us.forEach((u) => (mins += u.minutes));
          const items = us
            .map((u) => {
              const q = d.questions[u.qIndex];
              const done = d.progress[P.unitKey(u)] && d.progress[P.unitKey(u)].done;
              return `<div class="task-item ${done ? "done" : ""}" data-unit="${id}|${u.qIndex}|${u.pass}">
                <div class="ti-check">✓</div>
                <div class="ti-num">${ESC(q && q.num != null ? q.num : u.qIndex + 1)}</div>
                <div class="ti-body">
                  <div class="ti-q">${ESC(q ? q.question : "")}</div>
                  <div class="ti-meta"><span class="pass-badge">прогон ${u.pass}/${d.plan.passes}</span><span>📝 ${fmt((q ? q.qWords + q.aWords : 0))} слов</span><span>⏱️ ${dur(u.minutes)}</span></div>
                </div>
              </div>`;
            })
            .join("");
          return `<div class="task-group">
            <div class="tg-head"><div class="disc-icon" style="font-size:20px;width:38px;height:38px">${ESC(d ? d.icon || "📘" : "")}</div>
            <div style="flex:1"><div class="disc-name" style="font-size:14px">${ESC(d ? d.name : "")}</div><div class="disc-meta">${us.length} ед. · ${dur(mins)}</div></div>
            <span class="pill">${us.filter((u) => d.progress[P.unitKey(u)] && d.progress[P.unitKey(u)].done).length}/${us.length} готово</span>
          </div>${items}</div>`;
        })
        .join("");
    }

    // Сводка пересчёта
    let totalRemain = 0,
      totalDays = 0;
    state.disciplines.forEach((d) => {
      const r = plan.perDisc[d.id] && plan.perDisc[d.id].stats;
      if (r) {
        totalRemain += r.remainingUnits;
        totalDays = Math.max(totalDays, r.daysAvailable);
      }
    });
    const perDayAll = totalRemain && totalDays ? Math.ceil(totalRemain / totalDays) : 0;

    return `
      <div class="stack">
        <div class="card">
          <div class="task-day-head">
            <div>
              <div class="small muted">${isToday ? "Сегодня" : "Выбранный день"}</div>
              <h2 class="sec" style="margin-top:2px">${prettyDate(date)} · ${WEEK[P.weekday(date)]}</h2>
            </div>
            <div class="day-nav">
              <button class="dn-btn" data-day="-1">‹</button>
              <button class="btn" data-today>Сегодня</button>
              <button class="dn-btn" data-day="1">›</button>
            </div>
          </div>
          <div class="row wrap" style="gap:10px;margin-top:6px">
            <span class="pill">📋 ${units.length} единиц на день</span>
            <span class="pill">⏱️ ${dur(units.reduce((a, u) => a + u.minutes, 0))} чтения</span>
            <button class="btn primary" data-all="1">✅ Отметить всё за день</button>
            <button class="btn ghost" data-all="0">↺ Снять всё</button>
          </div>
          <div class="warn-box info" style="margin-top:12px">
            <span>🔄</span><span>Осталось всего <b>${fmt(totalRemain)}</b> единиц по всем дисциплинам. При текущих параметрах нужно в среднем <b>~${perDayAll}</b> в день, чтобы успеть ко всем экзаменам. Всё пересчитывается автоматически по мере вашей отметки.</span>
          </div>
        </div>
        ${groups}
      </div>`;
  }

  function wireToday() {
    document.querySelectorAll("[data-day]").forEach((b) =>
      b.addEventListener("click", () => {
        todayCursor = P.addDays(todayCursor, parseInt(b.dataset.day, 10));
        window.ExamAudio.nav();
        render();
      })
    );
    const tb = document.querySelector("[data-today]");
    if (tb)
      tb.addEventListener("click", () => {
        todayCursor = today();
        render();
      });
    document.querySelectorAll(".task-item").forEach((it) =>
      it.addEventListener("click", () => {
        const [id, qi, pass] = it.dataset.unit.split("|");
        const d = state.disciplines.find((x) => x.id === id);
        if (!d) return;
        const k = P.unitKey({ qIndex: +qi, pass: +pass });
        if (d.progress[k] && d.progress[k].done) delete d.progress[k];
        else d.progress[k] = { done: true, date: todayCursor };
        window.ExamAudio.chime();
        save();
        refresh();
        render();
        updateTopbar();
      })
    );
    document.querySelectorAll("[data-all]").forEach((b) =>
      b.addEventListener("click", () => {
        const mark = b.dataset.all === "1";
        const units = (plan.combined && plan.combined[todayCursor]) || [];
        units.forEach((u) => {
          const d = state.disciplines.find((x) => x.id === u.discId);
          if (!d) return;
          const k = P.unitKey(u);
          if (mark) d.progress[k] = { done: true, date: todayCursor };
          else delete d.progress[k];
        });
        if (mark) window.ExamAudio.sparkle();
        save();
        refresh();
        render();
        updateTopbar();
      })
    );
  }

  // ============================================================
  //  СТАТИСТИКА
  // ============================================================
  function viewStats() {
    if (state.disciplines.length === 0) {
      return emptyState("📊", "Нет данных", "Добавьте дисциплины, чтобы увидеть статистику.", "Импорт", () => setView("import"));
    }
    let total = 0,
      done = 0,
      words = 0,
      chars = 0,
      minAll = 0;
    state.disciplines.forEach((d) => {
      const units = P.buildUnits(d, state.settings);
      const ds = P.doneSet(d);
      total += units.length;
      done += units.filter((u) => ds.has(P.unitKey(u))).length;
      const t = discTotals(d);
      words += t.w;
      chars += t.ch;
      minAll += t.mAll;
    });
    const pct = total ? done / total : 0;

    // Распределение по дням (минуты)
    const dates = Object.keys(plan.combined || {}).sort();
    let maxMin = 1;
    dates.forEach((dt) => plan.combined[dt].forEach((u) => (maxMin = Math.max(maxMin, u.minutes))));
    let step = 1;
    if (dates.length > 40) step = Math.ceil(dates.length / 40);
    const bars = dates
      .filter((_, i) => i % step === 0)
      .map((dt) => {
        let m = 0;
        plan.combined[dt].forEach((u) => (m += u.minutes));
        const h = Math.max(4, (m / maxMin) * 150);
        const isT = dt === today();
        return `<div class="bar-col ${isT ? "today" : ""}"><div class="b" style="height:${h}px" title="${prettyDate(dt)}: ${dur(m)}"></div><div class="bl">${P.parseDate(dt).getDate()}</div></div>`;
      })
      .join("");

    const rings = state.disciplines
      .map(
        (d) => `<div class="card row center" style="gap:14px">
        <div class="ring" style="width:84px;height:84px">${ringSVG(discCompletion(d), { r: 36, sw: 9, color: d.color })}<div class="r-label" style="font-size:16px">${Math.round(discCompletion(d) * 100)}%</div></div>
        <div style="flex:1;min-width:0"><div class="disc-name" style="font-size:14px">${ESC(d.name)}</div>
        <div class="disc-meta">${d.questions.length} вопр. · ${fmt(discTotals(d).w)} слов · ${dur(discTotals(d).mAll)}</div></div>
      </div>`
      )
      .join("");

    return `
      <div class="stack">
        <div class="card row spread center" style="gap:18px">
          <div style="flex:1">
            <h2 class="sec">Общая готовность</h2>
            <div class="muted small">${fmt(done)} из ${fmt(total)} прогонов вопросов завершено.</div>
          </div>
          <div class="ring" style="width:140px;height:140px">${ringSVG(pct, { r: 62, sw: 12, color: "var(--gold)" })}<div class="r-label">${Math.round(pct * 100)}%</div></div>
        </div>

        <div class="grid grid-4">
          <div class="card"><div class="muted small">Всего вопросов</div><div class="big-num">${fmt(state.disciplines.reduce((a, d) => a + d.questions.length, 0))}</div></div>
          <div class="card"><div class="muted small">Всего слов</div><div class="big-num">${fmt(words)}</div></div>
          <div class="card"><div class="muted small">Всего знаков</div><div class="big-num">${fmt(chars)}</div></div>
          <div class="card"><div class="muted small">Время на всё (все прогоны)</div><div class="big-num" style="font-size:24px">${dur(minAll)}</div></div>
        </div>

        <div class="card">
          <h2 class="sec">📅 Распределение нагрузки по дням</h2>
          <div class="muted small">Высота столбца — минуты чтения в день. Золотой — сегодня.</div>
          <div class="bars">${bars || '<div class="muted">Нет запланированных дней.</div>'}</div>
        </div>

        <div class="card">
          <h2 class="sec">📚 Готовность по дисциплинам</h2>
          <div class="stack" style="margin-top:8px">${rings}</div>
        </div>
      </div>`;
  }
  function wireStats() {
    const ec = document.getElementById("emptyCta");
    if (ec) ec.addEventListener("click", () => setView("import"));
  }

  // ============================================================
  //  СОВЕТЫ
  // ============================================================
  function viewTips() {
    const tips = [
      {
        ic: "🌥️",
        t: "Распределяйте, а не «зубрите»",
        b: "Распределённая практика (spaced practice) обходит массированную: в мета-анализе Кепеды и соавторов (2006, 271 сравнение) отсроченное воспоминание в среднем 47,3% против 36,7% при «краминге», при равном времени. App автоматически раскидывает материал по дням — не пытайтесь прочитать всё за ночь.",
        src: "activerecalling.com/blog/distributed-practice-vs-massed-practice"
      },
      {
        ic: "🔁",
        t: "Повторяйте 3–5 раз — это норма",
        b: "Для концептуального материала нужно 3–5 успешных воспроизведений с разрывом во времени. Ваш параметр «прочитать файл N раз» (по умолчанию 3) как раз отражает это. Каждое повторение считается, только если вы вспомнили сами, без подглядывания.",
        src: "aevoran.com/en/how-many-times-repeat-active-recall"
      },
      {
        ic: "✍️",
        t: "Активное воспроизведение (active recall)",
        b: "Тестирование себя эффективнее перечитывания: в классическом эксперименте Ройдигера и Карпика (2006) удержание через неделю — 61% против 40% у перечитывания (+52%). Отмечайте в приложении конкретные номера вопросов, которые реально воспроизвели.",
        src: "flashcard-maker.cc/blog/recall-study-method"
      },
      {
        ic: "🔀",
        t: "Чередуйте дисциплины (interleaving)",
        b: "Перемешивание тем в одной сессии улучшает долгосрочное удержание и перенос навыка, хотя кажется сложнее. Режим «в общем бюджете» в приложении именно это и делает: понемногу из каждого файла каждый день.",
        src: "www.adobe.com/acrobat/resources/interleaving-study-method.html"
      },
      {
        ic: "🗓️",
        t: "Начинайте за 7–10 дней (лучше раньше)",
        b: "Структурированный повтор за 7–10 дней даёт прирост 20–30% к баллам против краминга. Чем дальше экзамен, тем больше можно растянуть интервалы между прогонами (правило: ~20–40% времени до экзамена).",
        src: "www.5staressays.com/blog/how-to-review-before-exams-effectively"
      },
      {
        ic: "🍅",
        t: "Техника Помодоро против выгорания",
        b: "Блоки по 25 минут с 5-минутными перерывами, после 4 блоков — длинный перерыв. 8–10 таких блоков в день (≈4–5 часов фокуса) — здоровый предел. App считает время по вашей скорости чтения, так что планируйте Pomodoro поверх него.",
        src: "www.learnco.ai/blog/pomodoro-technique-studying"
      },
      {
        ic: "💡",
        t: "Трудность — это признак пользы",
        b: "Эффект «желательной трудности» (Бьорк): когда вспоминать тяжело, память укрепляется сильнее. Не пугайтесь, если распределённое повторение ощущается менее гладким, чем зубрёжка, — это работает лучше.",
        src: "chunks.app/blog/the-science-of-spaced-repetition"
      }
    ];
    return `<div class="stack"><h2 class="sec">💡 Как готовиться эффективно — по данным когнитивной науки</h2>
      <div class="grid grid-2 stagger">${tips
        .map(
          (x) => `<div class="card tip-card"><div class="tip-ic">${x.ic}</div><div style="flex:1"><div class="tip-title">${ESC(x.t)}</div><div class="tip-body">${ESC(x.b)}</div><div class="tip-src">источник: <a href="https://${x.src}" target="_blank" rel="noopener">${ESC(x.src)}</a></div></div></div>`
        )
        .join("")}</div>
      <div class="card warn-box info"><span>🧭</span><span>Приложение заложило эти принципы в расчёт: равномерное распределение, несколько прогонов, режим «понемногу из каждой дисциплины» и авто-пересчёт при отставании.</span></div>
    </div>`;
  }

  // ============================================================
  //  НАСТРОЙКИ
  // ============================================================
  function viewSettings() {
    const s = state.settings;
    const restNames = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
    return `
      <div class="stack">
        <div class="card">
          <h2 class="sec">⚡ Скорость чтения</h2>
          <div class="muted small">От неё зависит время на каждый вопрос и весь план.</div>
          <div class="grid grid-2" style="margin-top:10px">
            <div class="field"><label>Единица измерения</label>
              <select id="s_unit">
                <option value="wpm" ${s.speedUnit === "wpm" ? "selected" : ""}>Слов в минуту</option>
                <option value="cpm" ${s.speedUnit === "cpm" ? "selected" : ""}>Знаков в минуту</option>
              </select>
            </div>
            <div class="field"><label id="s_rate_label">Скорость (слов/мин)</label><input type="number" id="s_rate" min="30" value="${s.speedUnit === "cpm" ? s.charsPerMinute : s.wordsPerMinute}"></div>
          </div>
          <div class="muted small" style="margin-top:8px">Средняя скорость взрослого читателя — около 200–250 слов/мин (≈1000–1500 знаков/мин). Если укажете нереалистично высокое значение, время будет слишком маленьким.</div>
        </div>

        <div class="card">
          <h2 class="sec">📆 Выходные дни (глобально)</h2>
          <div class="muted small">Эти дни исключаются из расписания всех дисциплин по умолчанию.</div>
          <div class="chip-row" id="s_rest" style="margin-top:10px">${restNames.map((n, i) => `<span class="chip ${s.restDays.includes(i + 1) ? "active" : ""}" data-rd="${i + 1}">${n}</span>`).join("")}</div>
        </div>

        <div class="card">
          <h2 class="sec">🌍 Общий бюджет времени</h2>
          <div class="field" style="max-width:320px"><label>Минут в день на все дисциплины (режим «в общем бюджете»)</label><input type="number" id="s_budget" min="5" value="${s.global.dailyMinutes}"></div>
        </div>

        <div class="card row spread center">
          <div><h2 class="sec">🔊 Звук и анимации</h2><div class="muted small">Мягкие перезвоны при отметке выполненного.</div></div>
          <label class="row center" style="gap:10px;cursor:pointer"><span class="muted small">Звук</span>
            <input type="checkbox" id="s_sound" ${s.soundEnabled ? "checked" : ""} style="width:20px;height:20px;accent-color:var(--accent)"></label>
        </div>

        <div class="card">
          <h2 class="sec">💾 Данные</h2>
          <div class="muted small">Все данные хранятся локально на вашем компьютере (в папке данных приложения). Ничего не отправляется в сеть.</div>
          <div class="row" style="margin-top:12px;gap:10px">
            <button class="btn" id="s_export">⬇ Экспорт состояния (JSON)</button>
            <button class="btn danger" id="s_reset">🗑 Сбросить всё</button>
          </div>
        </div>
      </div>`;
  }

  function wireSettings() {
    const unit = document.getElementById("s_unit");
    if (unit)
      unit.addEventListener("change", () => {
        state.settings.speedUnit = unit.value;
        document.getElementById("s_rate_label").textContent = unit.value === "cpm" ? "Скорость (знаков/мин)" : "Скорость (слов/мин)";
        document.getElementById("s_rate").value = unit.value === "cpm" ? state.settings.charsPerMinute : state.settings.wordsPerMinute;
        save();
        refresh();
      });
    const rate = document.getElementById("s_rate");
    if (rate)
      rate.addEventListener("change", () => {
        const v = Math.max(1, parseInt(rate.value, 10) || 1);
        if (state.settings.speedUnit === "cpm") state.settings.charsPerMinute = v;
        else state.settings.wordsPerMinute = v;
        save();
        refresh();
        toast("Скорость обновлена, план пересчитан");
      });
    document.querySelectorAll("#s_rest .chip").forEach((c) =>
      c.addEventListener("click", () => {
        const rd = parseInt(c.dataset.rd, 10);
        const arr = state.settings.restDays;
        const ix = arr.indexOf(rd);
        if (ix >= 0) arr.splice(ix, 1);
        else arr.push(rd);
        c.classList.toggle("active");
        save();
        refresh();
      })
    );
    const budget = document.getElementById("s_budget");
    if (budget)
      budget.addEventListener("change", () => {
        state.settings.global.dailyMinutes = Math.max(1, parseInt(budget.value, 10) || 60);
        save();
        refresh();
      });
    const sound = document.getElementById("s_sound");
    if (sound)
      sound.addEventListener("change", () => {
        state.settings.soundEnabled = sound.checked;
        window.ExamAudio.setEnabled(sound.checked);
        document.getElementById("soundBtn").textContent = sound.checked ? "🔊" : "🔇";
        if (sound.checked) window.ExamAudio.chime();
        save();
      });
    const exp = document.getElementById("s_export");
    if (exp)
      exp.addEventListener("click", () => {
        const blob = new Blob([JSON.stringify(state, null, 2)], { type: "application/json" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "exam-planner-backup.json";
        a.click();
        toast("Экспорт готов");
      });
    const reset = document.getElementById("s_reset");
    if (reset)
      reset.addEventListener("click", () => {
        if (!confirm("Удалить ВСЕ дисциплины и прогресс? Действие необратимо.")) return;
        state = defaultState();
        save();
        refresh();
        toast("Всё сброшено");
        setView("dashboard");
      });
  }

  // ============================================================
  boot();
})();
