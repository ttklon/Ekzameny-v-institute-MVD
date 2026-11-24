/*
 * app.js — управление приложением.
 *
 * Здесь: навигация между экранами, меню, перетаскивание файлов, окно импорта,
 * просмотр вопроса, экспорт плана. Логика расчётов — в src/core, отрисовка —
 * в views.js; этот файл связывает их и следит за общим состоянием.
 */
(function (root) {
  "use strict";

  const UI = root.UI;
  const h = UI.h;
  const P = root.ExamCore.planner;

  const VIEWS = [
    { id: "dashboard", label: "Обзор", icon: "dashboard", title: "Обзор", sub: "Готовность, работа на сегодня и ближайшие дни" },
    { id: "today", label: "Сегодня", icon: "today", title: "Сегодня", sub: "Что читать и что уже отмечено" },
    { id: "disciplines", label: "Дисциплины", icon: "library", title: "Дисциплины", sub: "Все загруженные файлы и их планы" },
    { id: "calendar", label: "Календарь", icon: "calendar", title: "Календарь", sub: "Нагрузка по дням до экзаменов" },
    { id: "stats", label: "Статистика", icon: "stats", title: "Статистика", sub: "Объёмы, время и прогресс" },
    { id: "tips", label: "Как готовиться", icon: "tips", title: "Как готовиться", sub: "Что помогает запоминать — и как это учтено в плане" },
    { id: "settings", label: "Настройки", icon: "settings", title: "Настройки", sub: "Скорость чтения, оформление, данные" }
  ];

  const app = {
    current: "dashboard",
    params: {},
    importing: false,
    ready: false
  };

  // ---------- Навигация ----------

  function go(view, params) {
    if (!root.Views[view]) view = "dashboard";
    const changed = app.current !== view || JSON.stringify(app.params) !== JSON.stringify(params || {});
    app.current = view;
    app.params = params || {};
    if (view === "today" && params && params.date) {
      // date передаётся в экран дня через параметры
    }
    root.Store.update(
      (s) => {
        s.ui.view = view;
        if (params && params.id) s.ui.selectedDiscipline = params.id;
      },
      { what: "navigation", save: false }
    );
    render();
    if (changed) root.Sound.play("whoosh");
    const scroller = document.getElementById("view");
    if (scroller) scroller.scrollTop = 0;
  }

  function refresh() {
    render();
  }

  /** Полная перерисовка: панель, заголовок и текущий экран. */
  function render() {
    if (!app.ready) return;
    const s = root.Store.state;
    renderNav();
    renderTopbar();

    const view = document.getElementById("view");
    if (!view) return;
    UI.clear(view);
    const fn = root.Views[app.current] || root.Views.dashboard;
    let el;
    try {
      el = fn(app.params);
    } catch (err) {
      console.error("view failed", err);
      el = h("div.card", [
        h("div.empty", [
          h("div.empty-icon", [UI.icon("warn")]),
          h("h3", "Не удалось показать экран"),
          h("p", String(err && err.message ? err.message : err))
        ])
      ]);
    }
    el.classList.add("view-enter");
    view.appendChild(el);
    renderSidefoot();
  }

  function renderNav() {
    const nav = document.getElementById("nav");
    if (!nav) return;
    UI.clear(nav);
    const planData = root.Views.plan();
    for (const v of VIEWS) {
      const badge = navBadgeFor(v.id, planData);
      const btn = h("button.nav-item" + (app.current === v.id ? ".active" : ""), {
        onclick: () => go(v.id),
        onmouseenter: () => root.Sound.play("tick"),
        title: v.title
      }, [
        h("span.ni", [UI.icon(v.icon)]),
        h("span", v.label),
        badge != null ? h("span.nav-badge", String(badge)) : null
      ]);
      nav.appendChild(btn);
    }
  }

  function navBadgeFor(viewId, planData) {
    if (viewId === "today") {
      const tasks = root.Views.groupTodayTasks(planData.todayTasks);
      return tasks.length || null;
    }
    if (viewId === "disciplines") {
      const n = root.Store.activeDisciplines().length;
      return n || null;
    }
    return null;
  }

  function renderTopbar() {
    const v = VIEWS.find((x) => x.id === app.current) || VIEWS[0];
    const title = document.getElementById("viewTitle");
    const sub = document.getElementById("viewSub");
    if (title) title.textContent = v.title;
    if (sub) sub.textContent = subFor(v);

    const pill = document.getElementById("todayPill");
    if (pill) {
      const d = new Date();
      const wd = UI.WEEKDAYS[(d.getDay() + 6) % 7];
      pill.textContent = d.getDate() + " " + UI.MONTHS[d.getMonth()] + ", " + wd;
    }
  }

  function subFor(v) {
    if (v.id === "dashboard") {
      const planData = root.Views.plan();
      const n = root.Store.activeDisciplines().length;
      if (!n) return "Добавьте файл с вопросами — программа посчитает объём и распределит подготовку";
      const left = P.daysBetween(P.todayStr(), nearestExam() || P.todayStr());
      const examText = nearestExam() ? "до ближайшего экзамена " + left + " " + UI.plural(left, "день", "дня", "дней") : "даты экзаменов не заданы";
      return n + " " + UI.plural(n, "дисциплина", "дисциплины", "дисциплин") + " · " + examText;
    }
    if (v.id === "disciplines" || v.id === "discipline") {
      const disc = root.Store.getDiscipline(app.params.id || root.Store.state.ui.selectedDiscipline);
      if (disc) {
        return disc.questions.length + " " + UI.plural(disc.questions.length, "вопрос", "вопроса", "вопросов") +
          " · " + UI.dur(P.totalMinutes(disc, root.Store.state.settings)) + " на " +
          disc.plan.passes + " " + UI.plural(disc.plan.passes, "прогон", "прогона", "прогонов");
      }
    }
    if (v.id === "today") {
      const planData = root.Views.plan();
      const tasks = root.Views.groupTodayTasks(planData.todayTasks);
      if (!tasks.length) return "На сегодня ничего не запланировано — можно отдохнуть или забежать вперёд";
      return tasks.length + " " + UI.plural(tasks.length, "вопрос", "вопроса", "вопросов") +
        " · " + UI.dur(planData.todayMinutes) + " чтения";
    }
    return v.sub;
  }

  function nearestExam() {
    let best = null;
    for (const d of root.Store.activeDisciplines()) {
      if (d.plan && P.isValidDate(d.plan.examDate)) {
        if (!best || d.plan.examDate < best) best = d.plan.examDate;
      }
    }
    return best;
  }

  function renderSidefoot() {
    const planData = root.Views.plan();
    const pct = planData.totals.progress * 100;
    const val = document.getElementById("sideValue");
    const bar = document.getElementById("sideBar");
    const sub = document.getElementById("sideSub");
    if (val) UI.animateNumber(val, pct, { suffix: "%", duration: 700 });
    if (bar) bar.style.width = pct + "%";
    if (sub) {
      const n = root.Store.activeDisciplines().length;
      if (!n) sub.textContent = "нет дисциплин";
      else {
        const left = planData.totals.minutesLeft;
        sub.textContent = left > 0 ? "осталось " + UI.dur(left) : "всё распределено";
      }
    }
  }

  // ---------- Импорт ----------

  function openImport() {
    if (app.importing) return;
    app.importing = true;

    const stage = h("div.import-steps");
    const modal = UI.openModal({
      title: "Добавить файл",
      subtitle: "TXT, DOCX, PDF, ODT, RTF — вопросы и ответы находятся автоматически",
      wide: true,
      body: stage,
      footer: [
        h("span.muted", { style: { fontSize: "12px" } }, "Файлы можно просто перетащить в окно программы"),
        h("div.spacer")
      ],
      onClose: () => {
        app.importing = false;
      }
    });

    const picker = h("div", { style: { display: "grid", gap: "12px" } }, [
      h("div", { style: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" } }, [
        UI.button("Выбрать файлы…", {
          kind: "primary",
          icon: "file",
          onClick: async () => {
            const files = await root.api.openFiles();
            if (files.length) await importFiles(files, modal, stage);
          }
        }),
        UI.button("Выбрать папку…", {
          icon: "import",
          onClick: async () => {
            const res = await root.api.openFolder();
            if (!res.dir) return;
            if (!res.files.length) {
              UI.toast({ kind: "warn", text: "В папке нет подходящих файлов." });
              return;
            }
            await importFiles(res.files, modal, stage);
          }
        })
      ]),
      h("div.warn-box.info", [
        UI.icon("info"),
        h("div", [
          h("b", { style: { display: "block", marginBottom: "3px" } }, "Что программа понимает"),
          h("span",
            "Нумерованные вопросы «1. …», заголовки «Вопрос 12. …», перечни вопросов с ответами ниже, " +
            "файлы по одному вопросу и большие сборники «Все ответы 001–149». " +
            "Если ответа нет, объём оценивается и это видно в списке.")
        ])
      ])
    ]);
    stage.appendChild(picker);
  }

  async function importFiles(paths, modal, stage) {
    const results = [];
    UI.clear(stage);
    stage.appendChild(
      h("div.loader", [
        h("div.loader-ring"),
        h("div", { style: { fontWeight: "600" } }, "Разбираем файлы…"),
        h("div.muted", { id: "importProgressText", style: { fontSize: "12.5px" } }, "0 из " + paths.length),
        h("div.progress-line", [h("i", { id: "importBar" })])
      ])
    );

    for (let i = 0; i < paths.length; i++) {
      const bar = document.getElementById("importBar");
      const txt = document.getElementById("importProgressText");
      if (bar) bar.style.width = ((i / paths.length) * 100).toFixed(0) + "%";
      if (txt) txt.textContent = (i + 1) + " из " + paths.length + " · " + shortName(paths[i]);
      const r = await root.api.readFile(paths[i]);
      results.push(r);
    }
    const bar = document.getElementById("importBar");
    if (bar) bar.style.width = "100%";

    UI.clear(stage);
    stage.appendChild(importResults(results, modal, stage));
    const ok = results.filter((r) => r.ok && r.parsed && r.parsed.count > 0);
    if (ok.length) root.Sound.play("import");
  }

  function shortName(p) {
    const parts = String(p).split(/[\\/]/);
    return parts[parts.length - 1];
  }

  /** Экран результатов разбора: что найдено и кнопка «добавить». */
  function importResults(results, modal, stage) {
    const wrap = h("div.import-result");
    const good = results.filter((r) => r.ok && r.parsed && r.parsed.count > 0);
    const bad = results.filter((r) => !r.ok || !r.parsed || !r.parsed.count);

    const selected = new Set(good.map((_, i) => i));
    const names = new Map();

    // Много файлов подряд (папка с «q001.txt … q149.txt») — это одна дисциплина,
    // а не сто сорок девять. Режим можно переключить.
    const manyFiles = good.length >= 3;
    let groupMode = manyFiles;
    const groupName = commonGroupName(good);

    if (!good.length) {
      wrap.appendChild(
        h("div.warn-box.error", [
          UI.icon("warn"),
          h("div", [
            h("b", { style: { display: "block", marginBottom: "3px" } }, "Не удалось разобрать файлы"),
            h("span", bad[0] && (bad[0].error || (bad[0].parsed && bad[0].parsed.warnings.map((w) => w.text).join(" "))) || "Проверьте формат файла.")
          ])
        ])
      );
      wrap.appendChild(
        h("div.row", [
          UI.button("Попробовать другой файл", { kind: "primary", onClick: () => {
            modal.close();
            setTimeout(openImport, 260);
          } })
        ])
      );
      return wrap;
    }

    const list = h("div", { style: { display: "grid", gap: "10px" } });

    const groupBox = h("div.warn-box.info", { style: { alignItems: "center" } });
    function paintGroupBox() {
      UI.clear(groupBox);
      groupBox.appendChild(UI.icon(groupMode ? "library" : "file"));
      groupBox.appendChild(
        h("div", { style: { flex: "1 1 auto" } }, [
          h("b", { style: { display: "block", marginBottom: "2px" } },
            groupMode
              ? "Одна дисциплина: «" + groupName + "»"
              : good.length + " " + UI.plural(good.length, "дисциплина", "дисциплины", "дисциплин")),
          h("span", { style: { fontSize: "12.5px" } },
            groupMode
              ? "Файлы " + good.length + " — вопросы сложатся в один список с общей датой экзамена и одним планом."
              : "Каждый файл станет отдельной дисциплиной со своим планом.")
        ])
      );
      groupBox.appendChild(
        UI.button(groupMode ? "Разделить по файлам" : "Объединить в одну", {
          kind: "ghost",
          onClick: () => {
            groupMode = !groupMode;
            paintGroupBox();
            paintList();
            root.Sound.play("tap");
          }
        })
      );
    }

    const listWrap = h("div", { style: { display: "grid", gap: "12px" } });

    function paintList() {
      UI.clear(listWrap);
      if (!groupMode) {
        listWrap.appendChild(list);
        return;
      }
      // Одна карточка на все файлы: суммарные цифры и общий предпросмотр.
      const totalQ = good.reduce((s, r) => s + r.parsed.count, 0);
      const totalW = good.reduce((s, r) => s + r.parsed.totalWords, 0);
      const totalC = good.reduce((s, r) => s + r.parsed.totalChars, 0);
      let mins = 0;
      for (const r of good) mins += readingMinutesOf(r.parsed);
      let answered = 0;
      for (const r of good) answered += r.parsed.answeredCount;

      const card = h("div", {
        style: {
          padding: "16px 18px",
          borderRadius: "16px",
          background: "rgba(255,255,255,.55)",
          border: "1px solid var(--glass-border)",
          display: "grid",
          gap: "10px"
        }
      });
      const nameInput = h("input.input", {
        value: groupName,
        style: { fontWeight: "600", fontSize: "15px" },
        oninput: (e) => {
          groupNameValue = e.target.value;
        }
      });
      card.appendChild(
        h("div.row", [
          h("span.tag.ok", "один план"),
          nameInput,
          h("span.tag", groupMode ? good.length + " " + UI.plural(good.length, "файл", "файла", "файлов") : "")
        ])
      );
      const row = h("div.stat-row");
      row.appendChild(miniStat("вопросов", UI.num(totalQ)));
      row.appendChild(miniStat("слов", UI.num(totalW)));
      row.appendChild(miniStat("знаков", UI.num(totalC)));
      row.appendChild(miniStat("чтение", UI.dur(mins)));
      if (answered < totalQ) row.appendChild(miniStat("без ответа", String(totalQ - answered)));
      card.appendChild(row);

      const fileList = h("div.file-list");
      for (const r of good) {
        fileList.appendChild(
          h("div.file-item", [
            h("span.fn", { title: r.name }, r.name),
            h("span.fq", r.parsed.count + " " + UI.plural(r.parsed.count, "вопрос", "вопроса", "вопросов"))
          ])
        );
      }
      card.appendChild(h("details", [
        h("summary", { style: { cursor: "pointer", fontSize: "12.5px", color: "var(--ink-soft)", fontWeight: "600" } },
          "показать " + good.length + " " + UI.plural(good.length, "файл", "файла", "файлов")),
        fileList
      ]));

      // Предупреждения — один раз, без повторов.
      const seen = new Set();
      for (const r of good) {
        for (const w of (r.warnings || []).concat(r.parsed.warnings || [])) {
          if (seen.has(w.text)) continue;
          seen.add(w.text);
          card.appendChild(h("div.warn-box", [UI.icon("info"), h("span", w.text)]));
        }
      }
      listWrap.appendChild(card);
    }
    let groupNameValue = groupName;

    good.forEach((r, i) => {
      const p = r.parsed;
      const card = h("div", {
        style: {
          padding: "14px 16px",
          borderRadius: "14px",
          background: "rgba(255,255,255,.5)",
          border: "1px solid var(--glass-border)",
          display: "grid",
          gap: "9px"
        }
      });

      const nameInput = h("input.input", {
        value: guessName(r.name),
        style: { fontWeight: "600" },
        oninput: (e) => names.set(i, e.target.value)
      });
      names.set(i, guessName(r.name));

      card.appendChild(
        h("div.row", [
          h("input", {
            type: "checkbox",
            checked: true,
            style: { width: "17px", height: "17px", accentColor: "var(--accent)" },
            onchange: (e) => {
              if (e.target.checked) selected.add(i);
              else selected.delete(i);
            }
          }),
          h("div", { style: { flex: "1 1 auto" } }, nameInput),
          h("span.tag", { title: "Как распознан файл" }, strategyLabel(p.strategy))
        ])
      );

      const row = h("div.stat-row");
      row.appendChild(miniStat("вопросов", UI.num(p.count)));
      row.appendChild(miniStat("слов", UI.num(p.totalWords)));
      row.appendChild(miniStat("знаков", UI.num(p.totalChars)));
      const mins = readingMinutesOf(p);
      row.appendChild(miniStat("чтение", UI.dur(mins)));
      if (p.answeredCount < p.count) row.appendChild(miniStat("без ответа", String(p.count - p.answeredCount)));
      card.appendChild(row);

      if (r.warnings && r.warnings.length) {
        for (const w of r.warnings) {
          card.appendChild(h("div.warn-box", [UI.icon("warn"), h("span", w.text)]));
        }
      }
      if (p.warnings && p.warnings.length) {
        for (const w of p.warnings) {
          card.appendChild(h("div.warn-box" + (w.type === "not-recognized" ? ".error" : ""), [
            UI.icon(w.type === "no-answers" || w.type === "partial-answers" ? "info" : "warn"),
            h("span", w.text)
          ]));
        }
      }

      // Предпросмотр первых вопросов
      const prev = h("div.preview-list");
      for (const q of p.questions.slice(0, 8)) {
        prev.appendChild(
          h("div.preview-item", [
            h("span.n", String(q.num)),
            h("span.t", { title: q.title }, q.title),
            h("span.w", UI.num(q.words) + " сл.")
          ])
        );
      }
      if (p.count > 8) {
        prev.appendChild(h("div.preview-item", [h("span.n", "…"), h("span.t.muted", "ещё " + (p.count - 8) + " " + UI.plural(p.count - 8, "вопрос", "вопроса", "вопросов")), h("span.w", "")]));
      }
      const details = h("details", [
        h("summary", { style: { cursor: "pointer", fontSize: "12.5px", color: "var(--ink-soft)", fontWeight: "600" } },
          "показать вопросы"),
        prev
      ]);
      details.querySelector("summary").addEventListener("click", () => root.Sound.play("page"));
      card.appendChild(details);
      list.appendChild(card);
    });
    wrap.appendChild(groupBox);
    wrap.appendChild(listWrap);
    paintGroupBox();
    paintList();

    if (bad.length) {
      for (const b of bad) {
        wrap.appendChild(
          h("div.warn-box.error", [
            UI.icon("warn"),
            h("div", [
              h("b", { style: { display: "block", marginBottom: "2px" } }, b.name || "файл"),
              h("span", b.error || "Не удалось разобрать: вопросов не найдено.")
            ])
          ])
        );
      }
    }

    const addBtn = UI.button("Добавить выбранные", {
      kind: "primary",
      icon: "plus",
      onClick: async () => {
        let added = 0;

        if (groupMode) {
          // Один общий файл: вопросы всех файлов по порядку номеров.
          const merged = [];
          const chosen = good.filter((_, i) => selected.has(i));
          for (const r of chosen) {
            for (const q of r.parsed.questions) merged.push(q);
          }
          // Номера могут повторяться — перенумеровываем по порядку.
          merged.forEach((q, idx) => (q.num = idx + 1));
          const combinedText = chosen.map((r) => r.text).join("\n\n");
          const id = root.Store.uid("disc");
          let textFile = "";
          try {
            const saved = await root.api.saveText(id, combinedText);
            if (saved && saved.ok) textFile = saved.name;
          } catch (e) {
            /* вопросы всё равно добавим */
          }
          root.Store.addDiscipline({
            id,
            name: (groupNameValue || "").trim() || "Дисциплина",
            fileName: chosen.length === 1 ? chosen[0].name : chosen.length + " файлов",
            filePath: chosen.length === 1 ? chosen[0].path : "",
            textFile,
            questions: merged,
            assumeAnswerWords: 250,
            parsing: {
              strategy: "merged",
              files: chosen.map((r) => r.name),
              count: merged.length,
              answered: merged.length,
              words: merged.reduce((s, q) => s + q.words, 0),
              chars: merged.reduce((s, q) => s + q.chars, 0),
              warnings: [],
              importedAt: new Date().toISOString()
            }
          });
          modal.close();
          root.Sound.play("complete");
          UI.toast({
            kind: "ok",
            title: "Добавлено",
            text: "«" + ((groupNameValue || "").trim() || "Дисциплина") + "»: " + merged.length +
              " " + UI.plural(merged.length, "вопрос", "вопроса", "вопросов") + " из " + chosen.length + " " +
              UI.plural(chosen.length, "файла", "файлов", "файлов") + ". Проверьте дату экзамена."
          });
          go("disciplines");
          return;
        }

        for (const i of Array.from(selected)) {
          const r = good[i];
          const name = (names.get(i) || "").trim() || guessName(r.name);
          const id = root.Store.uid("disc");
          let textFile = "";
          try {
            const saved = await root.api.saveText(id, r.text);
            if (saved && saved.ok) textFile = saved.name;
          } catch (e) {
            /* текст не сохранился — вопросы всё равно добавим */
          }
          root.Store.addDiscipline({
            id,
            name,
            fileName: r.name,
            filePath: r.path,
            textFile,
            questions: r.parsed.questions,
            assumeAnswerWords: 250,
            parsing: {
              strategy: r.parsed.strategy,
              count: r.parsed.count,
              answered: r.parsed.answeredCount,
              words: r.parsed.totalWords,
              chars: r.parsed.totalChars,
              warnings: (r.warnings || []).concat(r.parsed.warnings || []),
              importedAt: new Date().toISOString()
            }
          });
          added++;
        }
        modal.close();
        root.Sound.play("complete");
        UI.toast({
          kind: "ok",
          title: "Добавлено",
          text: added === 1 ? "Файл принят. Проверьте дату экзамена в настройках дисциплины." :
            added + " " + UI.plural(added, "файл", "файла", "файлов") + " приняты."
        });
        go("disciplines");
      }
    });
    wrap.appendChild(h("div.row", { style: { marginTop: "4px" } }, [addBtn]));
    return wrap;
  }

  function miniStat(k, v) {
    return h("div.mini-stat", [h("div.v", v), h("div.k", k)]);
  }

  function strategyLabel(s) {
    const map = {
      "markdown-headings": "заголовки",
      "question-headings": "заголовки вопросов",
      "single-question-file": "один вопрос",
      "list-and-answers": "перечень + ответы",
      "numbered-list": "нумерация",
      "numbered-with-answers": "нумерация + ответы",
      "question-lines": "вопросы со знаком «?»",
      "whole-document": "один документ",
      paragraphs: "абзацы"
    };
    return map[s] || "распознан";
  }

  /** Минуты чтения по результату разбора — при текущей скорости. */
  function readingMinutesOf(parsed) {
    const s = root.Store.state.settings;
    const unit = s.unit === "cpm" ? "cpm" : "wpm";
    const rate = unit === "cpm" ? s.charsPerMinute : s.wordsPerMinute;
    let sum = 0;
    for (const q of parsed.questions) {
      const base = unit === "cpm" ? q.chars : q.words;
      sum += (base * (q.difficulty || 1)) / Math.max(1, rate);
    }
    return sum;
  }

  /** Название дисциплины из имени файла: убираем расширение и служебные слова. */
  function guessName(fileName) {
    let n = String(fileName || "").replace(/\.[^.]+$/, "");
    n = n.replace(/[_\s]*(все\s+ответы|ответы\s+на\s+вопросы|примерный\s+перечень\s+вопросов)[^а-яёa-z]*$/i, "");
    n = n.replace(/^\d+[.)]\s*/, "");
    n = n.replace(/[_\s]+/g, " ").replace(/\s{2,}/g, " ").trim();
    n = n.replace(/^перечень вопросов к (экзамену|зачёту|зачету)\s*(по\s*)?/i, "");
    n = n.charAt(0).toUpperCase() + n.slice(1);
    if (!n) n = "Дисциплина";
    return n.slice(0, 90);
  }

  /**
   * Общее имя для группы файлов: у «q001.txt … q149.txt» в папке adp2 это
   * будет «adp2» по имени папки; у «adp2_q001» — «adp2» из имени файла.
   */
  function commonGroupName(results) {
    const dirs = results.map((r) => String(r.path || "").split(/[\\/]/).slice(0, -1).join("/"));
    const names = results.map((r) => guessName(r.name));
    // Общий префикс имён.
    let prefix = names[0] || "";
    for (const n of names) {
      let i = 0;
      while (i < prefix.length && i < n.length && prefix[i].toLowerCase() === n[i].toLowerCase()) i++;
      prefix = prefix.slice(0, i);
    }
    prefix = prefix.replace(/[\s_\-–—.]+$/, "").trim();
    if (prefix.length >= 3 && prefix.length < 70 && !/^[\d\s]+$/.test(prefix)) {
      return prefix.charAt(0).toUpperCase() + prefix.slice(1);
    }
    // Имя папки.
    const dirsUnique = Array.from(new Set(dirs));
    if (dirsUnique.length === 1 && dirsUnique[0]) {
      const parts = dirsUnique[0].split(/[\\/]/).filter(Boolean);
      const last = parts[parts.length - 1];
      if (last && last.length < 70) return last.charAt(0).toUpperCase() + last.slice(1);
    }
    return "Дисциплина из " + results.length + " " + UI.plural(results.length, "файла", "файлов", "файлов");
  }

  /** Импорт по путям (перетаскивание, меню, второй запуск). */
  async function importPaths(paths) {
    if (!paths || !paths.length) return;
    openImport();
    // Небольшая задержка, чтобы окно успело открыться.
    setTimeout(async () => {
      const stage = document.querySelector("#modal-root .import-steps");
      const modal = { close: () => UI.closeAllModals() };
      if (stage) await importFiles(paths, modal, stage);
    }, 120);
  }

  // ---------- Просмотр вопроса ----------

  async function openQuestion(discId, qIndex, date) {
    const d = root.Store.getDiscipline(discId);
    if (!d) return;
    const q = d.questions[qIndex];
    if (!q) return;
    const stq = P.questionState(d, qIndex, root.Store.state.settings);
    const day = date || P.todayStr();

    const body = h("div.question-view");
    body.appendChild(
      h("div.qv-head", [
        h("div.qv-num", String(q.num)),
        h("div", [
          h("div.qv-title", q.title),
          h("div.muted", { style: { fontSize: "12.5px", marginTop: "6px" } }, d.name)
        ])
      ])
    );

    body.appendChild(
      h("div.qv-stats", [
        h("span.tag", q.aWords + " " + UI.plural(q.aWords, "слово", "слова", "слов") + " в ответе"),
        h("span.tag", UI.num(q.chars) + " знаков"),
        h("span.tag", UI.dur(P.questionMinutes(d, q, 1, root.Store.state.settings)) + " чтения"),
        q.estimated ? h("span.tag.warn", "объём оценён") : null,
        h("span.tag" + (stq.done >= stq.passes ? ".ok" : ""), "прочитано " + stq.done + " из " + stq.passes)
      ])
    );

    // Текст ответа. Если сохранён полный текст файла — показываем ответ оттуда,
    // иначе — собранный парсером.
    let answerText = q.answer;
    if (!answerText && d.textFile) {
      try {
        const r = await root.api.loadText(d.textFile);
        if (r && r.ok) {
          const parsed = await root.api.parseText(r.text, 250);
          if (parsed && parsed.ok && parsed.parsed.questions[qIndex]) {
            answerText = parsed.parsed.questions[qIndex].answer;
          }
        }
      } catch (e) {
        /* останется пусто */
      }
    }

    body.appendChild(
      h("div.qv-text", answerText
        ? markdownish(answerText)
        : "Ответ не найден в файле — возможно, в нём только перечень вопросов.")
    );

    // Служебная информация о парсинге
    if (d.parsing) {
      body.appendChild(
        h("div.muted", { style: { fontSize: "11.5px", marginTop: "-6px" } },
          "Файл: " + (d.fileName || "—") + " · распознано как «" + strategyLabel(d.parsing.strategy) + "»")
      );
    }

    const reads = (d.reads && d.reads[String(qIndex)]) || [];
    const isRead = reads.indexOf(day) !== -1;

    const m = UI.openModal({
      title: "Вопрос " + q.num,
      subtitle: d.name,
      wide: true,
      body: body,
      footer: [
        UI.button(isRead ? "Снять отметку" : "Отметить прочитанным", {
          kind: isRead ? "ghost" : "primary",
          icon: isRead ? "reset" : "check",
          onClick: () => {
            root.Store.setRead(d.id, qIndex, day, !isRead);
            root.Sound.play(isRead ? "uncheck" : "check");
            if (!isRead) root.Views.sparkleBurst();
            m.close();
            refresh();
          }
        }),
        h("div.row", { style: { gap: "6px" } }, [
          h("span.muted", { style: { fontSize: "12px" } }, "другой день:"),
          h("input.input", {
            type: "date",
            value: day,
            style: { width: "160px", padding: "6px 10px", fontSize: "13px" },
            onchange: (e) => {
              const newDay = e.target.value;
              if (!P.isValidDate(newDay)) return;
              root.Store.setRead(d.id, qIndex, newDay, true);
              root.Sound.play("check");
              m.close();
              refresh();
            }
          })
        ]),
        h("div.spacer"),
        UI.button("Закрыть", { kind: "ghost", onClick: () => m.close() })
      ]
    });
  }

  /** Простая разметка ответа: абзацы, определения, перечни, выделения. */
  function markdownish(text) {
    const wrap = h("div");
    const lines = String(text || "").split("\n");
    let list = null;
    for (const raw of lines) {
      const line = raw.replace(/\s+$/, "");
      const trimmed = line.trim();
      if (!trimmed) {
        list = null;
        continue;
      }
      if (/^#{1,4}\s/.test(trimmed)) {
        list = null;
        wrap.appendChild(h("h4", inline(trimmed.replace(/^#{1,4}\s*/, ""))));
        continue;
      }
      if (/^[-*•]\s+/.test(trimmed)) {
        if (!list) {
          list = h("ul", { style: { paddingLeft: "18px", listStyle: "disc", display: "grid", gap: "4px", margin: "6px 0" } });
          wrap.appendChild(list);
        }
        list.appendChild(h("li", inline(trimmed.replace(/^[-*•]\s+/, ""))));
        continue;
      }
      if (/^>/.test(trimmed)) {
        list = null;
        wrap.appendChild(
          h("div", {
            style: {
              borderLeft: "3px solid var(--accent)",
              paddingLeft: "12px",
              margin: "8px 0",
              color: "var(--ink)"
            }
          }, inline(trimmed.replace(/^>\s*/, "")))
        );
        continue;
      }
      list = null;
      wrap.appendChild(h("p", { style: { margin: "6px 0" } }, inline(trimmed)));
    }
    return wrap;
  }

  /** Выделения **жирный** и //курсив// внутри строки. */
  function inline(text) {
    const frag = document.createDocumentFragment();
    const re = /(\*\*|__)(.+?)\1|\/\/(.+?)\/\//g;
    let last = 0;
    let m;
    while ((m = re.exec(text)) !== null) {
      if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
      if (m[2] !== undefined) {
        const b = document.createElement("b");
        b.textContent = m[2];
        frag.appendChild(b);
      } else {
        const i = document.createElement("i");
        i.textContent = m[3];
        frag.appendChild(i);
      }
      last = regexEnd(m);
    }
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
    return frag;
  }
  function regexEnd(m) {
    return m.index + m[0].length;
  }

  // ---------- Экспорт ----------

  function exportCsv() {
    const planData = root.Views.plan();
    const rows = [["Дата", "Дисциплина", "Вопрос", "Название", "Прогон", "Минут", "Слов"]];
    for (const date of Object.keys(planData.combined).sort()) {
      for (const t of planData.combined[date]) {
        const d = root.Store.getDiscipline(t.discId);
        const q = d && d.questions[t.qIndex];
        rows.push([
          date,
          csvCell(d ? d.name : ""),
          q ? q.num : "",
          csvCell(q ? q.title : ""),
          t.pass,
          t.minutes.toFixed(1),
          q ? q.words : ""
        ]);
      }
    }
    const csv = rows.map((r) => r.join(";")).join("\r\n");
    root.api.exportCsv(csv).then((r) => {
      if (r && r.ok) UI.toast({ kind: "ok", title: "План сохранён", text: r.path });
      else if (r && !r.canceled) UI.toast({ kind: "err", text: r.error || "Не удалось сохранить" });
    });
  }

  function csvCell(s) {
    const v = String(s || "").replace(/"/g, '""');
    return /[;"\n]/.test(v) ? '"' + v + '"' : v;
  }

  async function exportBackup() {
    const r = await root.api.exportBackup(root.Store.state);
    if (r && r.ok) UI.toast({ kind: "ok", title: "Копия сохранена", text: r.path });
    else if (r && !r.canceled) UI.toast({ kind: "err", text: r.error || "Не удалось сохранить" });
  }

  function openDataDir() {
    if (root.api && root.api.openDataDir) root.api.openDataDir();
  }

  function openExternal(url) {
    if (root.api && root.api.openExternal) root.api.openExternal(url);
    else window.open(url, "_blank");
  }

  // ---------- Перетаскивание ----------

  function setupDragDrop() {
    let depth = 0;
    const zone = document.getElementById("dropzone");

    window.addEventListener("dragenter", (e) => {
      if (!e.dataTransfer || !Array.from(e.dataTransfer.types || []).includes("Files")) return;
      depth++;
      zone.classList.add("on");
    });
    window.addEventListener("dragover", (e) => {
      e.preventDefault();
      if (e.dataTransfer) e.dataTransfer.dropEffect = "copy";
    });
    window.addEventListener("dragleave", (e) => {
      depth = Math.max(0, depth - 1);
      if (depth === 0) zone.classList.remove("on");
    });
    window.addEventListener("drop", async (e) => {
      e.preventDefault();
      depth = 0;
      zone.classList.remove("on");
      const files = Array.from((e.dataTransfer && e.dataTransfer.files) || []);
      const paths = [];
      for (const f of files) {
        // В Electron у файла есть реальный путь.
        const p = f.path || (root.api && root.api.getPathForFile ? root.api.getPathForFile(f) : null);
        if (p) paths.push(p);
      }
      if (paths.length) importPaths(paths);
      else UI.toast({ kind: "warn", text: "Не удалось получить путь к файлу — используйте кнопку «Добавить файл»." });
    });
  }

  // ---------- Горячие клавиши ----------

  function setupKeys() {
    document.addEventListener("keydown", (e) => {
      const inField = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement && document.activeElement.tagName);
      if (e.ctrlKey && e.key.toLowerCase() === "o") {
        e.preventDefault();
        openImport();
        return;
      }
      if (e.key === "Escape") {
        UI.closeAllModals();
        return;
      }
      if (inField) return;
      if (e.key === "1") go("dashboard");
      if (e.key === "2") go("today");
      if (e.key === "3") go("disciplines");
      if (e.key === "4") go("calendar");
      if (e.key === "5") go("stats");
    });
  }

  // ---------- Звук ----------

  function setupSound() {
    const btn = document.getElementById("soundBtn");
    const s = root.Store.state.settings;
    root.Sound.configure({ enabled: s.sound, volume: s.soundVolume });
    if (btn) {
      updateSoundBtn(btn, s.sound);
      btn.addEventListener("click", () => {
        const next = !root.Store.state.settings.sound;
        root.Store.state.settings.sound = next;
        root.Store.save();
        root.Sound.configure({ enabled: next });
        updateSoundBtn(btn, next);
        if (next) root.Sound.play("chime");
        UI.toast({
          kind: "info",
          text: next ? "Звуки включены" : "Звуки выключены",
          duration: 1800
        });
      });
    }
  }

  function updateSoundBtn(btn, on) {
    UI.clear(btn);
    btn.appendChild(UI.icon(on ? "volume" : "volumeOff"));
    btn.classList.toggle("off", !on);
    btn.title = on ? "Звук включён — нажмите, чтобы выключить" : "Звук выключен — нажмите, чтобы включить";
  }

  // ---------- Запуск ----------

  async function boot() {
    // Небо — первым, чтобы не было пустого фона.
    try {
      root.Sky.init(document.getElementById("sky"));
    } catch (e) {
      console.error("sky failed", e);
    }

    const loaded = await root.Store.load();
    if (loaded && loaded.recovered) {
      UI.toast({
        kind: "warn",
        title: "Восстановлена резервная копия",
        text: "Основной файл библиотеки был повреждён, данные взяты из последней копии."
      });
    }

    const s = root.Store.state.settings;
    document.body.classList.toggle("reduce-motion", !!s.reduceMotion);
    if (s.reduceMotion) root.Sky.stop();
    if (s.skyHour != null) root.Sky.setHour(s.skyHour);

    // Что-то изменилось в данных — перерисовываем.
    root.Store.subscribe((_state, what) => {
      if (what === "navigation") return;
      render();
    });

    app.ready = true;
    app.current = root.Store.state.ui.view || "dashboard";
    if (app.current === "discipline") app.params = { id: root.Store.state.ui.selectedDiscipline };

    render();
    setupSound();
    setupDragDrop();
    setupKeys();

    // Кнопка «добавить файл» в шапке.
    const impBtn = document.getElementById("importBtn");
    if (impBtn) {
      impBtn.appendChild(UI.icon("plus"));
      impBtn.addEventListener("click", openImport);
    }

    // Меню приложения.
    if (root.api && root.api.onMenu) {
      root.api.onMenu((action) => {
        if (action === "add-files") openImport();
        if (action === "add-folder") {
          openImport();
          setTimeout(async () => {
            const res = await root.api.openFolder();
            if (res.dir && res.files.length) importPaths(res.files);
          }, 200);
        }
        if (action === "backup") exportBackup();
        if (action === "help") go("tips");
      });
    }

    // Файлы из второго запуска (двойной щелчок по файлу в проводнике).
    if (root.api && root.api.onFilesDropped) {
      root.api.onFilesDropped((files) => importPaths(files));
    }
    if (root.api && root.api.takePendingFiles) {
      root.api.takePendingFiles().then((files) => {
        if (files && files.length) importPaths(files);
      });
    }

    // Первый запуск: подсказка.
    if (!root.Store.activeDisciplines().length) {
      setTimeout(() => {
        if (!root.Store.activeDisciplines().length && !app.importing) {
          UI.toast({
            kind: "info",
            title: "С чего начать",
            text: "Нажмите «Добавить файл» или просто перетащите файл с вопросами и ответами в окно.",
            duration: 8000
          });
        }
      }, 1400);
    }

    // Ночь и вечер: тёмная тема стекла.
    updateTheme();
    setInterval(updateTheme, 60000);

    // Сохранение при закрытии окна.
    window.addEventListener("beforeunload", () => {
      root.Store.flush();
    });
    setInterval(() => root.Store.flush(), 20000);
  }

  function updateTheme() {
    const hr = new Date().getHours();
    const s = root.Store.state.settings;
    const hour = s.skyHour != null ? s.skyHour : hr;
    const dusk = hour >= 19 || hour < 6;
    document.body.classList.toggle("theme-dusk", dusk);
  }

  root.App = {
    go,
    refresh,
    render,
    openImport,
    importPaths,
    openQuestion,
    exportCsv,
    exportBackup,
    openDataDir,
    openExternal
  };

  document.addEventListener("DOMContentLoaded", boot);
})(typeof window !== "undefined" ? window : globalThis);
