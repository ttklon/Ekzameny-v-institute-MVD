/*
 * views.js — экраны приложения.
 *
 * Каждый экран — функция, которая возвращает готовый DOM-элемент. Всё
 * пересобирается при изменении состояния: экраны не обновляют себя частями,
 * поэтому интерфейс не расходится с данными. Для 150 вопросов это доли
 * миллисекунды, для 2000 — несколько миллисекунд, что незаметно.
 *
 * Экраны:
 *   dashboard   — обзор: сколько готово, что сегодня, ближайшие дни;
 *   today       — день: список вопросов, отметки, перенос на другой день;
 *   disciplines — список дисциплин;
 *   discipline  — одна дисциплина: план, вопросы, настройки, статистика;
 *   calendar    — календарь нагрузки по дням;
 *   stats       — объёмы, время, серия дней;
 *   tips        — как готовиться: что говорит наука;
 *   settings    — скорость чтения, звук, данные.
 */
(function (root) {
  "use strict";

  const UI = root.UI;
  const h = UI.h;
  const P = root.ExamCore.planner;

  const ACCENTS = ["#2c7fc4", "#7b6cc4", "#3aa88b", "#d99a3c", "#cf6b7a", "#4a9fb8"];

  function state() {
    return root.Store.state;
  }
  function settings() {
    return root.Store.state.settings;
  }
  function today() {
    return P.todayStr();
  }

  /** Пересчёт всего плана: вызывается после любого изменения. */
  let cache = null;
  let cacheKey = "";
  function plan() {
    const s = state();
    // Ключ кэша должен учитывать всё, что влияет на расчёт: и план, и отметки,
    // и объём вопросов (оценку можно поменять в параметрах дисциплины).
    const key =
      String(s.disciplines.length) +
      "|" +
      JSON.stringify(s.settings) +
      "|" +
      s.disciplines
        .map(
          (d) =>
            d.id +
            ":" +
            JSON.stringify(d.plan) +
            ":" +
            JSON.stringify(d.reads) +
            ":" +
            (d.questions ? d.questions.length : 0) +
            ":" +
            volumeStamp(d)
        )
        .join(";");
    if (cache && cacheKey === key) return cache;
    cache = P.computeAll({ settings: s.settings, disciplines: s.disciplines }, today());
    cacheKey = key;
    return cache;
  }

  function discQuestions(d) {
    return d.questions || [];
  }

  /** Быстрый отпечаток объёма: сумма слов и знаков по вопросам. */
  function volumeStamp(d) {
    let w = 0;
    let c = 0;
    const qs = d.questions || [];
    for (let i = 0; i < qs.length; i++) {
      w += qs[i].words || 0;
      c += qs[i].chars || 0;
    }
    return w + "." + c;
  }

  /** Минуты вопроса при первом прогоне — для показа объёма. */
  function qMinutes(d, q, pass) {
    return P.questionMinutes(d, q, pass || 1, settings());
  }

  function totalMinutesOf(d) {
    return P.totalMinutes(d, settings());
  }

  // =====================================================================
  //  ОБЗОР
  // =====================================================================

  function viewDashboard() {
    const s = state();
    const planData = plan();
    const discs = root.Store.activeDisciplines();
    const wrap = h("div.grid", { style: { gap: "18px" } });

    if (!discs.length) {
      wrap.appendChild(emptyState());
      return wrap;
    }

    const progressPct = planData.totals.progress * 100;
    const todayMin = planData.todayMinutes;

    // --- Верхний блок: кольцо готовности + главные цифры -------------
    const hero = h("div.card", { style: { display: "grid", gridTemplateColumns: "auto 1fr", gap: "30px", alignItems: "center" } });
    const ringEl = UI.ring(progressPct, { size: 172, stroke: 13, label: "готовность" });

    let todaySub;
    if (todayMin > 0) {
      todaySub =
        "около " + UI.dur(todayMin) + " · " +
        planData.todayTasks.length + " " + UI.plural(planData.todayTasks.length, "вопрос", "вопроса", "вопросов");
    } else {
      todaySub = "на сегодня работа не запланирована";
    }

    const metrics = h("div.grid.cols-3", { style: { gap: "16px" } }, [
      h("div.metric", [
        h("div.value", [h("span.num", "0"), h("small", "мин")]),
        h("div.label", "сегодня"),
        h("div.sub", todaySub)
      ]),
      h("div.metric", [
        h("div.value", [h("span.num", "0"), h("small", "ч")]),
        h("div.label", "осталось"),
        h("div.sub", "по всем дисциплинам")
      ]),
      h("div.metric", [
        h("div.value", [h("span.num", "0")]),
        h("div.label", "дней до экзамена"),
        h("div.sub", nearestExamText())
      ])
    ]);

    hero.appendChild(ringEl);
    hero.appendChild(h("div.grid", { style: { gap: "20px" } }, [
      h("div", [
        h("div.section-label", "ваша подготовка"),
        h("h2", {
          style: {
            fontFamily: "var(--font-display)",
            fontSize: "29px",
            fontWeight: "600",
            lineHeight: "1.14",
            marginTop: "4px"
          }
        }, greeting()),
        h("p.soft", { style: { marginTop: "6px", fontSize: "14px", maxWidth: "54ch" } }, heroLine(planData))
      ]),
      metrics
    ]));
    wrap.appendChild(hero);

    // Анимация цифр после вставки.
    requestAnimationFrame(() => {
      const vals = metrics.querySelectorAll(".metric .value .num");
      if (vals.length < 3) return;
      UI.animateNumber(vals[0], Math.round(todayMin), { duration: 900 });
      UI.animateNumber(vals[1], planData.totals.minutesLeft / 60, {
        duration: 1000,
        format: (v) => (v >= 10 ? String(Math.round(v)) : v.toFixed(1).replace(".", ","))
      });
      const daysLeft = daysToNearestExam();
      UI.animateNumber(vals[2], daysLeft == null ? 0 : daysLeft, { duration: 900 });
    });

    // --- Сегодня -----------------------------------------------------
    const planForToday = h("div.card");
    planForToday.appendChild(
      h("div.card-title", [
        h("div", [
          h("h2", "Сегодня"),
          h("div.muted", { style: { fontSize: "12.5px", marginTop: "2px" } }, UI.dateLong(today()))
        ]),
        h("div.row", [
          UI.button("Все дни", { size: "sm", kind: "ghost", icon: "calendar", onClick: () => root.App.go("calendar") })
        ])
      ])
    );

    if (!planData.todayTasks.length) {
      planForToday.appendChild(
        h("div", { style: { padding: "18px 0", textAlign: "center" } }, [
          h("p.soft", "На сегодня по плану ничего нет."),
          h("p.muted", { style: { fontSize: "12.5px", marginTop: "4px" } },
            "Можно прочитать что-то заранее — план пересчитается сам.")
        ])
      );
    } else {
      const list = h("div.task-list");
      for (const task of groupTodayTasks(planData.todayTasks)) {
        list.appendChild(taskRow(task, today()));
      }
      planForToday.appendChild(list);
      planForToday.appendChild(
        h("div.row", { style: { marginTop: "14px" } }, [
          UI.button("Отметить всё прочитанным", {
            kind: "primary",
            icon: "check",
            onClick: () => markAllToday()
          }),
          h("div.spacer"),
          h("span.muted", { style: { fontSize: "12.5px" } },
            "Всего " + UI.dur(todayMin) + " — это " + shareText(todayMin))
        ])
      );
    }
    wrap.appendChild(planForToday);

    // --- Дисциплины и ближайшие дни ---------------------------------
    const two = h("div.grid.cols-2");

    // Ближайшие дни
    const upcoming = h("div.card");
    upcoming.appendChild(h("div.card-title", [h("h2", "Ближайшие дни")]));
    const upList = h("div", { style: { display: "grid", gap: "8px" } });
    const nextDays = planData.upcoming.filter((d) => d.date >= today()).slice(0, 6);
    if (!nextDays.length) {
      upList.appendChild(h("p.muted", "Пока ничего не запланировано."));
    }
    for (const day of nextDays) {
      const isToday = day.date === today();
      upList.appendChild(
        h("div.row", {
          style: {
            padding: "9px 12px",
            borderRadius: "12px",
            background: isToday ? "var(--accent-soft)" : "rgba(255,255,255,.42)",
            cursor: "pointer"
          },
          onclick: () => root.App.go("today", { date: day.date })
        }, [
          h("div", { style: { minWidth: "64px" } }, [
            h("div", { style: { fontWeight: "700", fontSize: "13px" } }, UI.dateShort(day.date)),
            h("div.muted", { style: { fontSize: "11px" } }, UI.weekDayShort(day.date))
          ]),
          h("div.mini-bar", { style: { flex: "1 1 auto" } }, [
            h("i", { style: { width: Math.min(100, (day.minutes / Math.max(30, planData.totals.maxDayMinutes || 60)) * 100) + "%" } })
          ]),
          h("div", { style: { fontSize: "12.5px", fontWeight: "700", minWidth: "62px", textAlign: "right" } }, UI.dur(day.minutes)),
          h("div.muted", { style: { fontSize: "11.5px", minWidth: "58px", textAlign: "right" } },
            day.items + " " + UI.plural(day.items, "вопрос", "вопроса", "вопросов"))
        ])
      );
    }
    upcoming.appendChild(upList);
    two.appendChild(upcoming);

    // Дисциплины — компактно
    const discBox = h("div.card");
    discBox.appendChild(
      h("div.card-title", [
        h("h2", "Дисциплины"),
        UI.button("Все", { size: "sm", kind: "ghost", icon: "chevronRight", onClick: () => root.App.go("disciplines") })
      ])
    );
    const dlist = h("div", { style: { display: "grid", gap: "9px" } });
    for (const d of discs.slice(0, 5)) {
      const pd = planData.perDisc[d.id];
      const pct = pd && pd.stats ? pd.stats.progress * 100 : 0;
      dlist.appendChild(
        h("div", { style: { cursor: "pointer" }, onclick: () => root.App.go("discipline", { id: d.id }) }, [
          h("div.row", { style: { justifyContent: "space-between", marginBottom: "5px" } }, [
            h("span", { style: { fontWeight: "600", fontSize: "13.5px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" } },
              d.name),
            h("span.mono", { style: { fontSize: "12.5px", fontWeight: "700", color: "var(--ink-soft)" } },
              Math.round(pct) + "%")
          ]),
          h("div.mini-bar", [h("i", { style: { width: pct + "%", background: "linear-gradient(90deg, " + accentOf(d) + ", " + accentOf(d) + "aa)" } })])
        ])
      );
    }
    discBox.appendChild(dlist);
    two.appendChild(discBox);
    wrap.appendChild(two);

    // --- Предупреждения ---------------------------------------------
    const warns = planData.warnings.filter((w) => w.type !== "peak" && w.type !== "too-few-days");
    if (warns.length) {
      const box = h("div.card");
      box.appendChild(h("div.card-title", [h("h2", "Стоит поправить")]));
      const list = h("div", { style: { display: "grid", gap: "9px" } });
      for (const w of warns.slice(0, 4)) {
        list.appendChild(
          h("div.warn-box", [
            UI.icon("warn"),
            h("div", [
              w.disciplineName ? h("b", { style: { display: "block", marginBottom: "2px" } }, w.disciplineName) : null,
              h("span", w.text)
            ])
          ])
        );
      }
      box.appendChild(list);
      wrap.appendChild(box);
    }

    return wrap;
  }

  function text(t) {
    return document.createTextNode(String(t));
  }

  function greeting() {
    const hr = new Date().getHours();
    if (hr < 5) return "Тихой ночи";
    if (hr < 12) return "Доброе утро";
    if (hr < 18) return "Добрый день";
    return "Добрый вечер";
  }

  function heroLine(planData) {
    const pct = Math.round(planData.totals.progress * 100);
    const left = planData.totals.minutesLeft;
    if (!planData.totals.passesTotal) return "Добавьте файл с вопросами — и программа разложит работу по дням.";
    if (pct >= 99) return "Всё прочитано. Осталось повторить перед экзаменом — отметьте повторные чтения, и план обновится.";
    if (left <= 0) return "Материал распределён полностью. Отмечайте прочитанное — остальное программа пересчитает сама.";
    return (
      "Пройдено " + pct + "% работы. Осталось " + UI.durLong(left) +
      " чтения — это примерно " + Math.round(left / 60) + " ч в тишине и покое."
    );
  }

  function shareText(minutes) {
    const s = settings();
    const words = Math.round(minutes * (s.wordsPerMinute || 150));
    return (
      "около " + UI.num(words) + " " + UI.plural(words, "слово", "слова", "слов") +
      " при " + (s.wordsPerMinute || 150) + " " + UI.plural(s.wordsPerMinute || 150, "слове", "словах", "словах") + " в минуту"
    );
  }

  function nearestExamText() {
    let best = null;
    for (const d of root.Store.activeDisciplines()) {
      if (!d.plan || !P.isValidDate(d.plan.examDate)) continue;
      if (!best || d.plan.examDate < best.date) best = { date: d.plan.examDate, name: d.name };
    }
    if (!best) return "дата экзамена не задана";
    return best.name + " · " + UI.dateShort(best.date);
  }

  function daysToNearestExam() {
    let best = null;
    for (const d of root.Store.activeDisciplines()) {
      if (!d.plan || !P.isValidDate(d.plan.examDate)) continue;
      if (!best || d.plan.examDate < best) best = d.plan.examDate;
    }
    if (!best) return null;
    return P.daysBetween(today(), best);
  }

  function accentOf(d) {
    return ACCENTS[(d.accent || 0) % ACCENTS.length];
  }

  /**
   * Слияние задач одного вопроса в один пункт списка.
   * Если сегодня вопрос и читается впервые, и повторяется — показываем одну
   * строку, а не две: так понятнее, что делать.
   */
  function groupTodayTasks(tasks) {
    const map = new Map();
    for (const t of tasks) {
      const key = t.discId + ":" + t.qIndex;
      if (!map.has(key)) map.set(key, { ...t, passes: [], minutes: 0 });
      const g = map.get(key);
      g.passes.push(t.pass);
      g.minutes += t.minutes;
      if (t.kind === "new") g.kind = "new";
    }
    return Array.from(map.values());
  }

  /** Строка задачи: отметка, название вопроса, объём. */
  function taskRow(task, date) {
    const d = root.Store.getDiscipline(task.discId);
    const q = d && d.questions[task.qIndex];
    if (!d || !q) return h("div");
    const reads = (d.reads && d.reads[String(task.qIndex)]) || [];
    const done = reads.indexOf(date) !== -1;
    const passes = task.passes && task.passes.length ? task.passes : [];
    const isNew = passes.indexOf(1) !== -1 || task.kind === "new";

    const check = h("button.task-check" + (done ? ".on" : ""), {
      title: done ? "Снять отметку" : "Отметить прочитанным",
      onclick: (e) => {
        e.stopPropagation();
        const next = !done;
        root.Store.setRead(d.id, task.qIndex, date, next);
        root.Sound.play(next ? "check" : "uncheck");
        if (next) celebrate(d, task.qIndex, date);
        root.App.refresh();
      }
    }, [UI.icon("check")]);

    const meta = h("div.task-meta", [
      h("span", { style: { color: accentOf(d), fontWeight: "700" } }, d.name),
      h("span", "№ " + q.num),
      isNew ? h("span.tag.new", "впервые") : h("span.tag.repeat", "повтор" + (passes.length ? " " + passes.join("+") : "")),
      q.estimated ? h("span.tag.warn", "объём оценён") : null,
      h("span", q.aWords + " " + UI.plural(q.aWords, "слово", "слова", "слов") + " в ответе")
    ]);

    return h("div.task" + (done ? ".done" : ""), [
      check,
      h("div.task-body", [
        h("div.task-title", q.title || ("Вопрос " + q.num)),
        meta
      ]),
      h("div", { style: { display: "grid", gap: "4px", justifyItems: "end" } }, [
        h("div.task-time", UI.dur(task.minutes)),
        h("button.btn.btn-ghost.btn-sm", {
          style: { padding: "2px 8px", fontSize: "11.5px" },
          onclick: (e) => {
            e.stopPropagation();
            root.Sound.play("tap");
            root.App.openQuestion(d.id, task.qIndex, date);
          }
        }, "читать")
      ])
    ]);
  }

  /** Небольшой праздник при отметке: звук + мягкая вспышка. */
  function celebrate(d, qIndex, date) {
    const pd = plan().perDisc[d.id];
    if (!pd) return;
    const completed = Object.keys(d.reads || {}).filter((k) => {
      const st = P.questionState(d, Number(k), settings());
      return st.done >= st.passes;
    }).length;
    const allDone = d.questions.length > 0 && completed >= d.questions.length;
    const todayList = groupTodayTasks(plan().todayTasks.filter((t) => t.discId === d.id));
    const allTodayDone = todayList.every((t) => {
      const r = (d.reads && d.reads[String(t.qIndex)]) || [];
      return r.indexOf(date) !== -1;
    });
    if (allDone) {
      root.Sound.play("complete");
      UI.toast({
        kind: "ok",
        title: "Дисциплина пройдена",
        text: "«" + d.name + "» — все вопросы прочитаны нужное число раз. Отличная работа.",
        duration: 6000
      });
      sparkleBurst();
    } else if (allTodayDone) {
      root.Sound.play("complete");
      UI.toast({ kind: "ok", title: "План на день выполнен", text: "Всё, что было на сегодня, отмечено.", duration: 5000 });
      sparkleBurst();
    }
  }

  /** Вспышка «искр» по экрану — короткая и ненавязчивая. */
  function sparkleBurst() {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const layer = h("div", {
      style: {
        position: "fixed",
        inset: "0",
        pointerEvents: "none",
        zIndex: "150",
        overflow: "hidden"
      }
    });
    document.body.appendChild(layer);
    const colors = ["#7cc0ee", "#a8e0c9", "#f5d79b", "#c9b6f0", "#ffffff"];
    for (let i = 0; i < 26; i++) {
      const size = 5 + Math.random() * 8;
      const dot = h("i", {
        style: {
          position: "absolute",
          left: "50%",
          top: "46%",
          width: size + "px",
          height: size + "px",
          borderRadius: Math.random() > 0.5 ? "50%" : "2px",
          background: colors[i % colors.length],
          opacity: "0.95",
          transform: "translate(-50%,-50%)",
          transition: "transform 1.05s cubic-bezier(.16,1,.3,1), opacity .95s ease-out"
        }
      });
      layer.appendChild(dot);
      const angle = Math.random() * Math.PI * 2;
      const dist = 90 + Math.random() * 260;
      requestAnimationFrame(() => {
        dot.style.transform =
          "translate(calc(-50% + " + Math.cos(angle) * dist + "px), calc(-50% + " +
          (Math.sin(angle) * dist - 60) + "px)) rotate(" + (Math.random() * 360) + "deg) scale(.6)";
        dot.style.opacity = "0";
      });
    }
    setTimeout(() => layer.remove(), 1200);
  }

  function markAllToday() {
    const planData = plan();
    const date = today();
    const byDisc = new Map();
    for (const t of planData.todayTasks) {
      if (!byDisc.has(t.discId)) byDisc.set(t.discId, []);
      byDisc.get(t.discId).push(t.qIndex);
    }
    for (const [discId, indices] of byDisc) {
      root.Store.setReadMany(discId, indices, date, true);
    }
    root.Sound.play("complete");
    sparkleBurst();
    UI.toast({ kind: "ok", title: "Готово", text: "Сегодняшние вопросы отмечены прочитанными." });
    root.App.refresh();
  }

  function emptyState() {
    const box = h("div.card");
    box.appendChild(
      h("div.empty", [
        h("div.empty-icon", [UI.icon("cloud")]),
        h("h3", "Пока пусто"),
        h("p", "Добавьте файл с вопросами и ответами — TXT, DOCX или PDF. Программа сама найдёт вопросы, посчитает слова и распределит подготовку по дням."),
        h("div.row", [
          UI.button("Добавить файл", { kind: "primary", icon: "plus", onClick: () => root.App.openImport() }),
          UI.button("Как это работает", { kind: "ghost", icon: "info", onClick: () => root.App.go("tips") })
        ])
      ])
    );
    return box;
  }

  // =====================================================================
  //  ДЕНЬ
  // =====================================================================

  let currentDay = null;

  function viewToday(params) {
    const date = (params && params.date) || currentDay || today();
    currentDay = date;
    const planData = plan();
    const wrap = h("div.grid", { style: { gap: "16px" } });

    // Переключатель дня
    const head = h("div.card.tight");
    const nav = h("div.day-nav");
    const prev = h("button.icon-btn", { title: "Предыдущий день", onclick: () => root.App.go("today", { date: P.addDays(date, -1) }) }, [UI.icon("chevronLeft")]);
    const next = h("button.icon-btn", { title: "Следующий день", onclick: () => root.App.go("today", { date: P.addDays(date, 1) }) }, [UI.icon("chevronRight")]);
    const dateLabel = h("div.day-date", UI.dateLong(date));
    const link = date === today()
      ? null
      : h("button.btn.btn-ghost.btn-sm", { onclick: () => root.App.go("today", { date: today() }) }, "вернуться к сегодня");

    nav.appendChild(prev);
    nav.appendChild(h("div", { style: { padding: "0 12px" } }, UI.dateShort(date)));
    nav.appendChild(next);

    head.appendChild(
      h("div.day-head", [
        nav,
        dateLabel,
        link,
        h("div.spacer"),
        UI.button("Экспорт плана", { size: "sm", kind: "ghost", icon: "export", onClick: () => root.App.exportCsv() })
      ])
    );

    // Сводка дня
    const dayMinutes = planData.dayTotals[date] || 0;
    const tasks = groupTodayTasks(planData.todayTasks.filter((t) => date === today())).length
      ? groupTodayTasks(planData.todayTasks)
      : groupTodayTasks((planData.combined[date] || []));
    const doneCount = tasks.filter((t) => {
      const d = root.Store.getDiscipline(t.discId);
      const r = (d && d.reads && d.reads[String(t.qIndex)]) || [];
      return r.indexOf(date) !== -1;
    }).length;

    head.appendChild(
      h("div.day-summary", { style: { marginTop: "14px" } }, [
        h("div.metric", [h("div.value", UI.dur(dayMinutes)), h("div.label", "времени")]),
        h("div.metric", [
          h("div.value", doneCount + " / " + tasks.length),
          h("div.label", "вопросов")
        ]),
        h("div.metric", [
          h("div.value", UI.num(tasks.reduce((s2, t) => {
            const d = root.Store.getDiscipline(t.discId);
            const q = d && d.questions[t.qIndex];
            return s2 + (q ? q.words : 0);
          }, 0))),
          h("div.label", "слов")
        ]),
        h("div.metric", [
          h("div.value", tasks.length ? Math.round((doneCount / tasks.length) * 100) + "%" : "—"),
          h("div.label", "сделано")
        ])
      ])
    );
    wrap.appendChild(head);

    // Список
    const card = h("div.card");
    if (!tasks.length) {
      card.appendChild(
        h("div.empty", [
          h("div.empty-icon", [UI.icon("cloud")]),
          h("h3", "Свободный день"),
          h("p", "На эту дату ничего не запланировано. Можно прочитать что-то из будущих дней — план пересчитается.")
        ])
      );
    } else {
      // Группируем по дисциплинам — так виднее, откуда что.
      const byDisc = new Map();
      for (const t of tasks) {
        if (!byDisc.has(t.discId)) byDisc.set(t.discId, []);
        byDisc.get(t.discId).push(t);
      }
      for (const [discId, list] of byDisc) {
        const d = root.Store.getDiscipline(discId);
        if (!d) continue;
        card.appendChild(
          h("div.row", { style: { margin: "6px 0 10px", gap: "9px" } }, [
            h("span", { style: { width: "8px", height: "8px", borderRadius: "50%", background: accentOf(d) } }),
            h("b", { style: { fontSize: "14px" } }, d.name),
            h("span.muted", { style: { fontSize: "12px" } },
              UI.dur(list.reduce((s2, t) => s2 + t.minutes, 0)))
          ])
        );
        const tl = h("div.task-list", { style: { marginBottom: "14px" } });
        for (const t of list) tl.appendChild(taskRow(t, date));
        card.appendChild(tl);
      }
      card.appendChild(
        h("div.row", { style: { marginTop: "6px" } }, [
          UI.button("Отметить всё", { kind: "primary", icon: "check", onClick: () => markAllOn(date) }),
          h("div.spacer"),
          h("span.muted", { style: { fontSize: "12px" } },
            "Отметки можно снять в любой момент — план пересчитается")
        ])
      );
    }
    wrap.appendChild(card);

    return wrap;
  }

  function markAllOn(date) {
    const planData = plan();
    const items = planData.combined[date] || [];
    const byDisc = new Map();
    for (const t of items) {
      if (!byDisc.has(t.discId)) byDisc.set(t.discId, []);
      byDisc.get(t.discId).push(t.qIndex);
    }
    for (const [discId, indices] of byDisc) root.Store.setReadMany(discId, indices, date, true);
    root.Sound.play("complete");
    sparkleBurst();
    root.App.refresh();
  }

  // =====================================================================
  //  ДИСЦИПЛИНЫ
  // =====================================================================

  function viewDisciplines() {
    const discs = root.Store.activeDisciplines();
    const planData = plan();
    const wrap = h("div.grid", { style: { gap: "14px" } });

    const head = h("div.row", [
      UI.button("Добавить файл", { kind: "primary", icon: "plus", onClick: () => root.App.openImport() }),
      h("div.spacer"),
      h("span.muted", { style: { fontSize: "13px" } },
        discs.length
          ? discs.length + " " + UI.plural(discs.length, "дисциплина", "дисциплины", "дисциплин") +
            " · " + UI.num(planData.totals.questions) + " " + UI.plural(planData.totals.questions, "вопрос", "вопроса", "вопросов")
          : "")
    ]);
    wrap.appendChild(head);

    if (!discs.length) {
      wrap.appendChild(emptyState());
      return wrap;
    }

    const list = h("div.disc-list");
    for (const d of discs) {
      const pd = planData.perDisc[d.id] || { stats: {} };
      const st = pd.stats || {};
      const pct = (st.progress || 0) * 100;
      const card = h("div.disc-card", {
        style: { "--disc-accent": accentOf(d) },
        onclick: () => root.App.go("discipline", { id: d.id })
      }, [
        h("div", { style: { width: "46px", height: "46px", borderRadius: "14px", background: accentOf(d) + "22", display: "grid", placeItems: "center", color: accentOf(d) } }, [UI.icon("book")]),
        h("div", { style: { minWidth: 0 } }, [
          h("div.disc-name", d.name),
          h("div.disc-meta", [
            h("span", [h("b", String(d.questions.length)), " " + UI.plural(d.questions.length, "вопрос", "вопроса", "вопросов")]),
            h("span", [h("b", UI.num(d.questions.reduce((s2, q) => s2 + q.words, 0))), " слов"]),
            h("span", [h("b", UI.dur(st.minutesLeft || 0)), " осталось"]),
            d.plan && P.isValidDate(d.plan.examDate)
              ? h("span", "экзамен " + UI.dateShort(d.plan.examDate) + " (" + UI.relativeDay(d.plan.examDate) + ")")
              : h("span", "дата экзамена не задана"),
            h("span", (d.plan.passes || 1) + " " + UI.plural(d.plan.passes || 1, "прогон", "прогона", "прогонов"))
          ])
        ]),
        h("div.disc-progress", [
          h("div.pct", Math.round(pct) + "%"),
          h("div.mini-bar", { style: { width: "100%" } }, [h("i", { style: { width: pct + "%", background: "linear-gradient(90deg," + accentOf(d) + "," + accentOf(d) + "aa)" } })]),
          h("div.muted", { style: { fontSize: "11px" } },
            st.behind ? "не всё помещается" : st.daysAvailable ? "по плану" : "нет дней")
        ])
      ]);
      list.appendChild(card);
    }
    wrap.appendChild(list);
    UI.stagger(list, 40);
    return wrap;
  }

  // =====================================================================
  //  ОДНА ДИСЦИПЛИНА
  // =====================================================================

  let discTab = "plan";
  let discFilter = "";

  function viewDiscipline(params) {
    const id = (params && params.id) || state().ui.selectedDiscipline;
    const d = id ? root.Store.getDiscipline(id) : null;
    if (!d) {
      return h("div.card", [
        h("div.empty", [
          h("div.empty-icon", [UI.icon("book")]),
          h("h3", "Дисциплина не выбрана"),
          h("p", "Выберите дисциплину в списке."),
          UI.button("К дисциплинам", { kind: "primary", onClick: () => root.App.go("disciplines") })
        ])
      ]);
    }
    state().ui.selectedDiscipline = id;
    const planData = plan();
    const pd = planData.perDisc[d.id] || { stats: {}, days: {}, warnings: [] };
    const st = pd.stats || {};
    const wrap = h("div.grid", { style: { gap: "16px" } });

    // --- Шапка --------------------------------------------------------
    const head = h("div.card");
    head.appendChild(
      h("div.disc-head", [
        h("div.disc-head-main", [
          h("div.row", { style: { gap: "8px", marginBottom: "6px" } }, [
            h("span.tag", { style: { background: accentOf(d) + "22", color: accentOf(d) } },
              (d.parsing && strategyName(d.parsing.strategy)) || "файл"),
            d.fileName ? h("span.muted", { style: { fontSize: "11.5px" } }, d.fileName) : null
          ]),
          h("h2", d.name),
          h("div.disc-meta", { style: { marginTop: "8px" } }, [
            h("span", [h("b", String(d.questions.length)), " " + UI.plural(d.questions.length, "вопрос", "вопроса", "вопросов")]),
            h("span", [h("b", UI.num(d.questions.reduce((s2, q) => s2 + q.words, 0))), " слов"]),
            h("span", [h("b", UI.num(d.questions.reduce((s2, q) => s2 + q.chars, 0))), " знаков"]),
            h("span", [h("b", UI.dur(P.totalMinutes(d, settings()))), " всего на " + (d.plan.passes || 1) + " " + UI.plural(d.plan.passes || 1, "прогон", "прогона", "прогонов")]),
            h("span", [h("b", UI.dur(st.minutesLeft || 0)), " осталось"])
          ])
        ]),
        h("div.row", { style: { gap: "8px" } }, [
          UI.button("Читать сегодняшнее", {
            kind: "primary",
            icon: "play",
            onClick: () => {
              const dayTasks = (planData.combined[today()] || []).filter((t) => t.discId === d.id);
              if (dayTasks.length) root.App.openQuestion(d.id, dayTasks[0].qIndex, today());
              else UI.toast({ kind: "info", text: "На сегодня по этой дисциплине ничего нет." });
            }
          }),
          h("button.icon-btn", { title: "Переименовать", onclick: () => renameDiscipline(d) }, [UI.icon("edit")]),
          h("button.icon-btn", { title: "Удалить", onclick: () => confirmDelete(d) }, [UI.icon("trash")])
        ])
      ])
    );

    // Полоса прогресса + кольцо
    const ringEl = UI.ring((st.progress || 0) * 100, { size: 108, stroke: 10, label: "пройдено" });
    head.appendChild(
      h("div", { style: { display: "grid", gridTemplateColumns: "auto 1fr", gap: "22px", alignItems: "center", marginTop: "18px" } }, [
        ringEl,
        h("div.grid.cols-4", { style: { gap: "12px" } }, [
          metricTile("прочитано", Math.round((st.passesDone / Math.max(1, st.passesTotal)) * 100) + "%",
            (st.passesDone || 0) + " из " + (st.passesTotal || 0) + " " + UI.plural(st.passesTotal || 0, "прочтения", "прочтений", "прочтений")),
          metricTile("в день", UI.dur(st.perDayMinutes || 0), daysWord(st.daysAvailable || 0)),
          metricTile("пик", UI.dur(st.peakMinutes || 0), st.peakDay ? UI.dateShort(st.peakDay) : "—"),
          metricTile("финиш", st.finishDate ? UI.dateShort(st.finishDate) : "—",
            st.finishDate ? UI.relativeDay(st.finishDate) : "нет плана")
        ])
      ])
    );

    // Предупреждения дисциплины
    if (pd.warnings && pd.warnings.length) {
      const w = h("div", { style: { display: "grid", gap: "8px", marginTop: "14px" } });
      for (const warn of pd.warnings) {
        w.appendChild(h("div.warn-box" + (warn.type === "behind" || warn.type === "exam-passed" ? ".error" : ""), [
          UI.icon(warn.type === "behind" || warn.type === "exam-passed" ? "warn" : "info"),
          h("span", warn.text)
        ]));
      }
      head.appendChild(w);
    }
    wrap.appendChild(head);

    // --- Вкладки ------------------------------------------------------
    const tabs = [
      ["plan", "План"],
      ["questions", "Вопросы"],
      ["schedule", "Расписание"],
      ["settings", "Параметры"]
    ];
    const tabsEl = h("div.tabs");
    for (const [key, label] of tabs) {
      tabsEl.appendChild(
        h("button.tab" + (discTab === key ? ".on" : ""), {
          onclick: () => {
            discTab = key;
            root.Sound.play("page");
            root.App.refresh();
          }
        }, label)
      );
    }
    wrap.appendChild(tabsEl);

    if (discTab === "plan") wrap.appendChild(discPlanTab(d, pd));
    else if (discTab === "questions") wrap.appendChild(discQuestionsTab(d, pd));
    else if (discTab === "schedule") wrap.appendChild(discScheduleTab(d, pd));
    else wrap.appendChild(discSettingsTab(d, pd));

    return wrap;
  }

  function metricTile(label, value, sub) {
    return h("div.stat-tile", [
      h("div.section-label", label),
      h("div", { style: { fontFamily: "var(--font-display)", fontSize: "24px", fontWeight: "600", lineHeight: "1.15", marginTop: "3px" } }, value),
      h("div.muted", { style: { fontSize: "11.5px" } }, sub)
    ]);
  }

  function daysWord(n) {
    return n + " " + UI.plural(n, "день", "дня", "дней") + " до экзамена";
  }

  function strategyName(s) {
    const map = {
      "markdown-headings": "заголовки «Вопрос N»",
      "question-headings": "заголовки вопросов",
      "single-question-file": "файл на один вопрос",
      "list-and-answers": "перечень + ответы",
      "numbered-list": "нумерованный список",
      "numbered-with-answers": "нумерация с «Ответ:»",
      "question-lines": "строки-вопросы",
      "whole-document": "один вопрос целиком",
      paragraphs: "абзацы",
      empty: "пусто"
    };
    return map[s] || "распознано";
  }

  /** Вкладка «План»: что читать в ближайшие дни + нагрузка. */
  function discPlanTab(d, pd) {
    const box = h("div.grid", { style: { gap: "16px" } });

    // Гистограмма нагрузки
    const loadCard = h("div.card");
    loadCard.appendChild(
      h("div.card-title", [
        h("h2", "Нагрузка по дням"),
        h("div.row", [
          h("span.tag.new", "новое"),
          h("span.tag.repeat", "повтор"),
          h("span.muted", { style: { fontSize: "11.5px" } }, "мин/день")
        ])
      ])
    );
    const days = Object.keys(pd.days || {}).sort();
    const vals = days.map((day) => (pd.days[day] || []).reduce((s2, it) => s2 + it.minutes, 0));
    if (vals.length) {
      const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
      loadCard.appendChild(
        UI.sparkline(vals, {
          labels: days.map((x) => UI.dateShort(x)),
          todayIndex: days.indexOf(today()),
          over: avg * 1.6,
          title: "Средняя нагрузка " + UI.dur(avg) + " в день"
        })
      );
      loadCard.appendChild(
        h("div.row", { style: { marginTop: "10px", justifyContent: "space-between" } }, [
          h("span.muted", { style: { fontSize: "11.5px" } }, UI.dateShort(days[0])),
          h("span.muted", { style: { fontSize: "11.5px" } }, "в среднем " + UI.dur(avg)),
          h("span.muted", { style: { fontSize: "11.5px" } }, UI.dateShort(days[days.length - 1]))
        ])
      );
    } else {
      loadCard.appendChild(h("p.muted", "План не построен — проверьте даты и число прогонов."));
    }
    box.appendChild(loadCard);

    // Ближайшие дни этой дисциплины
    const upcoming = h("div.card");
    upcoming.appendChild(h("div.card-title", [h("h2", "Ближайшие дни")]));
    const rows = h("div", { style: { display: "grid", gap: "8px" } });
    const future = days.filter((day) => day >= today() && (pd.days[day] || []).length).slice(0, 7);
    if (!future.length) rows.appendChild(h("p.muted", "Работа не запланирована."));
    for (const day of future) {
      const items = pd.days[day];
      const minutes = items.reduce((s2, it) => s2 + it.minutes, 0);
      const news = items.filter((i) => i.kind === "new").length;
      rows.appendChild(
        h("div.row", {
          style: { padding: "10px 12px", borderRadius: "12px", background: "rgba(255,255,255,.4)", cursor: "pointer" },
          onclick: () => root.App.go("today", { date: day })
        }, [
          h("div", { style: { minWidth: "96px" } }, [
            h("div", { style: { fontWeight: "700", fontSize: "13px" } }, UI.dateShort(day)),
            h("div.muted", { style: { fontSize: "11px" } }, UI.weekDayShort(day) + " · " + UI.relativeDay(day))
          ]),
          h("div", { style: { display: "flex", gap: "5px", flexWrap: "wrap", flex: "1 1 auto" } },
            items.slice(0, 8).map((it) =>
              h("span.tag" + (it.kind === "new" ? ".new" : ".repeat"), "№" + (d.questions[it.qIndex] ? d.questions[it.qIndex].num : it.qIndex + 1))
            ).concat(items.length > 8 ? [h("span.tag", "+" + (items.length - 8))] : [])
          ),
          h("div", { style: { textAlign: "right", minWidth: "78px" } }, [
            h("div", { style: { fontWeight: "700", fontSize: "13px" } }, UI.dur(minutes)),
            h("div.muted", { style: { fontSize: "11px" } }, news ? news + " новых" : "повторение")
          ])
        ])
      );
    }
    upcoming.appendChild(rows);
    box.appendChild(upcoming);

    return box;
  }

  /** Вкладка «Вопросы»: таблица с прогрессом, поиском и открытием ответа. */
  function discQuestionsTab(d, pd) {
    const box = h("div.card");

    const search = h("input.input", {
      type: "search",
      placeholder: "Поиск по вопросам…",
      value: discFilter,
      style: { maxWidth: "320px" },
      oninput: (e) => {
        discFilter = e.target.value;
        renderRows();
      }
    });

    box.appendChild(
      h("div.card-title", [
        h("h2", "Вопросы"),
        h("div.row", [search, UI.button("Отметки за сегодня", {
          size: "sm",
          kind: "ghost",
          icon: "check",
          onClick: () => {
            root.App.go("today");
          }
        })])
      ])
    );

    const table = h("div.q-table");
    const settingsNow = settings();

    function renderRows() {
      UI.clear(table);
      const q = discFilter.trim().toLowerCase();
      let shown = 0;
      d.questions.forEach((question, idx) => {
        if (q && question.title.toLowerCase().indexOf(q) === -1 &&
            String(question.num).indexOf(q) === -1) return;
        shown++;
        const stq = P.questionState(d, idx, settingsNow);
        const complete = stq.done >= stq.passes;
        const row = h("div.q-row" + (complete ? ".complete" : ""), {
          onclick: () => root.App.openQuestion(d.id, idx, today())
        }, [
          h("div.q-num", String(question.num)),
          h("div.q-name", { title: question.title }, question.title),
          h("div.q-vol", UI.dur(P.questionTotalMinutes(d, question, settingsNow))),
          h("div.pips", Array.from({ length: stq.passes }, (_, i) =>
            h("i.pip" + (i < stq.done ? ".on" : ""), { title: "прочтение " + (i + 1) + (stq.reads[i] ? ": " + UI.dateShort(stq.reads[i]) : "") })
          ))
        ]);
        table.appendChild(row);
      });
      if (!shown) table.appendChild(h("p.muted", { style: { padding: "16px" } }, "Ничего не найдено."));
    }
    renderRows();
    box.appendChild(table);
    box.appendChild(
      h("div.row", { style: { marginTop: "10px" } }, [
        h("span.muted", { style: { fontSize: "11.5px" } }, "Щёлкните по вопросу, чтобы прочитать ответ и отметить прочтение.")
      ])
    );
    return box;
  }

  /** Вкладка «Расписание»: календарь этой дисциплины. */
  function discScheduleTab(d, pd) {
    const box = h("div.card");
    const month = state().ui.calendarMonth || today().slice(0, 7);
    box.appendChild(
      h("div.card-title", [
        h("h2", "Расписание"),
        h("div.row", [
          h("button.icon-btn", {
            title: "Предыдущий месяц",
            onclick: () => {
              state().ui.calendarMonth = shiftMonth(month, -1);
              root.App.refresh();
            }
          }, [UI.icon("chevronLeft")]),
          h("b", { style: { minWidth: "140px", textAlign: "center" } }, monthName(month)),
          h("button.icon-btn", {
            title: "Следующий месяц",
            onclick: () => {
              state().ui.calendarMonth = shiftMonth(month, 1);
              root.App.refresh();
            }
          }, [UI.icon("chevronRight")])
        ])
      ])
    );
    box.appendChild(monthGrid(month, (day) => {
      const items = (pd.days || {})[day] || [];
      return {
        minutes: items.reduce((s2, it) => s2 + it.minutes, 0),
        count: items.length,
        isExam: day === d.plan.examDate,
        onClick: () => root.App.go("today", { date: day })
      };
    }));
    return box;
  }

  /** Вкладка «Параметры»: сроки, прогоны, режим, скорость. */
  function discSettingsTab(d, pd) {
    const box = h("div.card");
    box.appendChild(h("div.card-title", [h("h2", "Параметры дисциплины")]));

    const grid = h("div.plan-grid");

    // Название
    grid.appendChild(planField("Название", h("input.input", {
      value: d.name,
      onchange: (e) => {
        d.name = e.target.value.trim() || d.name;
        root.Store.save();
        root.App.refresh();
      }
    })));

    // Дата начала
    grid.appendChild(planField("Начать с", h("input.input", {
      type: "date",
      value: d.plan.startDate,
      onchange: (e) => updatePlan(d, { startDate: e.target.value })
    }), "можно поставить будущую дату"));

    // Дата экзамена
    grid.appendChild(planField("Экзамен / зачёт", h("input.input", {
      type: "date",
      value: d.plan.examDate,
      onchange: (e) => updatePlan(d, { examDate: e.target.value })
    }), examHint(d)));

    // Прогоны
    grid.appendChild(
      planField(
        "Сколько раз прочитать",
        UI.stepper(d.plan.passes, {
          min: 1,
          max: 12,
          onChange: (v) => updatePlan(d, { passes: v })
        }),
        "повторения идут с растущими промежутками"
      )
    );

    // Режим нагрузки
    const modeSeg = h("div.segmented");
    const modes = [
      ["even", "равномерно"],
      ["questions", "по вопросам"],
      ["minutes", "по минутам"]
    ];
    for (const [key, label] of modes) {
      modeSeg.appendChild(
        h("button" + (d.plan.mode === key ? ".on" : ""), {
          onclick: () => {
            updatePlan(d, { mode: key });
          }
        }, label)
      );
    }
    grid.appendChild(planField("Как распределять", modeSeg,
      d.plan.mode === "even"
        ? "движок делит остаток на оставшиеся дни и выравнивает нагрузку"
        : d.plan.mode === "questions"
          ? "фиксированное число новых вопросов в день"
          : "фиксированное число минут в день"));

    if (d.plan.mode === "questions") {
      grid.appendChild(
        planField("Вопросов в день", UI.stepper(d.plan.perDayQuestions, {
          min: 1,
          max: 200,
          onChange: (v) => updatePlan(d, { perDayQuestions: v })
        }), "новых вопросов, повторения добавляются сами")
      );
    }
    if (d.plan.mode === "minutes") {
      grid.appendChild(
        planField("Минут в день", UI.stepper(d.plan.perDayMinutes, {
          min: 5,
          max: 600,
          step: 5,
          onChange: (v) => updatePlan(d, { perDayMinutes: v })
        }), "включая повторения")
      );
    }

    // Выходные
    const chips = h("div.chips");
    const wd = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"];
    // В плане дни — как getDay(): 0 = воскресенье.
    const order = [1, 2, 3, 4, 5, 6, 0];
    order.forEach((dayNum, i) => {
      const on = (d.plan.restDays || []).indexOf(dayNum) !== -1;
      chips.appendChild(
        h("button.chip" + (on ? ".on.rest" : ""), {
          onclick: () => {
            const rest = (d.plan.restDays || []).slice();
            const at = rest.indexOf(dayNum);
            if (at >= 0) rest.splice(at, 1);
            else rest.push(dayNum);
            updatePlan(d, { restDays: rest });
          }
        }, wd[i])
      );
    });
    grid.appendChild(planField("Выходные (без чтения)", chips, "в эти дни нагрузка не ставится"));

    // Порядок
    const orderSeg = h("div.segmented");
    [["inOrder", "по порядку"], ["mixed", "вперемешку"]].forEach(([key, label]) => {
      orderSeg.appendChild(
        h("button" + (d.plan.order === key ? ".on" : ""), {
          onclick: () => updatePlan(d, { order: key })
        }, label)
      );
    });
    grid.appendChild(planField("Порядок вопросов", orderSeg,
      d.plan.order === "mixed"
        ? "вопросы перемешаны — помогает не привязываться к порядку файла"
        : "как в файле — проще находить ответ"));

    // Оценка объёма: нужна, когда в файле только вопросы без ответов.
    const estimatedCount = d.questions.filter((q) => q.estimated).length;
    if (estimatedCount > 0) {
      grid.appendChild(
        planField(
          "Объём ответа (оценка)",
          UI.stepper(d.assumeAnswerWords || 250, {
            min: 30,
            max: 1500,
            step: 10,
            onChange: (v) => {
              d.assumeAnswerWords = v;
              reestimateAnswers(d, v);
            }
          }),
          "для " + estimatedCount + " " + UI.plural(estimatedCount, "вопроса", "вопросов", "вопросов") +
            " без ответа — столько слов считается на каждый"
        )
      );
    }

    box.appendChild(grid);

    // Предпросмотр результата
    box.appendChild(
      h("div", { style: { marginTop: "18px", padding: "14px 16px", borderRadius: "14px", background: "rgba(255,255,255,.42)" } }, [
        h("div.section-label", "что получится"),
        h("div", { style: { display: "grid", gap: "6px", marginTop: "8px", fontSize: "13.5px" } }, [
          rowKV("Всего чтения", UI.durLong(P.totalMinutes(d, settings()))),
          rowKV("Осталось", UI.durLong(P.remainingMinutes(d, settings()))),
          rowKV("Дней до экзамена", daysWord(Math.max(0, P.daysBetween(today(), d.plan.examDate)))),
          rowKV("В среднем в день", UI.dur(pd.stats.perDayMinutes || 0))
        ])
      ])
    );

    // Опасная зона
    box.appendChild(
      h("div.row", { style: { marginTop: "18px" } }, [
        UI.button("Сбросить отметки", {
          kind: "ghost",
          onClick: () => {
            if (!confirm("Снять все отметки о прочтении по дисциплине «" + d.name + "»? Настройки плана сохранятся.")) return;
            d.reads = {};
            root.Store.save();
            root.Sound.play("uncheck");
            root.App.refresh();
          }
        }),
        h("div.spacer"),
        UI.button("Удалить дисциплину", {
          kind: "ghost",
          onClick: () => confirmDelete(d)
        })
      ])
    );

    return box;
  }

  /**
   * Меняет оценку объёма для вопросов без ответа и пересчитывает статистику.
   * Вопросы с настоящим ответом не трогаем.
   */
  function reestimateAnswers(d, words) {
    const t = root.ExamCore.text;
    for (const q of d.questions) {
      if (!q.estimated) continue;
      const sample = new Array(words + 1).join("слово ");
      const aStat = t.analyze(sample.trim(), "wpm", 1);
      q.aWords = aStat.words;
      q.aChars = aStat.chars;
      q.charsWithSpaces = q.qChars + aStat.charsWithSpaces;
      q.words = q.qWords + aStat.words;
      q.chars = q.qChars + aStat.chars;
      q.difficulty = t.difficultyIndex(q.question + " " + sample);
    }
    root.Store.save();
    root.Sound.play("tap");
    root.App.refresh();
  }

  function planField(label, control, hint) {
    return h("div.plan-field", [
      h("div.field-label", label),
      control,
      hint ? h("div.muted", { style: { fontSize: "11.5px", lineHeight: "1.4", marginTop: "-2px" } }, hint) : null
    ]);
  }

  function rowKV(k, v) {
    return h("div.row", { style: { justifyContent: "space-between" } }, [
      h("span.muted", k),
      h("b", v)
    ]);
  }

  function examHint(d) {
    if (!P.isValidDate(d.plan.examDate)) return "укажите дату";
    const days = P.daysBetween(today(), d.plan.examDate);
    if (days < 0) return "дата уже прошла";
    if (days === 0) return "экзамен сегодня";
    return "через " + days + " " + UI.plural(days, "день", "дня", "дней");
  }

  function updatePlan(d, patch) {
    Object.assign(d.plan, patch);
    root.Store.save();
    root.App.refresh();
  }

  // =====================================================================
  //  КАЛЕНДАРЬ
  // =====================================================================

  function viewCalendar() {
    const planData = plan();
    const month = state().ui.calendarMonth || today().slice(0, 7);
    const wrap = h("div.grid", { style: { gap: "16px" } });
    const card = h("div.card");
    card.appendChild(
      h("div.card-title", [
        h("div", [
          h("h2", monthName(month)),
          h("div.muted", { style: { fontSize: "12px" } }, calendarSummary(planData, month))
        ]),
        h("div.row", [
          h("button.icon-btn", {
            title: "Предыдущий месяц",
            onclick: () => {
              state().ui.calendarMonth = shiftMonth(month, -1);
              root.App.refresh();
            }
          }, [UI.icon("chevronLeft")]),
          UI.button("Сегодня", {
            size: "sm",
            kind: "ghost",
            onClick: () => {
              state().ui.calendarMonth = today().slice(0, 7);
              root.App.go("today");
            }
          }),
          h("button.icon-btn", {
            title: "Следующий месяц",
            onclick: () => {
              state().ui.calendarMonth = shiftMonth(month, 1);
              root.App.refresh();
            }
          }, [UI.icon("chevronRight")])
        ])
      ])
    );

    const examDays = new Set();
    for (const d of root.Store.activeDisciplines()) {
      if (P.isValidDate(d.plan.examDate)) examDays.add(d.plan.examDate);
    }
    card.appendChild(
      monthGrid(month, (day) => {
        const minutes = planData.dayTotals[day] || 0;
        const done = isDayFullyDone(day);
        return {
          minutes: minutes,
          count: (planData.combined[day] || []).length,
          isExam: examDays.has(day),
          done: done,
          onClick: () => root.App.go("today", { date: day })
        };
      })
    );
    wrap.appendChild(card);

    // Легенда
    wrap.appendChild(
      h("div.card.tight", [
        h("div.row.wrap", { style: { gap: "18px" } }, [
          legendItem("var(--accent)", "нагрузка"),
          legendItem("var(--mint)", "всё отмечено"),
          legendItem("var(--rose)", "экзамен"),
          h("span.muted", { style: { fontSize: "12px" } }, "Высота полоски — доля от самого тяжёлого дня месяца")
        ])
      ])
    );
    return wrap;
  }

  function legendItem(color, label) {
    return h("div.row", { style: { gap: "6px" } }, [
      h("span", { style: { width: "9px", height: "9px", borderRadius: "50%", background: color } }),
      h("span", { style: { fontSize: "12.5px", color: "var(--ink-soft)" } }, label)
    ]);
  }

  function isDayFullyDone(day) {
    if (day > today()) return false;
    const planData = plan();
    const items = planData.combined[day] || [];
    if (!items.length) return false;
    const seen = new Set();
    for (const t of items) {
      const key = t.discId + ":" + t.qIndex;
      if (seen.has(key)) continue;
      seen.add(key);
      const d = root.Store.getDiscipline(t.discId);
      const reads = (d && d.reads && d.reads[String(t.qIndex)]) || [];
      if (reads.indexOf(day) === -1) return false;
    }
    return true;
  }

  function monthName(month) {
    const [y, m] = month.split("-").map(Number);
    return UI.MONTHS_NOM[m - 1] + " " + y;
  }

  function shiftMonth(month, delta) {
    const [y, m] = month.split("-").map(Number);
    const d = new Date(y, m - 1 + delta, 1);
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0");
  }

  /** Сетка месяца: 7 колонок, первая — понедельник. */
  function monthGrid(month, describe) {
    const [y, m] = month.split("-").map(Number);
    const first = new Date(y, m - 1, 1);
    const daysInMonth = new Date(y, m, 0).getDate();
    const startOffset = (first.getDay() + 6) % 7;

    const grid = h("div.calendar");
    for (const wd of ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]) {
      grid.appendChild(h("div.cal-head", wd));
    }
    for (let i = 0; i < startOffset; i++) grid.appendChild(h("div.cal-day.empty"));

    // Максимум месяца — для относительной высоты полоски.
    let maxMin = 1;
    for (let day = 1; day <= daysInMonth; day++) {
      const iso = y + "-" + String(m).padStart(2, "0") + "-" + String(day).padStart(2, "0");
      const info = describe(iso);
      if (info.minutes > maxMin) maxMin = info.minutes;
    }

    for (let day = 1; day <= daysInMonth; day++) {
      const iso = y + "-" + String(m).padStart(2, "0") + "-" + String(day).padStart(2, "0");
      const info = describe(iso);
      const classes = ["cal-day"];
      if (iso === today()) classes.push("today");
      if (iso < today()) classes.push("past");
      if (info.isExam) classes.push("exam");
      const cell = h("div", { class: classes.join(" "), title: UI.dateLong(iso) + (info.minutes ? " · " + UI.dur(info.minutes) : "") });
      cell.appendChild(h("div.cal-num", String(day)));
      if (info.done) cell.appendChild(h("i.cal-dot"));
      if (info.minutes > 0) {
        cell.appendChild(
          h("div.cal-load", [
            h("div.cal-bar", [h("i", { style: { width: Math.max(8, (info.minutes / maxMin) * 100) + "%" } })]),
            h("div.cal-min", UI.dur(info.minutes))
          ])
        );
      }
      if (info.onClick) cell.addEventListener("click", info.onClick);
      grid.appendChild(cell);
    }
    return grid;
  }

  function calendarSummary(planData, month) {
    let total = 0;
    let days = 0;
    for (const [date, min] of Object.entries(planData.dayTotals)) {
      if (date.slice(0, 7) === month) {
        total += min;
        if (min > 0) days++;
      }
    }
    if (!days) return "в этом месяце работы нет";
    return days + " " + UI.plural(days, "день", "дня", "дней") + " с чтением · " + UI.dur(total) + " всего · " + UI.dur(total / days) + " в среднем";
  }

  // =====================================================================
  //  СТАТИСТИКА
  // =====================================================================

  function viewStats() {
    const planData = plan();
    const discs = root.Store.activeDisciplines();
    const wrap = h("div.grid", { style: { gap: "16px" } });

    if (!discs.length) {
      wrap.appendChild(emptyState());
      return wrap;
    }

    const totals = planData.totals;
    const words = totals.words;
    const chars = totals.chars;
    const spm = settings().wordsPerMinute || 150;

    // Верхние метрики
    const tiles = h("div.grid.cols-4");
    tiles.appendChild(statTile("вопросов", UI.num(totals.questions), discs.length + " " + UI.plural(discs.length, "дисциплина", "дисциплины", "дисциплин")));
    tiles.appendChild(statTile("слов", UI.num(words), "≈ " + UI.num(Math.round(words / Math.max(1, totals.questions))) + " на вопрос"));
    tiles.appendChild(statTile("знаков", UI.num(chars), "без пробелов"));
    tiles.appendChild(statTile("время", UI.durLong(totals.minutesTotal), Math.round(totals.minutesTotal / 60) + " " + UI.plural(Math.round(totals.minutesTotal / 60), "час", "часа", "часов") + " чтения"));
    wrap.appendChild(tiles);

    // Прогресс по дисциплинам
    const card = h("div.card");
    card.appendChild(h("div.card-title", [h("h2", "Прогресс по дисциплинам")]));
    const list = h("div", { style: { display: "grid", gap: "13px" } });
    for (const d of discs) {
      const pd = planData.perDisc[d.id] || { stats: {} };
      const st = pd.stats || {};
      const pct = (st.progress || 0) * 100;
      list.appendChild(
        h("div", [
          h("div.row", { style: { justifyContent: "space-between", marginBottom: "5px" } }, [
            h("span", { style: { fontWeight: "600", fontSize: "13.5px" } }, d.name),
            h("span.mono", { style: { fontSize: "12px", color: "var(--ink-faint)" } },
              UI.dur(st.minutesDone || 0) + " / " + UI.dur(st.minutesTotal || 0))
          ]),
          h("div.mini-bar", [h("i", { style: { width: pct + "%", background: "linear-gradient(90deg," + accentOf(d) + "," + accentOf(d) + "aa)" } })])
        ])
      );
    }
    card.appendChild(list);
    wrap.appendChild(card);

    // Активность: последние 30 дней
    const activity = h("div.card");
    const streak = state().stats.streak || 0;
    activity.appendChild(
      h("div.card-title", [
        h("h2", "Активность"),
        h("div.row", [
          UI.icon("flame"),
          h("b", { style: { fontSize: "14px" } }, streak + " " + UI.plural(streak, "день", "дня", "дней") + " подряд")
        ])
      ])
    );
    activity.appendChild(activityGrid());
    wrap.appendChild(activity);

    // Скорость чтения — что это значит
    const speed = h("div.card");
    speed.appendChild(h("div.card-title", [h("h2", "Что значит ваша скорость")]));
    speed.appendChild(
      h("div.grid.cols-3", { style: { gap: "12px" } }, [
        metricTile("скорость", spm + " слов/мин", settings().unit === "cpm" ? "сейчас в знаках/мин" : "текущая настройка"),
        metricTile("на один ответ", UI.dur(medianAnswerMinutes(discs)), "средний вопрос"),
        metricTile("прогонов", String(totals.passesTotal), "с учётом повторений")
      ])
    );
    speed.appendChild(
      h("p.muted", { style: { fontSize: "12.5px", marginTop: "12px" } },
        "Для учебного юридического текста обычная скорость — 120–180 слов в минуту; вслух — 100–130. " +
        "Если на деле выходит медленнее, поставьте меньшее число в настройках: план станет точнее.")
    );
    wrap.appendChild(speed);

    // Распределение нагрузки
    const dist = h("div.card");
    dist.appendChild(h("div.card-title", [h("h2", "Распределение нагрузки")]));
    const dayVals = Object.keys(planData.dayTotals).sort().map((d) => planData.dayTotals[d]);
    if (dayVals.length) {
      dist.appendChild(UI.sparkline(dayVals, { todayIndex: -1, over: average(dayVals) * 1.6 }));
      dist.appendChild(
        h("div.row", { style: { justifyContent: "space-between", marginTop: "8px" } }, [
          h("span.muted", { style: { fontSize: "11.5px" } }, "самый лёгкий: " + UI.dur(Math.min.apply(null, dayVals))),
          h("span.muted", { style: { fontSize: "11.5px" } }, "в среднем: " + UI.dur(average(dayVals))),
          h("span.muted", { style: { fontSize: "11.5px" } }, "самый тяжёлый: " + UI.dur(Math.max.apply(null, dayVals)))
        ])
      );
    } else {
      dist.appendChild(h("p.muted", "Пока нет запланированных дней."));
    }
    wrap.appendChild(dist);

    return wrap;
  }

  function statTile(label, value, sub) {
    return h("div.card.tight", [
      h("div.section-label", label),
      h("div", { style: { fontFamily: "var(--font-display)", fontSize: "31px", fontWeight: "600", lineHeight: "1.1", marginTop: "3px" } }, value),
      h("div.muted", { style: { fontSize: "11.5px" } }, sub)
    ]);
  }

  function average(arr) {
    if (!arr.length) return 0;
    return arr.reduce((a, b) => a + b, 0) / arr.length;
  }

  function medianAnswerMinutes(discs) {
    const all = [];
    for (const d of discs) {
      for (const q of d.questions || []) all.push(P.questionTotalMinutes(d, q, settings()));
    }
    if (!all.length) return 0;
    all.sort((a, b) => a - b);
    return all[Math.floor(all.length / 2)];
  }

  /** Сетка «тепловая карта» активности за 8 недель. */
  function activityGrid() {
    const days = new Set(state().stats.daysActive || []);
    const wrap = h("div", { style: { display: "grid", gridTemplateColumns: "repeat(8, 1fr)", gap: "9px" } });
    const end = today();
    for (let w = 7; w >= 0; w--) {
      const col = h("div", { style: { display: "grid", gap: "3px" } });
      col.appendChild(h("div.muted", { style: { fontSize: "9.5px", textAlign: "center", marginBottom: "2px" } },
        UI.dateShort(P.addDays(end, -w * 7 - 6)).split(" ")[1]));
      for (let i = 0; i < 7; i++) {
        const day = P.addDays(end, -(w * 7 + (6 - i)));
        const isToday = day === end;
        const active = days.has(day);
        col.appendChild(
          h("div", {
            title: UI.dateLong(day) + (active ? " · есть отметки" : ""),
            style: {
              height: "13px",
              borderRadius: "3.5px",
              background: active ? "linear-gradient(140deg, var(--mint), #2f9578)" : "rgba(24,58,92,.1)",
              outline: isToday ? "1.5px solid var(--accent)" : "none",
              outlineOffset: "1px",
              transition: "background .3s"
            }
          })
        );
      }
      wrap.appendChild(col);
    }
    return h("div", { style: { display: "grid", gap: "8px" } }, [
      wrap,
      h("div.row", { style: { justifyContent: "space-between" } }, [
        h("span.muted", { style: { fontSize: "11px" } }, "8 недель назад"),
        h("span.muted", { style: { fontSize: "11px" } }, "сегодня")
      ])
    ]);
  }

  // =====================================================================
  //  СОВЕТЫ
  // =====================================================================

  function viewTips() {
    const wrap = h("div.grid", { style: { gap: "16px" } });
    const intro = h("div.card");
    intro.appendChild(
      h("div", [
        h("h2", { style: { fontFamily: "var(--font-display)", fontSize: "27px", fontWeight: "600", marginBottom: "8px" } },
          "Как готовиться, чтобы действительно запомнить"),
        h("p.soft", { style: { fontSize: "14.5px", lineHeight: "1.65", maxWidth: "78ch" } },
          "Программа считает время и раскладывает работу — но запоминание зависит от того, что вы делаете " +
          "с текстом. Ниже — приёмы, которые в исследованиях дают наибольший эффект, и то, как они уже учтены в плане.")
      ])
    );
    wrap.appendChild(intro);

    const tips = [
      {
        title: "Повторять, а не перечитывать",
        text:
          "После первого чтения закройте ответ и попробуйте пересказать его вслух или записать ключевые пункты. " +
          "Проверка себя даёт заметно больше, чем повторное чтение того же текста: в опытах Рёдигера и Карпике " +
          "через неделю вспоминалось 61 % материала против 40 % у тех, кто читал четыре раза.",
        src: "Roediger & Karpicke, Psychological Science, 2006",
        link: "https://doi.org/10.1111/j.1467-9280.2006.01693.x",
        used: "Поэтому план ставит повторные чтения отдельными пунктами через дни, а не подряд."
      },
      {
        title: "Распределять по дням, а не учить за ночь",
        text:
          "Распределённая практика — один из двух приёмов, которые обзор десяти популярных стратегий признал " +
          "высокоэффективными. Один и тот же объём, разложенный на много дней, запоминается прочнее, чем собранный в один блок.",
        src: "Dunlosky et al., Psychological Science in the Public Interest, 2013",
        link: "https://doi.org/10.1177/1529100612453266",
        used: "Отсюда само устройство плана: работа делится на дни до экзамена, а не копится к концу."
      },
      {
        title: "Промежутки между повторениями растут",
        text:
          "Оптимальный первый промежуток — примерно 10–20 % от срока до контроля; дальше интервалы расширяются. " +
          "Для экзамена через месяц это значит: первое повторение через 3–6 дней, затем реже.",
        src: "Cepeda et al., Psychological Bulletin, 2006; Psychological Science, 2008",
        link: "https://doi.org/10.1037/0033-2909.132.3.354",
        used: "Параметр «интервал повторений» в настройках задаёт эту долю; по умолчанию 15 %."
      },
      {
        title: "Чередовать дисциплины",
        text:
          "Смена предмета в течение дня даёт умеренный, но устойчивый выигрыш по сравнению с блоками " +
          "«один предмет за один день»: мозг каждый раз заново поднимает нужный контекст.",
        src: "Brunmair & Richter, Psychological Bulletin, 2019",
        link: "https://doi.org/10.1037/bul0000198",
        used: "Поэтому в обзоре видно работу по всем дисциплинам каждый день, а не по одной подряд."
      },
      {
        title: "Сначала понять, потом зубрить",
        text:
          "Юридический ответ держится на структуре: определение, правовая основа, состав, порядок действий. " +
          "Если сначала разобрать схему ответа, детали ложатся на неё, и пересказ получается связным.",
        src: "практика подготовки к экзаменам по праву",
        used: "При просмотре вопроса видно объём ответа и число прочтений — планируйте на сложные больше времени."
      },
      {
        title: "Проверять себя по номерам вопросов",
        text:
          "Полезно не только читать, но и проверять: по номеру вопроса вспомнить, о чём он. " +
          "Если не выходит — этот вопрос и есть слабое место, его стоит перечитать раньше остальных.",
        src: "практика активного припоминания",
        used: "На вкладке «Вопросы» видно, сколько раз прочитан каждый вопрос; слабые места — где отметок меньше."
      },
      {
        title: "Не перегружать день",
        text:
          "Часы подряд с одним текстом дают мало: внимание падает через 30–45 минут. " +
          "Лучше два коротких подхода, чем один длинный.",
        src: "исследования устойчивости внимания",
        used: "В настройках можно ограничить день по минутам — план подстроится и растянет остаток."
      }
    ];

    const list = h("div.tips");
    for (const tip of tips) {
      list.appendChild(
        h("div.tip", [
          h("h4", tip.title),
          h("p", tip.text),
          h("div.src", [
            "Источник: ",
            tip.link
              ? h("a", { href: tip.link, onclick: (e) => { e.preventDefault(); root.App.openExternal(tip.link); } }, tip.src)
              : tip.src
          ]),
          h("div.warn-box.info", [
            UI.icon("spark"),
            h("span", [h("b", "В программе: "), tip.used])
          ])
        ])
      );
    }
    wrap.appendChild(list);

    // Как программа считает
    const how = h("div.card");
    how.appendChild(h("div.card-title", [h("h2", "Как считается время")]));
    how.appendChild(
      h("div", { style: { display: "grid", gap: "10px", fontSize: "14px", lineHeight: "1.6", color: "var(--ink-soft)" } }, [
        h("p", [
          h("b", "Слова и знаки. "), "Слово — последовательность букв и цифр; дефис внутри слова его не разрывает " +
          "(«административно-правовой» — одно слово), как считает Word. Знаки — без пробелов."
        ]),
        h("p", [
          h("b", "Сложность. "), "К длинным нормам с перечнями и множеством знаков препинания применяется поправка " +
          "до 2 раз: такой текст читается медленнее, чем сплошной."
        ]),
        h("p", [
          h("b", "Повторения. "), "Первое чтение — полное время, повторные — быстрее (по умолчанию в 1,5 раза). " +
          "Коэффициент можно изменить в настройках."
        ]),
        h("p", [
          h("b", "Пересчёт. "), "Как только вы отмечаете вопрос прочитанным, остаток делится на оставшиеся дни заново. " +
          "Поэтому отставание не «копится»: план сразу показывает новую норму."
        ])
      ])
    );
    wrap.appendChild(how);
    return wrap;
  }

  // =====================================================================
  //  НАСТРОЙКИ
  // =====================================================================

  function viewSettings() {
    const s = settings();
    const wrap = h("div.grid", { style: { gap: "16px" } });

    // Скорость чтения
    const speedCard = h("div.card");
    speedCard.appendChild(h("div.card-title", [h("h2", "Скорость чтения")]));
    speedCard.appendChild(
      h("div.settings-grid", [
        settingsRow(
          "Слов в минуту",
          "Сколько слов вы прочитываете за минуту в учебном тексте. Влияет на всё: время вопроса, норму дня, дату финиша.",
          UI.stepper(s.wordsPerMinute, { min: 40, max: 800, step: 5, onChange: (v) => setSetting("wordsPerMinute", v) })
        ),
        settingsRow(
          "Считать в знаках",
          "Некоторые считают скорость в знаках в минуту — так делают редакторы и корректоры. Обычно удобнее слова.",
          switchControl("unit", s.unit === "cpm", (on) => setSetting("unit", on ? "cpm" : "wpm"), on0("знаки"), "слова")
        ),
        s.unit === "cpm"
          ? settingsRow("Знаков в минуту", "Средняя скорость чтения вслух — около 900–1200 знаков в минуту.",
            UI.stepper(s.charsPerMinute, { min: 300, max: 4000, step: 50, onChange: (v) => setSetting("charsPerMinute", v) }))
          : null,
        settingsRow(
          "Повторное чтение быстрее",
          "Во сколько раз быстрее вы читаете уже знакомый ответ. 1,5 — обычное значение.",
          UI.stepper(Math.round(s.reviewSpeedFactor * 10), {
            min: 10,
            max: 30,
            onChange: (v) => setSetting("reviewSpeedFactor", v / 10)
          })
        ),
        settingsRow(
          "Интервал повторений",
          "Доля от срока до экзамена для первого повторения. Исследования дают оптимум 10–20 %.",
          minuteChips()
        )
      ])
    );
    wrap.appendChild(speedCard);

    // План по умолчанию
    const defCard = h("div.card");
    defCard.appendChild(h("div.card-title", [h("h2", "Новые дисциплины")]));
    defCard.appendChild(
      h("div.settings-grid", [
        settingsRow(
          "Прогонов по умолчанию",
          "Сколько раз прочитать файл. 3 — разумный минимум для экзамена.",
          UI.stepper(s.defaultPasses, { min: 1, max: 10, onChange: (v) => setSetting("defaultPasses", v) })
        ),
        settingsRow(
          "Как распределять",
          "Равномерно — весь объём делится на дни. По вопросам — фиксированное число новых в день.",
          modeControl()
        ),
        settingsRow(
          "Общий бюджет в день",
          "Если задан, работа по всем дисциплинам делится внутри этого времени: каждый день понемногу из каждой.",
          UI.stepper(s.globalDailyMinutes, { min: 0, max: 600, step: 15, onChange: (v) => setSetting("globalDailyMinutes", v) })
        ),
        settingsRow(
          "Потолок дня",
          "Жёсткий предел минут в день на одну дисциплину. 0 — без предела.",
          UI.stepper(s.dailyCapMinutes, { min: 0, max: 600, step: 10, onChange: (v) => setSetting("dailyCapMinutes", v) })
        )
      ])
    );
    wrap.appendChild(defCard);

    // Оформление и звук
    const lookCard = h("div.card");
    lookCard.appendChild(h("div.card-title", [h("h2", "Оформление и звук")]));
    lookCard.appendChild(
      h("div.settings-grid", [
        settingsRow("Звуки интерфейса", "Мягкие короткие звуки при отметках и переходах.",
          switchControl("sound", s.sound, (on) => {
            setSetting("sound", on);
            root.Sound.configure({ enabled: on });
          })),
        settingsRow("Громкость", "Общая громкость звуков.",
          h("input", {
            type: "range",
            min: "0",
            max: "100",
            value: String(Math.round((s.soundVolume || 0.45) * 100)),
            style: { width: "170px", accentColor: "var(--accent)" },
            oninput: (e) => {
              const v = Number(e.target.value) / 100;
              setSetting("soundVolume", v, true);
              root.Sound.configure({ volume: v });
            }
          })),
        settingsRow("Время суток на фоне", "Небо меняется по часам. Можно зафиксировать нужное время.",
          hourControl()),
        settingsRow("Меньше движения", "Отключает анимации — для спокойной работы или слабого компьютера.",
          switchControl("reduceMotion", s.reduceMotion, (on) => {
            setSetting("reduceMotion", on);
            document.body.classList.toggle("reduce-motion", on);
          }))
      ])
    );
    wrap.appendChild(lookCard);

    // Данные
    const dataCard = h("div.card");
    dataCard.appendChild(h("div.card-title", [h("h2", "Данные")]));
    dataCard.appendChild(
      h("div.settings-grid", [
        settingsRow("Резервная копия", "Сохранить всю библиотеку в файл — пригодится при переносе на другой компьютер.",
          h("div.row", [
            UI.button("Сохранить", { size: "sm", icon: "export", onClick: () => root.App.exportBackup() }),
            UI.button("Папка с данными", { size: "sm", kind: "ghost", onClick: () => root.App.openDataDir() })
          ])),
        settingsRow("Занято на диске", "", h("span.mono", { id: "storageInfo" }, "…")),
        settingsRow("Версия", "", h("span.mono", { id: "versionInfo" }, "…"))
      ])
    );
    wrap.appendChild(dataCard);

    // Заполняем сведения
    setTimeout(async () => {
      try {
        if (root.api && root.api.info) {
          const info = await root.api.info();
          const v = document.getElementById("versionInfo");
          if (v) v.textContent = info.version + " · Electron " + info.electron;
        }
        if (root.api && root.api.storageStats) {
          const st = await root.api.storageStats();
          const el = document.getElementById("storageInfo");
          if (el) el.textContent = fmtBytes(st.textsBytes + st.libraryBytes) + " (" + fmtBytes(st.textsBytes) + " тексты)";
        }
      } catch (e) {
        /* сведения не критичны */
      }
    }, 30);

    return wrap;
  }

  function on0(label) {
    return label;
  }

  function fmtBytes(n) {
    if (!n) return "0 КБ";
    if (n < 1024 * 1024) return Math.round(n / 1024) + " КБ";
    return (n / (1024 * 1024)).toFixed(1).replace(".", ",") + " МБ";
  }

  function setSetting(key, value, quiet) {
    state().settings[key] = value;
    root.Store.save();
    if (!quiet) root.App.refresh();
  }

  function settingsRow(title, desc, control) {
    return h("div.settings-row", [
      h("div", [h("div.title", title), desc ? h("div.desc", desc) : null]),
      h("div", control)
    ]);
  }

  function switchControl(name, on, onChange, alt) {
    const input = h("input", {
      type: "checkbox",
      checked: on,
      onchange: (e) => {
        root.Sound.play(e.target.checked ? "check" : "uncheck");
        onChange(e.target.checked);
      }
    });
    return h("label.switch", [input, h("span.track"), h("span.switch-label", on ? (alt || "включено") : "выключено")]);
  }

  function minuteChips() {
    const s = settings();
    const options = [0.1, 0.15, 0.2, 0.25, 0.3];
    const wrap = h("div.chips");
    for (const v of options) {
      const on = Math.abs((s.gapRatio || 0.15) - v) < 0.001;
      wrap.appendChild(
        h("button.chip" + (on ? ".on" : ""), {
          onclick: () => setSetting("gapRatio", v)
        }, Math.round(v * 100) + "%")
      );
    }
    return wrap;
  }

  function modeControl() {
    const s = settings();
    const seg = h("div.segmented");
    [["even", "равномерно"], ["questions", "по вопросам"], ["minutes", "по минутам"]].forEach(([k, l]) => {
      seg.appendChild(
        h("button" + (s.defaultMode === k ? ".on" : ""), {
          onclick: () => setSetting("defaultMode", k)
        }, l)
      );
    });
    return seg;
  }

  function hourControl() {
    const s = settings();
    const wrap = h("div.chips");
    const opts = [
      [null, "как есть"],
      [7, "утро"],
      [12, "день"],
      [18, "вечер"],
      [23, "ночь"]
    ];
    for (const [v, label] of opts) {
      const on = v == null ? s.skyHour == null : s.skyHour === v;
      wrap.appendChild(
        h("button.chip" + (on ? ".on" : ""), {
          onclick: () => {
            setSetting("skyHour", v);
            if (v == null) root.Sky.clearHour();
            else root.Sky.setHour(v);
          }
        }, label)
      );
    }
    return wrap;
  }

  // =====================================================================
  //  Диалоги
  // =====================================================================

  function renameDiscipline(d) {
    const input = h("input.input", { value: d.name, placeholder: "Название дисциплины" });
    const m = UI.openModal({
      title: "Название дисциплины",
      body: h("div", [
        UI.field("Как показывать", input),
        h("p.muted", { style: { fontSize: "12px", marginTop: "8px" } },
          "Например: «Административная деятельность полиции», «Уголовное право».")
      ]),
      footer: [
        UI.button("Сохранить", {
          kind: "primary",
          onClick: () => {
            const v = input.value.trim();
            if (v) {
              d.name = v;
              root.Store.save();
              root.Sound.play("check");
              root.App.refresh();
            }
            m.close();
          }
        }),
        UI.button("Отмена", { kind: "ghost", onClick: () => m.close() })
      ]
    });
    setTimeout(() => input.focus(), 60);
  }

  function confirmDelete(d) {
    const m = UI.openModal({
      title: "Удалить дисциплину?",
      subtitle: "«" + d.name + "»",
      body: h("div", [
        h("p.soft", "Вопросы, отметки о прочтении и настройки плана по этой дисциплине будут удалены."),
        h("div.warn-box", { style: { marginTop: "12px" } }, [
          UI.icon("warn"),
          h("span", "Сам файл на диске останется на месте — удаляется только запись в библиотеке.")
        ])
      ]),
      footer: [
        UI.button("Удалить", {
          kind: "ghost",
          onClick: () => {
            root.Store.removeDiscipline(d.id);
            root.Sound.play("uncheck");
            UI.toast({ kind: "info", title: "Удалено", text: "«" + d.name + "»" });
            m.close();
            root.App.go("disciplines");
          }
        }),
        h("div.spacer"),
        UI.button("Отмена", { kind: "primary", onClick: () => m.close() })
      ]
    });
  }

  root.Views = {
    dashboard: viewDashboard,
    today: viewToday,
    disciplines: viewDisciplines,
    discipline: viewDiscipline,
    calendar: viewCalendar,
    stats: viewStats,
    tips: viewTips,
    settings: viewSettings,
    plan,
    accentOf,
    groupTodayTasks,
    taskRow,
    sparkleBurst,
    setDiscTab: (t) => {
      discTab = t;
    }
  };
})(typeof window !== "undefined" ? window : globalThis);
