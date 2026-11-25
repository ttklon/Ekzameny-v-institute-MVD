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
            JSON.stringify(d.reading || null) +
            ":" +
            (d.answerVariant || "auto") +
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


  /** Быстрый отпечаток объёма: сумма слов и знаков по вопросам. */
  function volumeStamp(d) {
    let w = 0;
    let c = 0;
    // Объём краткого варианта тоже входит в отпечаток: без него кэш плана
    // остался бы старым, когда библиотека догрузит краткие ответы.
    let aw = 0;
    let ac = 0;
    const qs = d.questions || [];
    for (let i = 0; i < qs.length; i++) {
      w += qs[i].words || 0;
      c += qs[i].chars || 0;
      aw += qs[i].altWords || 0;
      ac += qs[i].altChars || 0;
    }
    return w + "." + c + "." + aw + "." + ac;
  }



  // =====================================================================
  //  ОБЗОР
  // =====================================================================

  /**
   * Обзор как самостоятельный экран больше не нужен: всё, что человеку важно
   * увидеть утром, — это «что читать сегодня». Поэтому обзор ведёт туда же.
   */
  function viewDashboard() {
    return viewToday();
  }

  function text(t) {
    return document.createTextNode(String(t));
  }




  /** Ближайшая дата экзамена среди дисциплин (или null). */
  function nearestExam() {
    let best = null;
    for (const d of root.Store.activeDisciplines()) {
      if (d.plan && P.isValidDate(d.plan.examDate)) {
        if (!best || d.plan.examDate < best) best = d.plan.examDate;
      }
    }
    return best;
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
        if (next) {
          celebrate(d, task.qIndex, date);
          // Плашка с отменой: отметили не тот вопрос — вернуть можно сразу.
          UI.toast({
            kind: "ok",
            title: "№ " + q.num + " отмечен",
            text: d.name + " · " + UI.dateShort(date),
            duration: 6000,
            action: {
              label: "Отменить",
              onClick: () => {
                root.Store.setRead(d.id, task.qIndex, date, false);
                root.Sound.play("uncheck");
                root.App.refresh();
              }
            }
          });
        } else {
          UI.toast({
            kind: "info",
            title: "Отметка снята",
            text: "Вопрос № " + q.num + " снова в работе — план пересчитан.",
            duration: 4200,
            action: {
              label: "Вернуть",
              onClick: () => {
                root.Store.setRead(d.id, task.qIndex, date, true);
                root.App.refresh();
              }
            }
          });
        }
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
    const box = h("div.grid", { style: { gap: "16px" } });

    const intro = h("div.card");
    intro.appendChild(
      h("div.empty", { style: { paddingBottom: "10px" } }, [
        h("div.empty-icon", [UI.icon("cloud")]),
        h("h3", "Ответы уже внутри"),
        h("p", "Все вопросы с ответами идут вместе с программой — добавлять ничего не нужно. Откройте «Дисциплины» и нажмите на предмет. Свои файлы тоже можно добавить, если понадобится."),
        h("div.row", [
          UI.button("Добавить файл", { kind: "primary", icon: "plus", onClick: () => root.App.openImport() }),
          UI.button("Как это работает", { kind: "ghost", icon: "info", onClick: () => root.App.go("settings") })
        ])
      ])
    );

    // Три шага — что произойдёт дальше.
    const steps = h("div.steps");
    [
      ["1", "Выберите дисциплину", "Семь предметов уже с ответами: от административной деятельности до трудового права. Внутри — весь перечень вопросов к экзамену."],
      ["2", "Поставьте дату экзамена", "Программа предложит месяц. Поставьте свою — от неё зависит вся нагрузка."],
      ["3", "Читайте по списку", "Каждый день на экране «Сегодня» будет список вопросов. Отметили прочитанное — план пересчитался."]
    ].forEach(([num, title, text]) => {
      steps.appendChild(
        h("div.step", [
          h("div.step-num", num),
          h("div", [
            h("div.step-title", title),
            h("div.step-text", text)
          ])
        ])
      );
    });
    intro.appendChild(steps);
    box.appendChild(intro);

    // Что программа умеет — коротко, без технических слов.
    const about = h("div.card");
    about.appendChild(h("div.card-title", [h("h2", "Что внутри")]));
    about.appendChild(
      h("div.about-grid", [
        aboutItem("file", "Готовые ответы внутри", "627 вопросов по семи дисциплинам уже в программе. По административной деятельности ответов два: подробный — на первое чтение, краткий — на повторения. Свои файлы тоже читаются: TXT, DOCX, PDF, ODT, RTF."),
        aboutItem("stats", "Точный объём", "Слова, знаки и время чтения по каждому вопросу — видно, что читается дольше."),
        aboutItem("calendar", "План до экзамена", "Вся работа раскладывается по дням с повторениями. Не успеваете — программа скажет."),
        aboutItem("check", "Отметки и пересчёт", "Отмечаете прочитанное — норма на остаток дней пересчитывается сама.")
      ])
    );
    box.appendChild(about);

    return box;
  }

  function aboutItem(icon, title, text) {
    return h("div.about-item", [
      h("div.about-icon", [UI.icon(icon)]),
      h("div", [
        h("div.about-title", title),
        h("div.about-text", text)
      ])
    ]);
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

    // Библиотека пуста — вместо календаря показываем, с чего начать.
    if (!root.Store.activeDisciplines().length) {
      wrap.appendChild(emptyState());
      return wrap;
    }

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
        h("div.row", { style: { marginTop: "6px", gap: "8px" } }, [
          UI.button("Отметить всё", { kind: "primary", icon: "check", onClick: () => markAllOn(date) }),
          // «Взять вперёд»: взял больше сегодня — следующие дни станут легче.
          // Отдельного места в плане для этого не нужно, поэтому просто
          // открываем первый вопрос из ближайшего дня.
          UI.button("Взять вперёд", {
            kind: "ghost",
            icon: "chevronRight",
            onClick: () => takeAhead(date)
          }),
          doneCount
            ? UI.button("Снять всё", { kind: "ghost", icon: "reset", onClick: () => clearAllOn(date) })
            : null,
          h("div.spacer"),
          h("span.muted", { style: { fontSize: "12px" } },
            "Отметки можно снять в любой момент — план пересчитается")
        ])
      );
    }
    wrap.appendChild(card);

    // Уже отмечено за этот день. Раньше ошибочно отмеченный вопрос исчезал
    // из списка, и снять отметку было негде — теперь он всегда на виду.
    const marked = markedOn(date);
    if (marked.length) wrap.appendChild(markedCard(date, marked));

    return wrap;
  }

  /**
   * Чтение вперёд: берём первый вопрос из следующего дня, где есть работа.
   *
   * Обычная отметка «прочитано» на чужой день и есть «вперёд»: программа
   * видит, что сегодня человек прочёл больше нормы, и снимает этот объём с
   * будущих дней. Кнопка просто избавляет от поиска такого вопроса вручную.
   */
  function takeAhead(date) {
    const planData = plan();
    const days = Object.keys(planData.combined || {}).sort();
    for (const day of days) {
      if (day <= date) continue;
      const items = planData.combined[day] || [];
      if (!items.length) continue;
      const t = items[0];
      root.Sound.play("page");
      root.App.openQuestion(t.discId, t.qIndex, day);
      return;
    }
    UI.toast({ kind: "info", title: "Впереди пусто", text: "Всё, что было запланировано, уже разложено." });
  }

  /** Вопросы, отмеченные прочитанными за день: [{discId, qIndex, rows}]. */
  function markedOn(date) {
    const out = [];
    for (const it of root.Store.readsOn(date)) {
      const d = root.Store.getDiscipline(it.discId);
      const q = d && d.questions[it.qIndex];
      if (!d || !q) continue;
      out.push({ discId: d.id, qIndex: it.qIndex, num: q.num, title: q.title, disc: d });
    }
    out.sort((a, b) => (a.disc.name < b.disc.name ? -1 : a.disc.name > b.disc.name ? 1 : a.num - b.num));
    return out;
  }

  /** Карточка «Уже отмечено»: список с крестиком у каждого вопроса. */
  function markedCard(date, list) {
    const card = h("div.card");
    card.appendChild(
      h("div.card-title", [
        h("h2", "Уже отмечено · " + list.length),
        UI.button("Снять всё", {
          kind: "ghost",
          size: "sm",
          icon: "reset",
          onClick: () => clearAllOn(date)
        })
      ])
    );
    const rows = h("div", { style: { display: "grid", gap: "6px" } });
    for (const it of list) {
      rows.appendChild(
        h("div.row", {
          style: {
            padding: "9px 12px",
            borderRadius: "12px",
            background: "rgba(255,255,255,.45)",
            gap: "10px"
          }
        }, [
          h("span", {
            style: {
              color: accentOf(it.disc),
              fontWeight: "700",
              fontSize: "12px",
              minWidth: "86px"
            }
          }, it.disc.name),
          h("span", { style: { fontSize: "13px", flex: "1 1 auto" } },
            "№ " + it.num + " · " + (it.title || "")),
          h("button.btn.btn-ghost.btn-sm", {
            title: "Снять отметку",
            style: { padding: "3px 9px", fontSize: "12px" },
            onclick: () => {
              root.Store.setRead(it.discId, it.qIndex, date, false);
              root.Sound.play("uncheck");
              root.App.refresh();
            }
          }, "снять")
        ])
      );
    }
    card.appendChild(rows);
    card.appendChild(
      h("p.muted", { style: { fontSize: "11.5px", marginTop: "10px" } },
        "Снятая отметка возвращает вопрос в план — ничего не потеряется.")
    );
    return card;
  }

  /** Снять все отметки за день с возможностью вернуть одним нажатием. */
  function clearAllOn(date) {
    const removed = root.Store.clearReadsOn(null, date);
    if (!removed.length) return;
    root.Sound.play("uncheck");
    UI.toast({
      kind: "info",
      title: "Отметки за день сняты",
      text: "Снято: " + removed.length + ". Вопросы снова в плане.",
      duration: 7000,
      action: {
        label: "Вернуть",
        onClick: () => {
          root.Store.restoreReads(removed, date);
          root.App.refresh();
        }
      }
    });
    root.App.refresh();
  }

  function markAllOn(date) {
    const planData = plan();
    const items = planData.combined[date] || [];
    const byDisc = new Map();
    for (const t of items) {
      if (!byDisc.has(t.discId)) byDisc.set(t.discId, []);
      byDisc.get(t.discId).push(t.qIndex);
    }
    const added = [];
    for (const [discId, indices] of byDisc) {
      // Уже отмеченное повторно не считаем: «вернуть» должно вернуть ровно то,
      // что добавила эта кнопка.
      const before = new Set(root.Store.readsOn(date, discId).map((x) => x.qIndex));
      const fresh = indices.filter((i) => !before.has(i));
      if (!fresh.length) continue;
      root.Store.setReadMany(discId, fresh, date, true);
      for (const qIndex of fresh) added.push({ discId: discId, qIndex: qIndex });
    }
    root.Sound.play("complete");
    sparkleBurst();
    if (added.length) {
      UI.toast({
        kind: "ok",
        title: "Отмечено: " + added.length,
        text: "Если это была ошибка — верните одним нажатием.",
        duration: 6500,
        action: {
          label: "Отменить",
          onClick: () => {
            const byDisc2 = new Map();
            for (const it of added) {
              if (!byDisc2.has(it.discId)) byDisc2.set(it.discId, []);
              byDisc2.get(it.discId).push(it.qIndex);
            }
            for (const [id, list] of byDisc2) root.Store.setReadMany(id, list, date, false);
            root.Sound.play("uncheck");
            root.App.refresh();
          }
        }
      });
    }
    root.App.refresh();
  }

  // =====================================================================
  //  ДИСЦИПЛИНЫ
  // =====================================================================

  function viewDisciplines() {
    const discs = root.Store.activeDisciplines();
    const planData = plan();
    const wrap = h("div.grid", { style: { gap: "14px" } });

    // Главное действие — открыть дисциплину и читать. Добавление своих файлов
    // стоит рядом, но не первым: ответы уже внутри.
    const head = h("div.row", [
      h("span.muted", { style: { fontSize: "13px" } },
        discs.length
          ? discs.length + " " + UI.plural(discs.length, "дисциплина", "дисциплины", "дисциплин") +
            " · " + UI.num(planData.totals.questions) + " " + UI.plural(planData.totals.questions, "вопрос", "вопроса", "вопросов") +
            " · ответы внутри"
          : ""),
      h("div.spacer"),
      UI.button("Добавить свой файл", { kind: "ghost", icon: "plus", onClick: () => root.App.openImport() })
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
          // Только то, по чему принимают решение: сколько читать и когда экзамен.
          h("div.disc-meta", [
            h("span", [h("b", String(d.questions.length)), " " + UI.plural(d.questions.length, "вопрос", "вопроса", "вопросов")]),
            h("span", [h("b", UI.dur(st.minutesLeft || 0)), " чтения"]),
            d.plan && P.isValidDate(d.plan.examDate)
              ? h("span", "экзамен " + UI.dateShort(d.plan.examDate) + " (" + UI.relativeDay(d.plan.examDate) + ")")
              : h("span", "дата экзамена не задана"),
            d.builtin
              ? h("span.tag.ok", d.hasShortAnswers ? "ответы: подробно + кратко" : "ответы внутри")
              : null
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

  let discFilter = "";

  /**
   * Экран дисциплины — одна страница вместо трёх вкладок.
   *
   * Сверху только то, что человек действительно меняет: сколько часов в день
   * он готов читать и когда экзамен. Всё остальное — свёрнутые «детали»:
   * их открывают один раз и больше не трогают.
   */
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
    const g = settings();
    const wrap = h("div.grid", { style: { gap: "16px" } });
    // Пример времени в «Деталях»: объявляем заранее, рисуем только когда блок
    // раскрыт. Пустая функция — чтобы вызов в конце не падал.
    let paintPreview = () => {};

    // ---------- Шапка: название и «сколько читать» ---------------------
    const head = h("div.card");
    head.appendChild(
      h("div.disc-head", [
        h("div.disc-head-main", [
          h("div.row", { style: { gap: "8px", marginBottom: "6px" } }, [
            h("span.tag", { style: { background: accentOf(d) + "22", color: accentOf(d) } },
              (d.parsing && strategyName(d.parsing.strategy)) || "файл"),
            h("span.muted", { style: { fontSize: "11.5px" } },
              d.questions.length + " " + UI.plural(d.questions.length, "вопрос", "вопроса", "вопросов"))
          ]),
          h("h2", d.name),
          h("div.muted", { style: { fontSize: "12.5px", marginTop: "6px" } },
            "Всего " + UI.durLong(P.totalMinutes(d, g)) + " чтения · осталось " + UI.dur(st.minutesLeft || 0))
        ]),
        h("div.row", { style: { gap: "8px" } }, [
          UI.button("Читать", {
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

    // Главная настройка: дата экзамена и число часов в день.
    head.appendChild(
      h("div.dates-row", { style: { marginTop: "16px" } }, [
        h("label.date-box" + (P.isValidDate(d.plan.examDate) && P.daysBetween(today(), d.plan.examDate) < 0 ? ".bad" : ""), [
          h("span.date-label", "Экзамен"),
          h("input.input", {
            type: "date",
            value: d.plan.examDate,
            onchange: (e) => updatePlan(d, { examDate: e.target.value })
          }),
          h("span.date-hint", examHint(d))
        ])
      ])
    );

    // «Сколько часов в день» — одно число вместо режимов и весов.
    const comfortCard = h("div", { style: { marginTop: "14px" } });
    const comfort = Number(d.plan.comfortMinutes) || 0;
    const hoursNow = comfort > 0 ? comfort / 60 : 0;
    const chips = h("div.chips");
    [0.5, 1, 1.5, 2, 3, 4].forEach((hr) => {
      chips.appendChild(
        h("button.chip" + (Math.abs(hoursNow - hr) < 0.01 ? ".on" : ""), {
          onclick: () => {
            updatePlan(d, { comfortMinutes: Math.abs(hoursNow - hr) < 0.01 ? 0 : Math.round(hr * 60) });
            root.Sound.play("tap");
          }
        }, UI.dur(Math.round(hr * 60)))
      );
    });
    comfortCard.appendChild(
      h("div.field-label", { style: { marginBottom: "6px" } }, "Сколько часов в день вы готовы читать")
    );
    comfortCard.appendChild(chips);
    comfortCard.appendChild(
      h("div.muted", { style: { fontSize: "12.5px", lineHeight: "1.5", marginTop: "8px" } },
        comfort > 0
          ? "План построен по " + UI.dur(comfort) + " в обычный день — сейчас выходит около " +
            UI.dur(st.perDayMinutes || 0) + ". Если прочитаете больше, следующие дни станут легче."
          : "Пока не выбрано: считаю по " + UI.dur(st.perDayMinutes || 0) + " в день (ровно, чтобы успеть). " +
            "Поставьте своё время — план подстроится.")
    );
    head.appendChild(comfortCard);

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

    // ---------- Ближайшие дни: что и когда читать ----------------------
    const days = Object.keys(pd.days || {}).sort();
    const future = days.filter((day) => day >= today() && (pd.days[day] || []).length).slice(0, 5);
    if (future.length) {
      const card = h("div.card");
      card.appendChild(h("div.card-title", [h("h2", "Ближайшие дни")]));
      const rows = h("div", { style: { display: "grid", gap: "7px" } });
      for (const day of future) {
        const items = pd.days[day];
        const minutes = items.reduce((a, it) => a + it.minutes, 0);
        rows.appendChild(
          h("div.row", {
            style: { padding: "9px 12px", borderRadius: "12px", background: "rgba(255,255,255,.42)", cursor: "pointer" },
            onclick: () => root.App.go("today", { date: day })
          }, [
            h("div", { style: { minWidth: "100px" } }, [
              h("div", { style: { fontWeight: "700", fontSize: "13px" } }, UI.dateShort(day)),
              h("div.muted", { style: { fontSize: "11px" } }, UI.weekDayShort(day))
            ]),
            h("div", { style: { flex: "1 1 auto", fontSize: "12.5px" } },
              items.slice(0, 6).map((it) => "№" + (d.questions[it.qIndex] ? d.questions[it.qIndex].num : it.qIndex + 1)).join(" · ") +
              (items.length > 6 ? " +" + (items.length - 6) : "")),
            h("div", { style: { fontWeight: "700", fontSize: "13px", minWidth: "64px", textAlign: "right" } },
              UI.dur(minutes))
          ])
        );
      }
      card.appendChild(rows);
      wrap.appendChild(card);
    }

    // ---------- Вопросы -------------------------------------------------
    const qCard = h("div.card");
    const search = h("input.input", {
      type: "search",
      placeholder: "Поиск по вопросам…",
      value: discFilter,
      style: { maxWidth: "300px" },
      oninput: (e) => {
        discFilter = e.target.value;
        paintQuestions();
      }
    });
    qCard.appendChild(
      h("div.card-title", [
        h("div", [
          h("h2", "Вопросы"),
          h("div.muted", { style: { fontSize: "12px", marginTop: "2px" } },
            "Щёлкните, чтобы прочитать ответ и отметить прочтение")
        ]),
        search
      ])
    );

    const table = h("div.q-table");
    function paintQuestions() {
      UI.clear(table);
      const needle = discFilter.trim().toLowerCase();
      let shown = 0;
      d.questions.forEach((question, idx) => {
        if (needle && question.title.toLowerCase().indexOf(needle) === -1 &&
            String(question.num).indexOf(needle) === -1) return;
        shown++;
        const stq = P.questionState(d, idx, g);
        const complete = stq.done >= stq.passes;
        table.appendChild(
          h("div.q-row" + (complete ? ".complete" : ""), {
            onclick: () => root.App.openQuestion(d.id, idx, today())
          }, [
            h("div.q-num", String(question.num)),
            h("div.q-name", { title: question.title }, question.title),
            h("div.q-vol", UI.dur(P.questionTotalMinutes(d, question, g))),
            h("div.pips", Array.from({ length: stq.passes }, (_, i) =>
              h("i.pip" + (i < stq.done ? ".on" : ""), {
                title: "прочтение " + (i + 1) + (stq.reads[i] ? ": " + UI.dateShort(stq.reads[i]) : "")
              })
            ))
          ])
        );
      });
      if (!shown) table.appendChild(h("p.muted", { style: { padding: "16px" } }, "Ничего не найдено."));
    }
    paintQuestions();
    qCard.appendChild(table);
    wrap.appendChild(qCard);

    // ---------- Детали: всё, что нужно редко ---------------------------
    const advOpen = d.advOpen === true;
    const adv = h("div.card");
    adv.appendChild(
      h("button.adv-toggle", {
        onclick: () => {
          d.advOpen = !advOpen;
          root.Store.save();
          root.App.refresh();
        }
      }, [
        UI.icon(advOpen ? "chevronDown" : "chevronRight"),
        h("span", "Детали"),
        h("span.muted", { style: { fontSize: "12px", fontWeight: "400" } },
          advOpen ? "" : "скорость, прогоны, выходные, вариант ответа")
      ])
    );

    if (advOpen) {
      const grid = h("div.plan-grid");

      // Число прогонов
      grid.appendChild(
        planField("Прочитать полностью", UI.stepper(d.plan.passes, {
          min: 1, max: 12,
          onChange: (v) => updatePlan(d, { passes: v })
        }), "сколько раз пройти все вопросы до экзамена. 3 — разумный минимум")
      );

      // Своя скорость чтения
      const own = d.reading || null;
      const wpm = own && own.wordsPerMinute ? own.wordsPerMinute : g.wordsPerMinute || 150;
      const slider = h("input.speed-slider", {
        type: "range", min: "60", max: "400", step: "5", value: String(wpm),
        oninput: (e) => {
          d.reading = Object.assign({}, d.reading || {}, { wordsPerMinute: Number(e.target.value) });
          root.Store.save();
          const out = adv.querySelector(".speed-value");
          if (out) out.textContent = e.target.value + " слов/мин";
          paintPreview();
        },
        onchange: () => {
          root.Sound.play("tap");
          root.App.refresh();
        }
      });
      let avgWords = 0;
      let answered = 0;
      for (const q of d.questions) {
        if (q.aWords > 0) { avgWords += q.words; answered++; }
      }
      avgWords = answered ? Math.round(avgWords / answered) : 600;
      const preview = h("div.read-example");
      paintPreview = function () {
        UI.clear(preview);
        const rate = (d.reading && d.reading.wordsPerMinute) || g.wordsPerMinute || 150;
        preview.appendChild(h("div", [
          h("div.section-label", "средний ответ — " + UI.num(avgWords) + " слов"),
          h("div.read-big", [UI.dur(avgWords / rate), h("span.read-unit", " на один вопрос")])
        ]));
        preview.appendChild(h("div", [
          h("div.section-label", "вся дисциплина, " + d.plan.passes + " " +
            UI.plural(d.plan.passes, "прогон", "прогона", "прогонов")),
          h("div.read-big", UI.durLong(P.totalMinutes(d, g)))
        ]));
      };
      grid.appendChild(planField("Скорость чтения", h("div", [
        h("div.speed-line", [h("span.speed-value", wpm + " слов/мин"), slider]),
        own ? UI.button("Как у всех", {
          kind: "ghost", size: "sm", icon: "reset",
          onClick: () => {
            delete d.reading;
            root.Store.save();
            root.App.refresh();
          }
        }) : null,
        preview
      ]), "у разных предметов разный язык; общая — в «Настройках»"));

      grid.appendChild(dayLoadField(d));

      // Схема «сначала большой файл, потом маленький»: подробный ответ один
      // раз целиком, краткий — после него, и второй раз по краткому только
      // если останется время.
      if (d.hasShortAnswers) {
        const bf = (d.plan && d.plan.bigFirst) || null;
        const mode = !bf ? "usual" : (bf.small > 1 ? "twice" : "once");
        // Режим берём из самой дисциплины в момент нажатия: экран мог быть
        // нарисован раньше, а выбор уже изменился.
        const modeNow = () => {
          const live = root.Store.getDiscipline(d.id) || d;
          const cur = live.plan && live.plan.bigFirst;
          if (!cur) return "usual";
          return (Number(cur.small) || 1) > 1 ? "twice" : "once";
        };
        const modeSeg = h("div.segmented");
        [
          ["usual", "как обычно"],
          ["once", "большой → маленький"],
          ["twice", "и ещё раз маленький"]
        ].forEach(([key, label]) => {
          modeSeg.appendChild(h("button" + (mode === key ? ".on" : ""), {
            onclick: () => {
              if (modeNow() === key) return;
              if (key === "usual") d.plan.bigFirst = null;
              else d.plan.bigFirst = { big: 1, small: key === "twice" ? 2 : 1 };
              root.Store.save();
              root.Sound.play("tap");
              root.App.refresh();
            }
          }, label));
        });
        grid.appendChild(planField("Два файла: подробный и краткий", modeSeg,
          mode === "twice"
            ? "подробный один раз, краткий один раз, и второй раз по краткому — только если останется время"
            : mode === "once"
              ? "подробный один раз, потом краткий один раз"
              : "выберите, если ответы лежат двумя файлами — большим и маленьким"));
      }

      // Вариант ответа: подробный или краткий
      if (d.hasShortAnswers) {
        const seg = h("div.segmented");
        [["auto", "сначала подробно, потом кратко"], ["full", "всегда подробно"], ["short", "всегда кратко"]]
          .forEach(([key, label]) => {
            seg.appendChild(h("button" + ((d.answerVariant || "auto") === key ? ".on" : ""), {
              onclick: () => {
                if ((d.answerVariant || "auto") === key) return;
                d.answerVariant = key;
                root.Store.save();
                root.Sound.play("tap");
                root.App.refresh();
              }
            }, label));
          });
        grid.appendChild(planField("Какой ответ читать", seg,
          "по этой дисциплине ответы есть в двух вариантах — время считается по тому, который читаете"));
      }

      const estimatedCount = d.questions.filter((q) => q.estimated).length;
      if (estimatedCount > 0) {
        grid.appendChild(planField("Объём ответа (оценка)",
          UI.stepper(d.assumeAnswerWords || 250, {
            min: 30, max: 1500, step: 10,
            onChange: (v) => { d.assumeAnswerWords = v; reestimateAnswers(d, v); }
          }),
          "для " + estimatedCount + " " + UI.plural(estimatedCount, "вопроса", "вопросов", "вопросов") + " без ответа"));
      }

      adv.appendChild(grid);

      // Опасные кнопки — в самом низу, чтобы не бросались в глаза.
      adv.appendChild(
        h("div.row", { style: { marginTop: "16px", gap: "8px" } }, [
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
          UI.button("Удалить дисциплину", { kind: "ghost", onClick: () => confirmDelete(d) })
        ])
      );
    }
    wrap.appendChild(adv);

    requestAnimationFrame(() => paintPreview());
    return wrap;
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

  /**
   * Нагрузка по дням недели. Три уровня вместо ползунков: понять за секунду,
   * изменить в один клик. «В воскресенье больше» — это один клик по «Больше».
   */
  const DAY_NAMES = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"];
  const DAY_ORDER = [1, 2, 3, 4, 5, 6, 0]; // weekday(): 0 — воскресенье
  // Нагрузка по дням недели: не «три кнопки», а шкала от «отдых» до «втрое
  // больше». У человека разные дни, и загонять его в «вдвое» нельзя.
  const DAY_LEVELS = [
    { v: 0, label: "отдых", title: "в этот день не читаем" },
    { v: 1, label: "обычно", title: "как все дни" },
    { v: 1.5, label: "×1,5", title: "в полтора раза больше обычного" },
    { v: 2, label: "×2", title: "вдвое больше обычного" },
    { v: 3, label: "×3", title: "втрое больше обычного" },
    { v: 4, label: "×4", title: "вчетверо больше обычного" }
  ];

  /** Таблица нагрузки по дням недели: [вс, пн, вт, ср, чт, пт, сб]. */
  function dayLoadTable(plan) {
    const t = plan && plan.dayLoad;
    if (Array.isArray(t) && t.length === 7) {
      // Вес храним как есть: человек мог вписать «240 минут при обычных 180» —
      // это 1,33, и округлять его до 1,5 значит терять его же настройку.
      return t.map((x) => {
        const v = Number(x);
        if (!isFinite(v) || v <= 0) return 0;
        return Math.min(20, v);
      });
    }
    const rest = (plan && plan.restDays) || [];
    return [0, 1, 2, 3, 4, 5, 6].map((wd) => (rest.indexOf(wd) !== -1 ? 0 : 1));
  }

  function dayLoadField(d) {
    const table = dayLoadTable(d.plan);
    const wrap = h("div.day-load");
    const levels = h("div.day-load-head");
    levels.appendChild(h("span"));
    DAY_LEVELS.forEach((lv) => levels.appendChild(h("span.day-load-cap", lv.label)));
    wrap.appendChild(levels);

    DAY_ORDER.forEach((wd, i) => {
      const row = h("div.day-load-row");
      row.appendChild(h("span.day-load-day", DAY_NAMES[i]));
      // Подсвечиваем ближайшую ступень: вес мог быть задан точным числом
      // минут (1,33), и тогда ни одна клетка не совпала бы ровно.
      let nearest = DAY_LEVELS[0];
      for (const lv of DAY_LEVELS) {
        if (Math.abs(lv.v - table[wd]) < Math.abs(nearest.v - table[wd])) nearest = lv;
      }
      for (const lv of DAY_LEVELS) {
        const on = nearest === lv;
        row.appendChild(
          h("button.day-load-cell" + (on ? ".on" : "") + (lv.v === 0 ? ".off" : ""), {
            title: DAY_NAMES[i] + " — " + lv.title,
            onclick: () => {
              if (table[wd] === lv.v) return;
              const next = table.slice();
              next[wd] = lv.v;
              updatePlan(d, { dayLoad: next, restDays: [] });
            }
          }, on ? "•" : "")
        );
      }
      wrap.appendChild(row);
    });

    // Сколько это в минутах: человек видит не «×2», а «суббота — около 2 ч».
    const comfort = Number(d.plan.comfortMinutes) || 0;
    const heavy = DAY_ORDER.map((wd, i) => ({ name: DAY_NAMES[i], w: table[wd] })).filter((x) => x.w > 1);
    const restCount = table.filter((x) => x === 0).length;
    let hint;
    if (restCount === 7) hint = "Все дни отмечены как отдых — плану некуда ставить вопросы.";
    else if (comfort > 0 && heavy.length) {
      hint =
        "В обычный день " + UI.dur(comfort) + ", а " +
        heavy.map((x) => x.name.toLowerCase() + " — около " + UI.dur(comfort * x.w)).join(", ") + ".";
    } else if (heavy.length) {
      hint = "Дни с ×1,5, ×2 и ×3 получат больше вопросов — так и посчитается.";
    } else if (restCount) {
      hint = "Есть выходные. Если в какой-то день читаете больше — поставьте ×2 или ×3.";
    } else {
      hint = "Все дни одинаковые. Если в субботу можете больше — поставьте ×2 или ×3.";
    }

    // Точные минуты по дням: ступени «×2» мало, если в субботу человек может
    // читать четыре часа, а в воскресенье — шесть. Здесь можно вписать своё
    // число минут для каждого дня недели, и вес посчитается из него.
    if (comfort > 0) {
      const exact = h("div.day-exact");
      DAY_ORDER.forEach((wd, i) => {
        const minutes = Math.round(comfort * table[wd]);
        const row = h("div.day-exact-row", [
          h("span.day-load-day", DAY_NAMES[i]),
          UI.stepper(minutes, {
            min: 0,
            max: 960,
            step: 15,
            onChange: (v) => {
              const next = table.slice();
              // 0 минут — выходной, иначе вес = сколько минут делить на обычный день.
              next[wd] = v <= 0 ? 0 : Math.min(20, Math.max(0.25, v / comfort));
              updatePlan(d, { dayLoad: next, restDays: [] });
            }
          }),
          h("span.muted", { style: { fontSize: "12px" } }, minutes > 0 ? UI.dur(minutes) : "не читаю")
        ]);
        exact.appendChild(row);
      });
      wrap.appendChild(
        h("div", { style: { marginTop: "12px" } }, [
          h("div.field-label", { style: { marginBottom: "6px" } }, "Свои минуты по дням"),
          exact,
          h("div.muted", { style: { fontSize: "11.5px", marginTop: "4px" } },
            "Если в какой-то день можете 4 или 6 часов — впишите это число, шкала подстроится сама.")
        ])
      );
    }

    return planField("Нагрузка по дням недели", wrap, hint);
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

  // =====================================================================
  //  НАСТРОЙКИ
  // =====================================================================

  function viewSettings() {
    const s = settings();
    const planData = plan();
    const wrap = h("div.grid", { style: { gap: "16px" } });

    // =================================================================
    //  1. Сколько вы читаете в минуту
    // =================================================================
    const speed = h("div.card");
    speed.appendChild(
      h("div.card-title", [
        h("div", [
          h("h2", "Сколько вы читаете в минуту"),
          h("div.muted", { style: { fontSize: "12.5px", marginTop: "3px", maxWidth: "62ch" } },
            "От этого числа зависит всё остальное: сколько минут займёт ответ, сколько вопросов в день и когда вы закончите. Если не знаете — оставьте 150: это спокойное чтение учебного текста про себя.")
        ]),
        h("span.tag", "главное")
      ])
    );

    // Живой пример: сколько займёт ваш средний ответ.
    let avgWords = 0;
    let answered = 0;
    for (const d of root.Store.activeDisciplines()) {
      for (const q of d.questions) {
        if (q.aWords > 0) {
          avgWords += q.words;
          answered++;
        }
      }
    }
    avgWords = answered ? Math.round(avgWords / answered) : 600;
    const example = h("div.read-example");

    const slider = h("input.speed-slider", {
      type: "range",
      min: "60",
      max: "400",
      step: "5",
      value: String(s.wordsPerMinute),
      oninput: (e) => {
        const v = Number(e.target.value);
        state().settings.wordsPerMinute = v;
        paintSpeed();
        root.Store.save();
      },
      onchange: () => {
        root.Store.save();
        root.Sound.play("tap");
      }
    });

    const presets = h("div.chips");
    [
      [90, "медленно"],
      [130, "спокойно"],
      [150, "обычно"],
      [200, "быстро"],
      [280, "очень быстро"]
    ].forEach(([v, label]) => {
      presets.appendChild(
        h("button.chip" + (s.wordsPerMinute === v ? ".on" : ""), {
          onclick: () => {
            state().settings.wordsPerMinute = v;
            slider.value = String(v);
            root.Store.save();
            root.Sound.play("tap");
            paintSpeed();
          }
        }, label + " · " + v)
      );
    });

    function paintSpeed() {
      const wpm = state().settings.wordsPerMinute || 150;
      const mins = (avgWords * 1.0) / wpm;
      UI.clear(example);
      example.appendChild(
        h("div", [
          h("div.section-label", "ваш средний ответ — " + UI.num(avgWords) + " слов"),
          h("div.read-big", [UI.dur(mins), h("span.read-unit", " на один вопрос")])
        ])
      );
      example.appendChild(
        h("div", [
          h("div.section-label", "весь объём, все прогоны"),
          h("div.read-big", UI.durLong(planData.totals.minutesTotal))
        ])
      );
      // Обновляем подпись у ползунка без перерисовки всего экрана.
      const out = speed.querySelector(".speed-value");
      if (out) out.textContent = wpm + " слов/мин";
      presets.querySelectorAll(".chip").forEach((c, i) => {
        const v = [90, 130, 150, 200, 280][i];
        c.classList.toggle("on", v === wpm);
      });
    }

    speed.appendChild(
      h("div.speed-line", [
        h("span.speed-value", s.wordsPerMinute + " слов/мин"),
        slider
      ])
    );
    speed.appendChild(presets);
    speed.appendChild(example);
    // Заполняем пример сразу: requestAnimationFrame может не сработать до показа.
    paintSpeed();
    speed.appendChild(
      h("div.muted", { style: { fontSize: "12px", marginTop: "2px" } },
        "Повторное чтение уже знакомого ответа считается в 1,5 раза быстрее — так обычно и бывает. Изменить это можно ниже, в разделе «Тонкая настройка».")
    );
    wrap.appendChild(speed);

    // =================================================================
    //  2. Норма дня — одна на всё приложение
    // =================================================================
    // Раньше здесь был «предел на день по всем дисциплинам», а на странице
    // дисциплины — свой объём. Человеку приходилось держать в голове две
    // цифры. Теперь одна: сколько часов в день он читает.
    const time = h("div.card");
    time.appendChild(h("div.card-title", [h("h2", "Сколько времени в день")]));
    time.appendChild(
      h("div.muted", { style: { fontSize: "12.5px", marginBottom: "12px", maxWidth: "66ch" } },
        "Это главное число: программа делит весь объём на дни до экзамена ровно по нему. " +
        "Ничего не выбирать — тоже вариант: тогда считается по объёму работы, чтобы успеть к экзамену.")
    );

    const planChips = h("div.chips");
    [
      [0, "по объёму работы"],
      [30, "30 минут"],
      [45, "45 минут"],
      [60, "1 час"],
      [90, "1,5 часа"],
      [120, "2 часа"],
      [180, "3 часа"],
      [240, "4 часа"]
    ].forEach(([v, label]) => {
      const on = (s.globalDailyMinutes || 0) === v;
      planChips.appendChild(
        h("button.chip" + (on ? ".on" : ""), {
          onclick: () => {
            // Общая норма и «свой объём» дисциплины — одна и та же цифра:
            // ставим её в настройки и в каждую дисциплину, чтобы не было
            // двух противоречащих друг другу значений.
            state().settings.globalDailyMinutes = v;
            for (const d of state().disciplines) {
              if (v > 0) d.plan.comfortMinutes = v;
              else delete d.plan.comfortMinutes;
            }
            root.Store.save();
            root.Sound.play("tap");
            root.App.refresh();
          }
        }, label)
      );
    });
    time.appendChild(
      h("div.settings-row", [
        h("div", [
          h("div.title", "Читаю в день"),
          h("div.desc", "Одно число на все дисциплины. Можно поменять и у отдельной дисциплины — там же, на её странице.")
        ]),
        planChips
      ])
    );

    // Что получается при этом выборе — сразу видно.
    const outcome = h("div.outcome");
    const activeDays = planData.totals.daysWithWork || 0;
    const perDay = activeDays > 0 ? planData.totals.minutesLeft / activeDays : 0;
    outcome.appendChild(outcomeLine("В среднем в день", perDay > 0 ? UI.dur(perDay) : "—"));
    outcome.appendChild(outcomeLine("Самый тяжёлый день",
      planData.totals.maxDayMinutes > 0
        ? UI.dur(planData.totals.maxDayMinutes) + (planData.totals.maxDay ? " (" + UI.dateShort(planData.totals.maxDay) + ")" : "")
        : "—"));
    outcome.appendChild(outcomeLine("Закончите", finishLine(planData)));
    outcome.appendChild(outcomeLine("Осталось прочитать", UI.durLong(planData.totals.minutesLeft)));
    time.appendChild(outcome);
    wrap.appendChild(time);

    // =================================================================
    //  3. Как выглядит и звучит
    // =================================================================
    const look = h("div.card");
    look.appendChild(h("div.card-title", [h("h2", "Как выглядит и звучит")]));
    look.appendChild(
      h("div.settings-grid", [
        settingsRow("Звуки", "Короткие мягкие звуки при отметках и переходах между экранами.",
          switchControl("sound", s.sound, (on) => {
            setSetting("sound", on);
            root.Sound.configure({ enabled: on });
            if (on) root.Sound.play("chime");
          })),
        settingsRow("Громкость", "Общая громкость звуков приложения.",
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
        settingsRow("Небо на фоне", "Небо меняется по времени суток. Можно зафиксировать, если нравится определённое.",
          hourControl()),
        settingsRow("Меньше движения", "Отключает анимации — спокойнее для глаз и легче для слабого компьютера.",
          switchControl("reduceMotion", s.reduceMotion, (on) => {
            setSetting("reduceMotion", on);
            document.body.classList.toggle("reduce-motion", on);
          }))
      ])
    );
    // =================================================================
    //  3-b. Напоминания, трей, автозапуск — коротко, по одному переключателю
    // =================================================================
    const remind = h("div.card");
    remind.appendChild(h("div.card-title", [h("h2", "Напоминания и запуск")]));

    const remindOn = !!(s.remind && s.remind.enabled);
    const remindAt = (s.remind && s.remind.at) || "18:00";

    const remindGrid = h("div.settings-grid", [
      settingsRow("Напоминать о занятиях", "Один раз в день, только если на сегодня что-то есть.",
        switchControl("remindEnabled", remindOn, (on) => {
          setSetting("remind", Object.assign({}, (s.remind || {}), { enabled: on, at: remindAt }), true);
          if (root.api && root.api.remind) root.api.remind.refresh();
          if (on) UI.toast({ kind: "ok", text: "Напомним в " + remindAt });
        })),
      settingsRow("Время напоминания", "Когда присылать напоминание.",
        h("input", {
          type: "time",
          value: remindAt,
          style: { width: "110px" },
          onchange: (e) => {
            const at = e.target.value || "18:00";
            setSetting("remind", Object.assign({}, (s.remind || {}), { enabled: !!(s.remind && s.remind.enabled), at: at }), true);
            if (root.api && root.api.remind) root.api.remind.refresh();
          }
        })),
      settingsRow("Сворачивать в трей", "Крестик прячет окно, приложение продолжает работать.",
        switchControl("closeToTray", !!s.closeToTray, (on) => setSetting("closeToTray", on, true))),
      settingsRow("Запускать с Windows", "Открывается сразу после входа в систему.",
        switchControl("autostart", !!s.autostart, (on) => {
          const api = root.api;
          if (!api || !api.autostart) {
            setSetting("autostart", on, true);
            return;
          }
          api.autostart.set(on).then((res) => {
            if (res && res.ok) setSetting("autostart", !!res.enabled, true);
            else {
              UI.toast({ kind: "error", text: "Не удалось изменить автозапуск" });
              root.App.refresh();
            }
          });
        }))
    ]);
    remind.appendChild(remindGrid);
    wrap.appendChild(remind);
    wrap.appendChild(look);

    // =================================================================
    //  4. Тонкая настройка — свёрнута, чтобы не мешать
    // =================================================================
    const advancedOpen = !!state().ui.settingsAdvanced;
    const adv = h("div.card");
    adv.appendChild(
      h("button.adv-toggle", {
        onclick: () => {
          state().ui.settingsAdvanced = !state().ui.settingsAdvanced;
          root.Store.save();
          root.App.refresh();
        }
      }, [
        UI.icon(advancedOpen ? "chevronDown" : "chevronRight"),
        h("span", "Тонкая настройка"),
        h("span.muted", { style: { fontSize: "12px", fontWeight: "400" } },
          advancedOpen ? "для тех, кто хочет всё под контролем" : "коэффициенты, интервалы, потолки")
      ])
    );

    if (advancedOpen) {
      adv.appendChild(
        h("div.settings-grid", [
          settingsRow(
            "Считать в знаках",
            "По умолчанию скорость считается в словах. Редакторы и корректоры чаще считают в знаках — можно переключить.",
            switchControl("unit", s.unit === "cpm", (on) => setSetting("unit", on ? "cpm" : "wpm"), "знаки", "слова")
          ),
          s.unit === "cpm"
            ? settingsRow("Знаков в минуту", "Средняя скорость чтения вслух — около 900–1200 знаков в минуту.",
              UI.stepper(s.charsPerMinute, { min: 300, max: 4000, step: 50, onChange: (v) => setSetting("charsPerMinute", v) }))
            : null,
          settingsRow(
            "Повторное чтение быстрее в",
            "Во сколько раз быстрее вы читаете уже знакомый ответ. 1,5 — обычное значение, 2 — если помните почти всё.",
            h("div.row", [
              UI.stepper(Math.round(s.reviewSpeedFactor * 10), {
                min: 10,
                max: 30,
                onChange: (v) => setSetting("reviewSpeedFactor", v / 10)
              }),
              h("span.muted", { style: { fontSize: "12px" } }, "раз")
            ])
          ),
          settingsRow(
            "Когда начинать повторять",
            "Через какую долю срока до экзамена ставить первое повторение. Исследования дают оптимум 10–20 %: слишком рано — забудете, слишком поздно — не успеете закрепить.",
            minuteChips()
          ),
          settingsRow(
            "Прогонов для новых файлов",
            "Сколько раз прочитать файл по умолчанию. 3 — разумный минимум для экзамена. У каждой дисциплины это можно поменять отдельно.",
            UI.stepper(s.defaultPasses || 3, { min: 1, max: 10, onChange: (v) => setSetting("defaultPasses", v) })
          ),
          settingsRow(
            "Как распределять новые файлы",
            "Равномерно — весь объём делится на дни. По вопросам — фиксированное число новых в день. По минутам — фиксированное время.",
            modeControl()
          ),
          settingsRow(
            "Потолок дня на дисциплину",
            "Жёсткий предел минут в день на одну дисциплину. 0 — без предела. Нужен редко; обычно достаточно предела на день выше.",
            UI.stepper(s.dailyCapMinutes, { min: 0, max: 960, step: 10, onChange: (v) => setSetting("dailyCapMinutes", v) })
          )
        ])
      );
    }
    wrap.appendChild(adv);

    // =================================================================
    //  5. Данные
    // =================================================================
    const data = h("div.card");
    data.appendChild(h("div.card-title", [h("h2", "Данные")]));
    data.appendChild(
      h("div.settings-grid", [
        settingsRow("Резервная копия", "Сохранить всю библиотеку в файл — пригодится при переносе на другой компьютер.",
          h("div.row", [
            UI.button("Сохранить копию", { size: "sm", icon: "export", onClick: () => root.App.exportBackup() }),
            UI.button("Открыть папку", { size: "sm", kind: "ghost", icon: "folder", onClick: () => root.App.openDataDir() })
          ])),
        settingsRow("Занято на диске", "Библиотека и копии добавленных файлов.", h("span.mono", { id: "storageInfo" }, "…")),
        settingsRow(
          "Версия и сборка",
          "Приложение само проверяет обновления раз в минуту и спросит перед установкой.",
          h("div.row", [
            h("span.mono", { id: "versionInfo" }, "…"),
            UI.button("Проверить обновление", {
              size: "sm",
              kind: "ghost",
              icon: "reset",
              onClick: async () => {
                if (!root.api || !root.api.update) {
                  UI.toast({ kind: "info", title: "Проверка недоступна", text: "Обновления проверяются только в установленной программе." });
                  return;
                }
                UI.toast({ kind: "info", title: "Проверяем…", text: "Спрашиваем GitHub о новой сборке." });
                const st = await root.api.update.check();
                if (!st || !st.available) {
                  UI.toast({
                    kind: "ok",
                    title: "У вас последняя версия",
                    text: st && st.error ? "GitHub не ответил: " + st.error : "Новых сборок нет."
                  });
                }
              }
            })
          ])
        )
      ])
    );
    wrap.appendChild(data);

    setTimeout(async () => {
      try {
        if (root.api && root.api.info) {
          const info = await root.api.info();
          const v = document.getElementById("versionInfo");
          if (v) {
            const parts = [info.version];
            if (info.build) parts.push("сборка " + info.build);
            else if (info.electron) parts.push("Electron " + info.electron);
            v.textContent = parts.join(" · ");
          }
        }
        if (root.api && root.api.storageStats) {
          const st = await root.api.storageStats();
          const el = document.getElementById("storageInfo");
          if (el) el.textContent = fmtBytes(st.textsBytes + st.libraryBytes);
        }
      } catch (e) {
        /* сведения не критичны */
      }
    }, 30);

    return wrap;
  }

  /** Строка «что получится» на экране настроек. */
  function outcomeLine(label, value) {
    return h("div.outcome-line", [
      h("span.muted", label),
      h("b", value)
    ]);
  }

  /** Когда закончится подготовка при текущем плане. */
  function finishLine(planData) {
    let last = null;
    for (const date of Object.keys(planData.combined)) {
      if (planData.combined[date] && planData.combined[date].length) {
        if (!last || date > last) last = date;
      }
    }
    if (!last) return "пока нечего планировать";
    const exam = nearestExam();
    const rel = UI.relativeDay(last);
    if (exam && last <= exam) return UI.dateShort(last) + " — " + rel;
    return UI.dateShort(last) + " — позже экзамена";
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
    // Три экрана: что читать сегодня, дисциплины и настройки. Обзор и
    // дисциплина — это части двух первых, отдельных пунктов меню им не нужно.
    dashboard: viewDashboard,
    today: viewToday,
    disciplines: viewDisciplines,
    discipline: viewDiscipline,
    settings: viewSettings,
    plan,
    accentOf,
    groupTodayTasks,
    taskRow,
    sparkleBurst,
  };
})(typeof window !== "undefined" ? window : globalThis);
