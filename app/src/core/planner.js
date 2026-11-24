/*
 * planner.js — движок планирования.
 * Считает время на каждый вопрос, распределяет нагрузку по дням,
 * поддерживает несколько прогонов (прочитать файл N раз),
 * глобальный бюджет (готовиться ко всем понемногу) и пересчёт при изменении прогресса.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof window !== "undefined") window.ExamCore = Object.assign(window.ExamCore || {}, { planner: api });
})(typeof self !== "undefined" ? self : this, function () {
  // ---------- Работа с датами (без часовых поясов) ----------
  function parseDate(s) {
    const [y, m, d] = s.split("-").map(Number);
    return new Date(y, m - 1, d);
  }
  function fmtDate(dt) {
    return (
      dt.getFullYear() +
      "-" +
      String(dt.getMonth() + 1).padStart(2, "0") +
      "-" +
      String(dt.getDate()).padStart(2, "0")
    );
  }
  function addDays(s, n) {
    const dt = parseDate(s);
    dt.setDate(dt.getDate() + n);
    return fmtDate(dt);
  }
  function daysBetween(a, b) {
    return Math.round((parseDate(b) - parseDate(a)) / 86400000);
  }
  function weekday(s) {
    return parseDate(s).getDay(); // 0=Вс .. 6=Сб
  }
  // Список активных дней в [start, end] исключая restDays (массив 0..6).
  function listActiveDays(start, end, restDays) {
    restDays = restDays || [];
    const out = [];
    let cur = start;
    let guard = 0;
    while (cur <= end && guard < 5000) {
      if (!restDays.includes(weekday(cur))) out.push(cur);
      cur = addDays(cur, 1);
      guard++;
    }
    return out;
  }

  // ---------- Построение единиц работы ----------
  // Каждая "единица" = прочтение одного вопроса в одном из прогонов.
  function buildUnits(disc, settings) {
    const unit = settings.speedUnit || "wpm";
    const rate = unit === "cpm" ? settings.charsPerMinute : settings.wordsPerMinute;
    const assumeWords = disc.plan.assumeAnswerWords || 0;
    const reviewFactor = disc.plan.reviewSpeedFactor || 1; // >1 → повторение быстрее
    const passes = Math.max(1, disc.plan.passes || 1);
    const units = [];
    for (let p = 1; p <= passes; p++) {
      const speedMul = p === 1 ? 1 : Math.max(0.2, reviewFactor);
      disc.questions.forEach((q, qi) => {
        const words = q.qWords + (q.aWords > 0 ? q.aWords : assumeWords);
        const chars = q.qChars + (q.aChars > 0 ? q.aChars : Math.round(assumeWords * 6.5));
        const minutes = Math.max(0.05, textstatsMinutes(words, chars, unit, rate) / speedMul);
        units.push({ qIndex: qi, pass: p, minutes, words, chars });
      });
    }
    return units;

    function textstatsMinutes(w, c, u, r) {
      return u === "cpm" ? c / Math.max(1, r) : w / Math.max(1, r);
    }
  }

  function doneSet(disc) {
    const set = new Set();
    const prog = disc.progress || {};
    for (const k of Object.keys(prog)) {
      if (prog[k] && prog[k].done) set.add(k);
    }
    return set;
  }
  function unitKey(u) {
    return u.qIndex + ":" + u.pass;
  }

  // ---------- Планирование одной дисциплины (режимы questions / minutes) ----------
  function scheduleSingle(disc, settings, today) {
    const plan = disc.plan;
    const all = buildUnits(disc, settings);
    const done = doneSet(disc);
    const undone = all.filter((u) => !done.has(unitKey(u)));

    const start = plan.startDate > today ? plan.startDate : today;
    const end = plan.examDate;
    if (parseDate(end) < parseDate(start)) {
      return { error: "examBeforeStart", schedule: {}, stats: emptyStats(all, undone) };
    }
    const days = listActiveDays(start, end, plan.restDays || []);
    if (days.length === 0) {
      return { error: "noActiveDays", schedule: {}, stats: emptyStats(all, undone) };
    }

    const sched = {};
    days.forEach((d) => (sched[d] = []));
    const mode = plan.mode || "questions";
    let behind = false;
    let overloaded = false;
    let perDayTarget = 0;
    const warnings = [];

    if (mode === "questions") {
      const userPerDay = Math.max(1, plan.perDayQuestions || 1);
      // Сколько нужно в день, чтобы гарантированно успеть к последнему дню.
      const neededPerDay = Math.ceil(undone.length / days.length);
      perDayTarget = Math.max(userPerDay, neededPerDay);
      // Если нужная норма нереалистична — помечаем как "невозможно".
      behind = neededPerDay > 250;
      let adjusted = neededPerDay > userPerDay; // автоматически повышаем норму, чтобы успеть
      let i = 0,
        di = 0;
      while (i < undone.length && di < days.length) {
        const cap = di === days.length - 1 ? undone.length - i : perDayTarget;
        const take = undone.slice(i, i + cap);
        sched[days[di]].push(...take);
        i += cap;
        di++;
      }
      if (adjusted && !behind) {
        warnings.push({
          disciplineId: disc.id,
          type: "adjusted",
          text: `Чтобы успеть к ${end}, нужно минимум ${neededPerDay} вопр./день. Ваша норма (${userPerDay}) недостаточна — расписание автоматически увеличено.`
        });
      }
    } else if (mode === "minutes") {
      const budget = Math.max(0.1, plan.perDayMinutes || 30);
      let i = 0,
        di = 0;
      while (i < undone.length && di < days.length) {
        let sum = 0;
        while (i < undone.length && sum + undone[i].minutes <= budget + 1e-6) {
          sched[days[di]].push(undone[i]);
          sum += undone[i].minutes;
          i++;
        }
        if (i < undone.length && sched[days[di]].length === 0) {
          // одна единица длиннее бюджета — ставим принудительно
          sched[days[di]].push(undone[i]);
          sum += undone[i].minutes;
          i++;
          overloaded = true;
        }
        if (sum > budget + 1e-6) overloaded = true;
        di++;
      }
      behind = i < undone.length;
    }

    const stats = {
      totalUnits: all.length,
      doneUnits: all.length - undone.length,
      remainingUnits: undone.length,
      daysAvailable: days.length,
      perDayTarget,
      behind,
      overloaded
    };
    return { schedule: sched, stats, days, warnings };
  }

  function emptyStats(all, undone) {
    return {
      totalUnits: all.length,
      doneUnits: all.length - undone.length,
      remainingUnits: undone.length,
      daysAvailable: 0,
      perDayTarget: 0,
      behind: false,
      overloaded: false
    };
  }

  // ---------- Глобальный бюджет (режим global): готовимся ко всем понемногу ----------
  function scheduleGlobal(discs, settings, today) {
    const budget = Math.max(1, settings.global ? settings.global.dailyMinutes : 60);
    // Собираем недоделанные юниты по каждой дисциплине.
    const buckets = discs.map((d) => {
      const all = buildUnits(d, settings);
      const done = doneSet(d);
      const undone = all.filter((u) => !done.has(unitKey(u)));
      const start = d.plan.startDate > today ? d.plan.startDate : today;
      const end = d.plan.examDate;
      return { d, undone, start, end };
    });
    const active = buckets.filter((b) => b.undone.length > 0);
    if (active.length === 0) return { schedule: {}, days: [] };

    // Окно планирования — пересечение всех окон.
    let start = active.reduce((a, b) => (b.start > a ? b.start : a), active[0].start);
    let end = active.reduce((a, b) => (b.end < a ? b.end : a), active[0].end);
    if (parseDate(end) < parseDate(start)) end = start;

    const restUnion = Array.from(
      new Set(active.flatMap((b) => b.d.plan.restDays || []))
    );
    const days = listActiveDays(start, end, restUnion);
    const sched = {};
    days.forEach((d) => (sched[d] = []));
    if (days.length === 0) return { schedule: {}, days };

    let di = 0;
    while (di < days.length) {
      const day = days[di];
      let remaining = budget;
      const share = budget / active.length;
      let anyLeft = active.some((b) => b.undone.length > 0);
      if (!anyLeft) break;
      let progress = false;
      for (const b of active) {
        if (b.undone.length === 0) continue;
        let discSum = 0;
        while (
          b.undone.length > 0 &&
          discSum + b.undone[0].minutes <= share + 1e-6 &&
          remaining - b.undone[0].minutes >= -1e-6
        ) {
          const u = b.undone.shift();
          sched[day].push({ discId: b.d.id, ...u });
          discSum += u.minutes;
          remaining -= u.minutes;
          progress = true;
        }
      }
      // Если за день не влезло ни одной единицы (все слишком длинные) — форсируем одну.
      if (!progress) {
        const b = active.find((x) => x.undone.length > 0);
        if (b) {
          const u = b.undone.shift();
          sched[day].push({ discId: b.d.id, ...u });
        } else break;
      }
      di++;
    }
    const remaining = active.reduce((acc, b) => acc + b.undone.length, 0);
    return { schedule: sched, days, remaining };
  }

  // ---------- Верхнеуровневый расчёт по всему состоянию ----------
  // state: { settings, disciplines:[...] }
  function computeAll(state, today) {
    today = today || fmtDate(new Date());
    const settings = state.settings;
    const discs = state.disciplines || [];

    const perDisc = {};
    const globalDiscs = [];
    let combined = {}; // date -> [unit...]

    for (const d of discs) {
      if (d.plan.mode === "global") {
        globalDiscs.push(d);
        perDisc[d.id] = { schedule: {}, stats: singleStats(d, settings), global: true };
      } else {
        const r = scheduleSingle(d, settings, today);
        perDisc[d.id] = r;
        for (const date of Object.keys(r.schedule)) {
          if (!combined[date]) combined[date] = [];
          for (const u of r.schedule[date]) combined[date].push({ discId: d.id, ...u });
        }
      }
    }

    if (globalDiscs.length > 0) {
      const g = scheduleGlobal(globalDiscs, settings, today);
      perDisc.__global = { schedule: g.schedule, days: g.days };
      for (const date of Object.keys(g.schedule)) {
        if (!combined[date]) combined[date] = [];
        combined[date].push(...g.schedule[date]);
      }
    }

    // Итоги и предупреждения.
    const warnings = [];
    for (const d of discs) {
      const r = perDisc[d.id];
      if (!r) continue;
      if (r.warnings) warnings.push(...r.warnings);
      if (r.error) {
        warnings.push({ disciplineId: d.id, type: r.error, text: errorText(r.error, d) });
      } else if (r.stats && r.stats.behind) {
        warnings.push({
          disciplineId: d.id,
          type: "behind",
          text: `По дисциплине «${d.name}» даже при максимальной норме не успеть к ${d.plan.examDate}. Уменьшите число прогонов или сдвиньте дату экзамена.`
        });
      } else if (r.stats && r.stats.overloaded) {
        warnings.push({
          disciplineId: d.id,
          type: "overloaded",
          text: `По дисциплине «${d.name}» дневной лимит времени превышен — некоторые вопросы дольше лимита.`
        });
      }
    }

    // Глобальный бюджет: проверяем, не остались ли незапланированные юниты.
    if (globalDiscs.length > 0) {
      const g = perDisc.__global;
      if (g && g.days && g.days.length > 0 && g.remaining > 0) {
        warnings.push({
          type: "global-short",
          text: `При глобальном бюджете ${settings.global.dailyMinutes} мин/день весь материал не помещается до экзамена. Увеличьте бюджет или сдвиньте даты. Осталось вне расписания: ${g.remaining} единиц.`
        });
      }
    }

    return {
      today,
      perDisc,
      combined,
      warnings,
      todayTasks: combined[today] || []
    };
  }

  function singleStats(disc, settings) {
    const all = buildUnits(disc, settings);
    const done = doneSet(disc);
    const undone = all.filter((u) => !done.has(unitKey(u)));
    return emptyStats(all, undone);
  }

  function errorText(type, d) {
    if (type === "examBeforeStart")
      return `У дисциплины «${d.name}» дата экзамена раньше даты начала.`;
    if (type === "noActiveDays")
      return `У дисциплины «${d.name}» не осталось активных дней (проверьте выходные).`;
    return "Ошибка планирования.";
  }

  // Процент готовности дисциплины (по прочитанным единицам).
  function completion(disc, settings) {
    const all = buildUnits(disc, settings);
    if (all.length === 0) return 0;
    const done = doneSet(disc);
    const doneCount = all.filter((u) => done.has(unitKey(u))).length;
    return doneCount / all.length;
  }

  return {
    parseDate,
    fmtDate,
    addDays,
    daysBetween,
    weekday,
    listActiveDays,
    buildUnits,
    scheduleSingle,
    scheduleGlobal,
    computeAll,
    completion,
    unitKey,
    doneSet
  };
});
