/*
 * planner.js — движок распределения подготовки.
 *
 * Что он делает
 * -------------
 * По каждому вопросу известно, сколько минут он занимает при вашей скорости
 * чтения. Дальше движок раскладывает работу по дням от даты начала до даты
 * экзамена так, чтобы:
 *   • каждый вопрос был прочитан нужное число раз (параметр «прогонов»);
 *   • повторные чтения шли по расширяющимся интервалам, а не подряд —
 *     это то, что называют распределённой практикой (spaced practice):
 *     повтор через 1 день, потом через 3, потом через 7 … но всегда с
 *     запасом до экзамена;
 *   • дневная нагрузка была ровной, а не «всё в последнюю неделю»;
 *   • при отметке прочитанного остаток пересчитывался автоматически.
 *
 * Режимы дневной нагрузки
 * -----------------------
 *   even      — делить весь оставшийся объём на оставшиеся дни (по умолчанию);
 *   questions — фиксированное число новых вопросов в день (например, 10);
 *   minutes   — фиксированное число минут в день (например, 45);
 *   global    — общий бюджет на все дисциплины: каждый день понемногу из каждой.
 *
 * Всё, что здесь считается, — чистые функции: одинаковый вход даёт одинаковый
 * выход, поэтому план можно пересчитывать при каждом изменении прогресса.
 */
(function (root, factory) {
  const deps =
    typeof module !== "undefined" && module.exports
      ? { text: require("./text") }
      : { text: (root.ExamCore || {}).text };
  const api = factory(deps.text);
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof window !== "undefined") {
    window.ExamCore = Object.assign(window.ExamCore || {}, { planner: api });
  }
})(typeof self !== "undefined" ? self : this, function (text) {
  "use strict";

  const DAY_MS = 86400000;

  // ---------- Даты (без часовых поясов, строка «ГГГГ-ММ-ДД») ----------

  function parseDate(s) {
    const p = String(s || "").split("-").map(Number);
    return new Date(p[0], (p[1] || 1) - 1, p[2] || 1);
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
  function todayStr(now) {
    return fmtDate(now || new Date());
  }
  function addDays(s, n) {
    const dt = parseDate(s);
    dt.setDate(dt.getDate() + n);
    return fmtDate(dt);
  }
  function daysBetween(a, b) {
    return Math.round((parseDate(b).getTime() - parseDate(a).getTime()) / DAY_MS);
  }
  function weekday(s) {
    return parseDate(s).getDay(); // 0 — воскресенье … 6 — суббота
  }
  function isValidDate(s) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(s || ""))) return false;
    const dt = parseDate(s);
    return isFinite(dt.getTime()) && fmtDate(dt) === s;
  }

  /** Активные дни в диапазоне [start, end] без отдыха. */
  function listActiveDays(start, end, restDays, plan) {
    const out = [];
    if (!isValidDate(start) || !isValidDate(end)) return out;
    // Если задана таблица по дням недели, она и решает: restDays — устаревшее
    // поле из старых сохранений и не должно спорить с ней.
    const hasTable = !!(plan && Array.isArray(plan.dayLoad) && plan.dayLoad.length === 7);
    const rest = hasTable ? [] : restDays || [];
    let cur = start;
    let guard = 0;
    while (cur <= end && guard < 4000) {
      const p = plan || { restDays: rest };
      if (rest.indexOf(weekday(cur)) === -1 && !isDayOff(p, cur)) out.push(cur);
      cur = addDays(cur, 1);
      guard++;
    }
    return out;
  }

  /**
   * Во сколько раз день недели тяжелее обычного.
   * plan.dayLoad — массив из 7 чисел по дням от понедельника (0) до воскресенья (6),
   * где 1 — обычная нагрузка, 0 — выходной, 2 — двойная. Пустые дни недели
   * считаются обычными, а дни из старого restDays — выходными.
   */
  function weekdayFactor(plan, dateStr) {
    // weekday() уже отдаёт 0 = воскресенье … 6 = суббота, как и dayLoad.
    // Вес дня — любое неотрицательное число: 0 (отдых), 1 (обычно),
    // 1.5, 3, 5 — «в этот день могу читать втрое больше». Верхней границы нет:
    // ограничивать человека нечем, он сам знает свой день.
    const wd = weekday(dateStr);
    const table = plan && plan.dayLoad;
    if (Array.isArray(table) && table.length === 7) {
      const v = Number(table[wd]);
      return isFinite(v) && v >= 0 ? Math.min(20, v) : 1;
    }
    const rest = (plan && plan.restDays) || [];
    return rest.indexOf(weekday(dateStr)) === -1 ? 1 : 0;
  }

  /** Дни, отмеченные как выходные (или нулевой нагрузкой). */
  function isDayOff(plan, dateStr) {
    return weekdayFactor(plan, dateStr) <= 0;
  }

  // ---------- Оценка времени ----------

  /**
   * Минуты на один вопрос при прогоне pass.
   * Первый прогон — полное время; повторные — быстрее (параметр reviewSpeedFactor).
   */
  function questionMinutes(disc, q, pass, globalSettings) {
    const settings = discSettings(disc, globalSettings);
    const unit = settings.unit === "cpm" ? "cpm" : "wpm";
    const rate = unit === "cpm" ? settings.charsPerMinute || 900 : settings.wordsPerMinute || 150;
    const factor = pass <= 1 ? 1 : Math.max(0.5, settings.reviewSpeedFactor || 1.5);
    // Повторное чтение идёт по краткому варианту ответа, если он есть:
    // по административной деятельности к каждому вопросу есть и подробный
    // ответ (первое чтение), и краткий (повторения). Считать повторение
    // по объёму подробного — значит завышать время вдвое.
    // Выбор человека главнее: «только подробно» — кратким не пользуемся
    // никогда, «только кратко» — наоборот, читаем краткий с первого раза.
    const variant = (disc && disc.answerVariant) || "auto";
    const altFits = variant === "short" ? true : variant === "full" ? false : pass > 1;
    const useAlt =
      altFits && (unit === "cpm" ? q.altChars > 0 : q.altWords > 0);
    const raw = unit === "cpm" ? (useAlt ? q.altChars : q.chars) : (useAlt ? q.altWords : q.words);
    const base = raw / Math.max(1, rate);
    return (base * (q.difficulty || 1)) / factor;
  }

  /**
   * Настройки чтения для конкретной дисциплины.
   *
   * У каждой дисциплины может быть своя скорость: юридический текст и конспект
   * читаются по-разному, и одна общая цифра тут только мешает. Если у
   * дисциплины ничего не задано — берутся общие настройки.
   */
  function discSettings(disc, globalSettings) {
    const g = globalSettings || {};
    const own = (disc && disc.reading) || null;
    if (!own) return g;
    const merged = Object.assign({}, g);
    if (own.unit === "cpm" || own.unit === "wpm") merged.unit = own.unit;
    if (own.wordsPerMinute > 0) merged.wordsPerMinute = own.wordsPerMinute;
    if (own.charsPerMinute > 0) merged.charsPerMinute = own.charsPerMinute;
    if (own.reviewSpeedFactor > 0) merged.reviewSpeedFactor = own.reviewSpeedFactor;
    return merged;
  }

  /** Полное время вопроса со всеми прогонами. */
  function questionTotalMinutes(disc, q, settings) {
    const passes = Math.max(1, disc.plan.passes || 1);
    let sum = 0;
    for (let p = 1; p <= passes; p++) sum += questionMinutes(disc, q, p, settings);
    return sum;
  }

  // ---------- Прогресс ----------

  function readsOf(disc, qIndex) {
    const r = (disc.reads || {})[qIndex];
    return Array.isArray(r) ? r : [];
  }

  /**
   * Состояние вопроса: сколько раз прочитан, когда в последний раз, когда
   * следующее повторение по расширяющемуся интервалу.
   */
  function questionState(disc, qIndex, settings) {
    const reads = readsOf(disc, qIndex).slice().sort();
    const passes = Math.max(1, disc.plan.passes || 1);
    const done = Math.min(reads.length, passes);
    const last = reads.length ? reads[reads.length - 1] : null;
    const exam = disc.plan.examDate;
    let dueDate = null;
    if (done >= 1 && done < passes && last && isValidDate(exam)) {
      dueDate = reviewDate(last, exam, done, settings);
    }
    return { reads: reads, done: done, passes: passes, last: last, dueDate: dueDate };
  }

  /**
   * Дата следующего повторения после чтения last.
   *
   * Интервал растёт: первый повтор — примерно gapRatio от срока до экзамена
   * (исследования по распределённой практике дают оптимум 10–20 % от времени
   * до контроля), каждый следующий — примерно в 1.8 раза длиннее, но так,
   * чтобы последнее повторение осталось до экзамена.
   */
  function reviewDate(last, exam, doneCount, settings) {
    const ratio = Math.min(0.5, Math.max(0.05, settings.gapRatio || 0.15));
    const span = Math.max(1, daysBetween(last, exam));
    let gap = Math.max(1, Math.round(span * ratio));
    // Экспоненциальное растяжение интервалов: 1×, 1.8×, 3.2× …
    gap = Math.round(gap * Math.pow(1.8, Math.max(0, doneCount - 1)));
    gap = Math.max(1, Math.min(gap, span - 1));
    return addDays(last, gap);
  }

  /** Сколько ещё осталось прочитать по вопросу (в минутах) с учётом прогресса. */
  function remainingMinutes(disc, globalSettings) {
    const settings = discSettings(disc, globalSettings);
    let sum = 0;
    const passes = Math.max(1, disc.plan.passes || 1);
    disc.questions.forEach((q, i) => {
      const s = questionState(disc, i, settings);
      for (let p = s.done + 1; p <= passes; p++) sum += questionMinutes(disc, q, p, settings);
    });
    return Math.round(sum * 100) / 100;
  }

  /** Объём дисциплины целиком (все прогоны). */
  function totalMinutes(disc, globalSettings) {
    const settings = discSettings(disc, globalSettings);
    let sum = 0;
    const passes = Math.max(1, disc.plan.passes || 1);
    disc.questions.forEach((q) => {
      for (let p = 1; p <= passes; p++) sum += questionMinutes(disc, q, p, settings);
    });
    return Math.round(sum * 100) / 100;
  }

  // ---------- Порядок вопросов ----------

  /**
   * Порядок «вперемешку»: соседние дни берут вопросы из разных частей файла.
   * Это полезнее, чем читать подряд (перемежающаяся практика), но по умолчанию
   * оставлен прямой порядок — так удобнее искать вопрос в файле.
   */
  function orderedIndices(disc) {
    const n = disc.questions.length;
    const idx = [];
    for (let i = 0; i < n; i++) idx.push(i);
    if ((disc.plan.order || "inOrder") === "mixed" && n > 6) {
      // Детерминированная перестановка с шагом, взаимно простым с n.
      let step = Math.max(2, Math.round(n * 0.618));
      while (gcd(step, n) !== 1) step++;
      const out = [];
      const seen = new Set();
      for (let k = 0; out.length < n && k < n * 3; k++) {
        const i = (k * step) % n;
        if (!seen.has(i)) {
          seen.add(i);
          out.push(i);
        }
      }
      for (let i = 0; i < n; i++) if (!seen.has(i)) out.push(i);
      return out;
    }
    return idx;
  }
  function gcd(a, b) {
    while (b) {
      const t = a % b;
      a = b;
      b = t;
    }
    return a;
  }

  /**
   * Выравнивание загрузки: переносит единицы работы из перегруженных дней
   * в соседние свободные, не нарушая порядок (повторение не раньше первого чтения).
   */
  function balance(bucket, load, days, minutesOf, disc, questions, settings) {
    const target = load.reduce((a, b) => a + b, 0) / Math.max(1, days.length);
    if (!(target > 0)) return;
    const hard = Math.max(target * 1.35, target + 12);
    const passOf = {};
    bucket.forEach((items, di) => items.forEach((it) => (passOf[it.qIndex + ":" + it.pass] = di)));

    for (let di = 0; di < days.length; di++) {
      if (load[di] <= hard) continue;
      // Первое чтение не переносим: порядок вопросов 1, 2, 3 … важнее ровной
      // загрузки, иначе план читается «вразнобой». Выравниваем только повторения.
      const items = bucket[di]
        .filter((it) => it.pass > 1)
        .slice()
        .sort((a, b) => b.minutes - a.minutes);
      for (const it of items) {
        if (load[di] <= hard) break;
        // Ищем самый свободный день: для повторений — позже срока, для новых — рядом.
        let bestDi = -1;
        let bestLoad = Infinity;
        for (let dj = 0; dj < days.length; dj++) {
          if (dj === di) continue;
          // Повторение не может стоять раньше первого чтения.
          if (it.pass > 1) {
            const firstDi = passOf[it.qIndex + ":1"];
            if (firstDi != null && dj <= firstDi) continue;
            if (it.pass > 2) {
              const prevDi = passOf[it.qIndex + ":" + (it.pass - 1)];
              if (prevDi != null && dj <= prevDi) continue;
            }
          }
          const dist = Math.abs(dj - di);
          const score = load[dj] + dist * target * 0.05;
          if (score < bestLoad && load[dj] + it.minutes <= hard) {
            bestLoad = score;
            bestDi = dj;
          }
        }
        if (bestDi < 0) continue;
        // Переносим.
        bucket[di].splice(bucket[di].indexOf(it), 1);
        bucket[bestDi].push(it);
        load[di] -= it.minutes;
        load[bestDi] += it.minutes;
        passOf[it.qIndex + ":" + it.pass] = bestDi;
      }
      bucket[di].sort((a, b) => a.qIndex - b.qIndex || a.pass - b.pass);
    }
  }

  // ---------- Планирование одной дисциплины ----------

  /**
   * buildDisciplinePlan(disc, settings, today)
   *
   * Возвращает:
   *   days     — { 'ГГГГ-ММ-ДД': [ {qIndex, pass, minutes} … ] }
   *   stats    — объёмы, готовность, норма на день
   *   warnings — что не помещается и почему
   */
  function buildDisciplinePlan(disc, settings, today, options) {
    options = options || {};
    today = today || todayStr();
    const plan = disc.plan || {};
    const warnings = [];
    const passes = Math.max(1, plan.passes || 1);
    const questions = disc.questions || [];

    const emptyStats = {
      questions: questions.length,
      passesDone: 0,
      passesTotal: questions.length * passes,
      remainingPasses: questions.length * passes,
      minutesTotal: 0,
      minutesLeft: 0,
      minutesDone: 0,
      daysAvailable: 0,
      perDayMinutes: 0,
      perDayQuestions: 0,
      newPerDay: 0,
      newQuestionsPlanned: 0,
      reviewPassesPlanned: 0,
      plannedMinutes: 0,
      unplannedMinutes: 0,
      peakMinutes: 0,
      peakDay: null,
      progress: 0,
      firstReadProgress: 0,
      behind: false,
      finishDate: null,
      leftQuestions: 0
    };

    if (!questions.length) {
      return {
        days: {},
        stats: emptyStats,
        warnings: [{ type: "empty", text: "В дисциплине нет вопросов." }]
      };
    }
    if (!isValidDate(plan.examDate)) {
      return {
        days: {},
        stats: Object.assign({}, emptyStats, {
          minutesTotal: totalMinutes(disc, settings),
          minutesLeft: remainingMinutes(disc, settings)
        }),
        warnings: [{ type: "no-exam-date", text: "Не задана дата экзамена." }]
      };
    }

    const exam = plan.examDate;
    const start = plan.startDate && isValidDate(plan.startDate) && plan.startDate > today
      ? plan.startDate
      : today;

    // --- Готовность -----------------------------------------------------
    let passesDone = 0;
    let firstRead = 0;
    const states = questions.map((q, i) => {
      const st = questionState(disc, i, settings);
      passesDone += st.done;
      if (st.done > 0) firstRead++;
      return st;
    });
    const minTotal = totalMinutes(disc, settings);
    const minLeft = remainingMinutes(disc, settings);
    const baseStats = Object.assign({}, emptyStats, {
      passesDone: passesDone,
      passesTotal: questions.length * passes,
      remainingPasses: questions.length * passes - passesDone,
      minutesTotal: minTotal,
      minutesLeft: minLeft,
      minutesDone: Math.max(0, minTotal - minLeft),
      progress: questions.length ? firstRead / questions.length : 0,
      firstReadProgress: questions.length ? firstRead / questions.length : 0
    });

    if (exam < start) {
      return {
        days: {},
        stats: baseStats,
        warnings: [
          {
            type: "exam-passed",
            text:
              "Дата экзамена (" + exam + ") уже прошла или раньше даты начала — план не строится. " +
              "Измените дату экзамена в настройках дисциплины."
          }
        ]
      };
    }

    const days = listActiveDays(start, exam, plan.restDays || [], plan);
    if (!days.length) {
      return {
        days: {},
        stats: baseStats,
        warnings: [
          {
            type: "no-days",
            text: "Не осталось ни одного учебного дня: все дни недели в диапазоне отмечены как выходные."
          }
        ]
      };
    }

    const dayIndex = {};
    days.forEach((d, i) => (dayIndex[d] = i));
    const load = days.map(() => 0);
    const bucket = days.map(() => []);
    // Последний день, куда поставлен новый вопрос: держит первый прогон
    // строго по возрастанию номеров (1, 2, 3 … без перескоков).
    let lastNewDay = 0;

    // Мягкий дневной потолок: столько минут в день стараемся не превышать.
    const target = minLeft / Math.max(1, days.length);
    const mode = plan.mode || "even";
    let softCap = Math.max(10, target * 1.15);
    if (mode === "minutes") softCap = Math.max(5, plan.perDayMinutes || 45);
    if (settings.dailyCapMinutes > 0) softCap = Math.min(softCap, Math.max(10, settings.dailyCapMinutes));
    // «По вопросам»: норма задана штуками, а не минутами. Потолок по времени
    // снимаем, но пересчитываем в минуты эквивалент нормы — иначе последний
    // день собирал все остатки и в нём оказывалось втрое больше вопросов.
    if (mode === "questions") {
      const perDayQ = Math.max(1, Number(plan.perDayQuestions) || 10);
      const avgMin = questions.length ? minLeft / questions.length : 0;
      // Небольшой запас: ровно N вопросов должно влезать, а не «N минус
      // округление» — иначе часть вопросов сваливалась в последний день.
      softCap = Math.max(5, avgMin * perDayQ * 1.1);
    }
    if (options.softCapMinutes && options.softCapMinutes > 0) {
      softCap = Math.min(softCap, Math.max(5, options.softCapMinutes));
    }

    // Дневная ёмкость с учётом весов дней недели: в «тяжёлый» день влезает
    // больше, в лёгкий — меньше. Дни с нулевым весом в days уже не попали.
    // Личный предел чтения: если человек сказал «в обычный день 90 минут»,
    // план старается в это укладываться и переносит остаток на дни с большим
    // весом. Это ориентир, а не запрет: важнее успеть к экзамену.
    const comfort = Number(plan.comfortMinutes) || Number(settings.comfortMinutes) || 0;
    if (comfort > 0) {
      // Личный объём — это предел, а не приказ: если человек задал ещё и
      // общий предел на день (или потолок дисциплины), побеждает меньшее.
      // Раньше здесь стояло «= comfort», и общий предел на день молча
      // отключался, стоило задать свой объём.
      softCap = Math.min(softCap, Math.max(5, comfort));
    }
    const dayFactor = days.map((d) => Math.max(0.25, weekdayFactor(plan, d)));
    // Внимание: здесь именно вес дня, а не сам день. Раньше сюда попадала
    // строка с датой, умножение давало NaN — и дневного потолка не было
    // вообще: последний день собирал все остатки, а порядок вопросов ломался.
    const cap = dayFactor.map((f) => softCap * f);

    /** Первый учебный день не раньше даты, либо -1. */
    function dayOnOrAfter(dateStr) {
      for (let i = 0; i < days.length; i++) if (days[i] >= dateStr) return i;
      return -1;
    }

    // Норма «сколько вопросов в день» в штуках. Считаем её один раз и уже по
    // ней ограничиваем новые вопросы — иначе последний день собирал остатки
    // (в нём оказывалось втрое больше нормы, а порядок читался как попало).
    const perDayQuestions =
      mode === "questions" ? Math.max(1, Number(plan.perDayQuestions) || 10) : 0;
    const avgQuestionMinutes = questions.length ? minLeft / questions.length : 0;
    const newCountOnDay = days.map(() => 0);

    /** Куда поставить единицу работы: ближайший день после срока с наименьшей загрузкой. */
    function place(idx, pass, prefIdx, kind) {
      if (prefIdx < 0) return -1;
      if (prefIdx >= days.length) prefIdx = days.length - 1;
      // Порядок важнее ровной загрузки: новые вопросы идут строго по номерам,
      // поэтому очередной вопрос не может встать раньше предыдущего. Без этого
      // «свободный день» перетаскивал вопрос 40 во второй день плана.
      if (pass === 1 && prefIdx < lastNewDay) prefIdx = lastNewDay;
      if (pass === 1 && prefIdx >= days.length) prefIdx = days.length - 1;
      const minutes = questionMinutes(disc, questions[idx], pass, settings);
      // Разброс по окну: ищем день, где загрузка не превышает мягкий потолок.
      const window = Math.max(1, Math.round(days.length * 0.1));
      // Помещается ли ещё один вопрос в этот день: по минутам и, если норма
      // задана штуками, по количеству.
      const fits = (di) => {
        if (pass === 1 && perDayQuestions > 0 && newCountOnDay[di] >= perDayQuestions) return false;
        return load[di] + minutes <= Math.max(cap[di], minutes);
      };
      let best = -1;
      for (let k = 0; k <= window && prefIdx + k < days.length; k++) {
        const di = prefIdx + k;
        if (fits(di)) {
          best = di;
          break;
        }
      }
      // Новый вопрос: если в этот день уже не помещается, ставим в следующий
      // свободный, а не в самый свободный из окна. Иначе, когда норма в день —
      // «N вопросов», в один день сбивалось больше N, а порядок ломался.
      if (best === -1 && pass === 1) {
        for (let di = prefIdx; di < days.length; di++) {
          if (fits(di)) {
            best = di;
            break;
          }
        }
      }
      if (best === -1) {
        // Ничего не подошло — берём самый свободный день в окне (или срок).
        // Свободный считаем не в минутах, а в долях от ёмкости этого дня:
        // в день «×3» ёмкость втрое больше, и при перегрузке (объём больше,
        // чем влезает) он всё равно должен получать втрое больше остальных.
        // Иначе при тесном сроке веса дней пропадали и все дни уравнивались.
        let minShare = Infinity;
        for (let k = 0; k <= window && prefIdx + k < days.length; k++) {
          const di = prefIdx + k;
          const share = load[di] / Math.max(1, cap[di]);
          if (share < minShare) {
            minShare = share;
            best = di;
          }
        }
        if (best === -1) best = Math.min(prefIdx, days.length - 1);
      }
      bucket[best].push({ qIndex: idx, pass: pass, kind: kind, minutes: minutes });
      load[best] += minutes;
      if (pass === 1) {
        newCountOnDay[best]++;
        if (best > lastNewDay) lastNewDay = best;
      }
      return best;
    }

    // --- Фаза 1. Новый материал ----------------------------------------
    // Новые вопросы распределяем по первым 80 % срока: каждая порция получает
    // время на повторения до экзамена.
    const reviewTail = Math.max(1, Math.round(days.length * 0.18));
    const newDayCount = Math.max(1, days.length - reviewTail);
    const newQueue = orderedIndices(disc).filter((i) => states[i].done === 0);
    const plannedNewDate = {};

    // Куда поставить k-й новый вопрос: по накопленной ёмкости дней, а не по
    // ровной сетке. Иначе «в воскресенье больше» осталось бы только словами.
    const prefixCap = [];
    let accCap = 0;
    for (let i = 0; i < newDayCount; i++) {
      accCap += dayFactor[i];
      prefixCap.push(accCap);
    }
    const totalCapNew = accCap || 1;
    function dayForNew(k) {
      // Начало порции k в долях накопленной ёмкости. Именно начало, а не
      // середина: иначе при ровной неделе первый день оставался бы пустым.
      const point = (k * totalCapNew) / Math.max(1, newQueue.length);
      for (let i = 0; i < prefixCap.length; i++) if (prefixCap[i] > point) return i;
      return newDayCount - 1;
    }

    let unplanned = 0;
    newQueue.forEach((idx, k) => {
      const pref = Math.min(newDayCount - 1, Math.max(0, dayForNew(k)));
      const di = place(idx, 1, pref, "new");
      if (di === -1) {
        for (let pass = 1; pass <= passes; pass++) unplanned += questionMinutes(disc, questions[idx], pass, settings);
        return;
      }
      plannedNewDate[idx] = days[di];
    });

    // --- Фаза 2. Повторения по расширяющимся интервалам -----------------
    // Порядок важен: сначала повторения для вопросов, прочитанных раньше.
    const reviewItems = [];
    questions.forEach((q, idx) => {
      const st = states[idx];
      if (st.done >= passes) return;
      if (st.done === 0 && !plannedNewDate[idx]) return; // новый не поместился
      const anchor = st.done > 0 ? (st.last || days[0]) : plannedNewDate[idx];
      reviewItems.push({ idx: idx, done: st.done, anchor: anchor, due: anchor });
    });
    // Сортируем по сроку первого повторения, чтобы ранние ушли в ранние дни.
    reviewItems.sort((a, b) => {
      const da = a.done > 0 ? (dayIndex[a.due] != null ? dayIndex[a.due] : -1) : (dayIndex[plannedNewDate[a.idx]] || 0);
      const db = b.done > 0 ? (dayIndex[b.due] != null ? dayIndex[b.due] : -1) : (dayIndex[plannedNewDate[b.idx]] || 0);
      return da - db;
    });

    for (const item of reviewItems) {
      const idx = item.idx;
      let anchorDate = item.anchor;
      let prevIdx = dayIndex[anchorDate];
      // Для нового вопроса первое чтение уже поставлено в фазе 1 — начинаем с pass 2.
      // Если же вопрос уже читался, note.done — сколько раз, повторяем со следующего.
      const firstPass = item.done > 0 ? item.done + 1 : 2;
      for (let pass = firstPass; pass <= passes; pass++) {
        const due = reviewDate(anchorDate, exam, pass - 1, settings);
        let prefIdx = dayOnOrAfter(due);
        if (prefIdx === -1) prefIdx = days.length - 1;
        if (prevIdx !== undefined && prefIdx <= prevIdx) prefIdx = prevIdx + 1;
        const di = place(idx, pass, prefIdx, "review");
        if (di === -1) {
          // Не поместилось: остаток считаем невыполненным.
          for (let p = pass; p <= passes; p++) unplanned += questionMinutes(disc, questions[idx], p, settings);
          break;
        }
        anchorDate = days[di];
        prevIdx = di;
      }
    }

    // --- Балансировка ----------------------------------------------------
    // Если в последних днях пусто, а в первых тесно — это нормально: повторения
    // привязаны к срокам. Но если самый тяжёлый день заметно тяжелее среднего,
    // переносим из него единицы работы на свободные дни неподалёку.
    balance(bucket, load, days, questionMinutes, disc, questions, settings);

    const leftQuestions = newQueue.filter((idx) => plannedNewDate[idx] === undefined).length;

    // --- Итоги ----------------------------------------------------------
    const dayPlan = {};
    days.forEach((d, i) => (dayPlan[d] = bucket[i]));

    let plannedMinutes = 0;
    let peakMinutes = 0;
    let peakDay = null;
    let newQuestions = 0;
    let reviewPasses = 0;
    let lastDayWithWork = null;
    days.forEach((d, i) => {
      let m = 0;
      for (const it of bucket[i]) {
        m += it.minutes;
        if (it.kind === "new") newQuestions++;
        else reviewPasses++;
      }
      plannedMinutes += m;
      if (m > peakMinutes) {
        peakMinutes = m;
        peakDay = d;
      }
      if (m > 0.01) lastDayWithWork = d;
    });

    // «Не помещается» — только если действительно не удалось поставить работу:
    // каждая единица либо в плане, либо в unplanned, поэтому расхождение больше
    // половины минуты означает, что какой-то день переполнен.
    const behind = unplanned > 0.5;
    const perDay = plannedMinutes / Math.max(1, days.length);

    const stats = Object.assign({}, baseStats, {
      daysAvailable: days.length,
      newDayCount: newDayCount,
      perDayMinutes: perDay,
      perDayQuestions: newQuestions / Math.max(1, days.length),
      newPerDay: newQuestions / Math.max(1, days.length),
      newQuestionsPlanned: newQuestions,
      reviewPassesPlanned: reviewPasses,
      plannedMinutes: plannedMinutes,
      unplannedMinutes: unplanned,
      peakMinutes: peakMinutes,
      peakDay: peakDay,
      finishDate: lastDayWithWork,
      behind: behind,
      leftQuestions: leftQuestions
    });

    // --- Предупреждения -------------------------------------------------
    if (behind) {
      const need = minLeft / Math.max(1, days.length);
      warnings.push({
        type: "behind",
        text:
          "Всё не помещается: вне плана остаётся " +
          text.humanDurationShort(unplanned) +
          " работы. Чтобы успеть, нужно около " +
          Math.round(need) +
          " мин в день вместо " +
          Math.round(perDay) +
          ". Помогает уменьшение числа прогонов, более поздняя дата экзамена или больше дней в неделю."
      });
    }
    if (leftQuestions > 0) {
      warnings.push({
        type: "not-all-new",
        text:
          "Не все вопросы получат первое чтение до экзамена: осталось " + leftQuestions +
          ". Увеличьте число вопросов в день или добавьте дни."
      });
    }
    if (peakMinutes > 0 && perDay > 0 && peakMinutes > Math.max(perDay * 1.6, perDay + 30)) {
      warnings.push({
        type: "peak",
        text:
          "Самый тяжёлый день — " + peakDay + ": " + Math.round(peakMinutes) +
          " мин (в среднем " + Math.round(perDay) + " мин). Так бывает, когда повторения совпадают."
      });
    }
    // Перегрузка. Порог не выдумываем за человека: если он указал, сколько
    // готов читать в обычный день, сравниваем именно с этой цифрой. Без
    // настройки предупреждаем только о совсем тяжёлом режиме (4 часа в день),
    // потому что «2 часа» для одного нормa, а для другого много.
    const limit = comfort > 0 ? comfort : 240;
    if (perDay > limit) {
      warnings.push({
        type: "overload",
        text:
          "В среднем выходит " + text.humanDurationShort(perDay) + " в день" +
          (comfort > 0 ? ", а вы рассчитывали на " + text.humanDurationShort(comfort) : "") +
          ". Помогает уменьшить число прогонов, сдвинуть экзамен, добавить дни недели " +
          "или разрешить в отдельные дни читать больше."
      });
    }
    if (passes > 1 && days.length < 3) {
      warnings.push({
        type: "too-few-days",
        text: "До экзамена меньше трёх учебных дней — повторения не успеют дать эффект."
      });
    }

    return { days: dayPlan, stats: stats, warnings: warnings, order: days };
  }

  // ---------- Общий план по всем дисциплинам ----------

  /**
   * computeAll(state, today)
   *
   * state = { settings, disciplines }
   * Возвращает сводку: план по каждой дисциплине, объединённый календарь,
   * «сегодня», ближайшие дни, тревоги и общий прогресс.
   */
  function computeAll(state, today) {
    today = today || todayStr();
    const settings = normalizeSettings(state.settings || {});
    const discs = (state.disciplines || []).filter((d) => d && d.include !== false);
    const perDisc = {};
    const combined = {};
    const warnings = [];

    // Общий дневной бюджет: если задан, делим его между дисциплинами
    // пропорционально оставшемуся объёму — тогда каждый день идёт работа
    // по всем дисциплинам сразу, а не «сначала одна, потом другая».
    const budget = settings.globalDailyMinutes > 0 ? settings.globalDailyMinutes : 0;
    const weights = {};
    if (budget) {
      let totalLeft = 0;
      for (const d of discs) {
        const left = remainingMinutes(d, settings);
        weights[d.id] = left;
        totalLeft += left;
      }
      for (const d of discs) {
        const share = totalLeft > 0 ? (weights[d.id] / totalLeft) * budget : budget / Math.max(1, discs.length);
        weights[d.id] = Math.max(4, share);
      }
    }

    for (const d of discs) {
      const r = buildDisciplinePlan(d, settings, today, budget ? { softCapMinutes: weights[d.id] } : undefined);
      perDisc[d.id] = r;
      for (const date of Object.keys(r.days)) {
        if (!combined[date]) combined[date] = [];
        for (const it of r.days[date]) {
          combined[date].push({ discId: d.id, discName: d.name, ...it });
        }
      }
      for (const w of r.warnings) warnings.push(Object.assign({ disciplineId: d.id, disciplineName: d.name }, w));
    }

    // Порядок внутри дня: сначала новые вопросы по возрастанию номера, потом
    // повторения. Так список на экране всегда читается как «1, 2, 3 …», даже
    // если в план попали правки из прошлых версий.
    for (const date of Object.keys(combined)) {
      combined[date].sort(
        (a, b) =>
          (a.pass > 1 ? 1 : 0) - (b.pass > 1 ? 1 : 0) ||
          a.qIndex - b.qIndex ||
          a.pass - b.pass
      );
      for (const it of combined[date]) {
        if (perDisc[it.discId] && perDisc[it.discId].days[date]) {
          perDisc[it.discId].days[date].sort(
            (a, b) => (a.pass > 1 ? 1 : 0) - (b.pass > 1 ? 1 : 0) || a.qIndex - b.qIndex || a.pass - b.pass
          );
        }
      }
    }

    // Дневная нагрузка по календарю.
    const dayTotals = {};
    for (const date of Object.keys(combined)) {
      let m = 0;
      for (const it of combined[date]) m += it.minutes;
      if (m > 0.005) dayTotals[date] = m;
    }
    const totals = {
      disciplines: discs.length,
      questions: discs.reduce((s, d) => s + (d.questions || []).length, 0),
      words: discs.reduce((s, d) => s + (d.questions || []).reduce((a, q) => a + q.words, 0), 0),
      chars: discs.reduce((s, d) => s + (d.questions || []).reduce((a, q) => a + q.chars, 0), 0)
    };

    let minutesTotal = 0;
    let minutesLeft = 0;
    let passesTotal = 0;
    let passesDone = 0;
    for (const d of discs) {
      const st = perDisc[d.id].stats;
      minutesTotal += st.minutesTotal || 0;
      minutesLeft += st.minutesLeft || 0;
      passesTotal += st.passesTotal || 0;
      passesDone += st.passesDone || 0;
    }

    const todayTasks = combined[today] || [];
    const upcoming = [];
    const dates = Object.keys(dayTotals).sort();
    for (const date of dates) {
      if (date < today) continue;
      upcoming.push({ date: date, minutes: dayTotals[date], items: (combined[date] || []).length });
      if (upcoming.length >= 14) break;
    }

    // Самый тяжёлый день — по всему календарю, а не только по ближайшим двум неделям.
    let maxDayMinutes = 0;
    let maxDay = null;
    for (const date of Object.keys(dayTotals)) {
      if (dayTotals[date] > maxDayMinutes) {
        maxDayMinutes = dayTotals[date];
        maxDay = date;
      }
    }

    return {
      today: today,
      settings: settings,
      perDisc: perDisc,
      combined: combined,
      dayTotals: dayTotals,
      todayTasks: todayTasks,
      todayMinutes: dayTotals[today] || 0,
      upcoming: upcoming,
      warnings: warnings,
      totals: Object.assign(totals, {
        minutesTotal: minutesTotal,
        minutesLeft: minutesLeft,
        passesTotal: passesTotal,
        passesDone: passesDone,
        maxDayMinutes: maxDayMinutes,
        maxDay: maxDay,
        daysWithWork: Object.keys(dayTotals).length,
        progress: passesTotal ? passesDone / passesTotal : 0
      })
    };
  }

  /** Значения настроек по умолчанию + приведение типов. */
  function normalizeSettings(s) {
    return Object.assign(
      {
        wordsPerMinute: 150,
        charsPerMinute: 900,
        unit: "wpm",
        reviewSpeedFactor: 1.5,
        gapRatio: 0.15,
        dailyCapMinutes: 0,
        globalDailyMinutes: 0,
        passesDefault: 3
      },
      s || {}
    );
  }

  /** Настройки плана дисциплины по умолчанию. */
  function defaultPlan(today, examDate) {
    return {
      startDate: today,
      examDate: examDate || addDays(today, 30),
      passes: 3,
      mode: "even",
      perDayQuestions: 10,
      perDayMinutes: 45,
      restDays: [],
      // Нагрузка по дням недели, от воскресенья к субботе (как weekday()):
      // 0 — отдых, 1 — как обычно, 2 — вдвое больше, 3 — втрое и так далее.
      // Вес может быть дробным (1.5) и любым большим: если в субботу человек
      // готов читать 3 часа, а в будни 40 минут — это просто «6» в субботу.
      dayLoad: [0, 1, 1, 1, 1, 1, 1],
      // Сколько человек реально готов читать в обычный день, минут.
      // 0 — не задано, тогда потолок считается по объёму работы.
      comfortMinutes: 0,
      order: "inOrder"
    };
  }

  /** Что осталось на день по дисциплине. */
  function dayItems(planResult, date) {
    return (planResult.days && planResult.days[date]) || [];
  }

  /**
   * Прогноз: как изменится дата окончания, если сегодня прочитать n вопросов.
   * Нужен для подсказки «если сегодня +2 вопроса — успеваете».
   */
  function forecast(disc, settings, today, extraPasses) {
    const clone = JSON.parse(JSON.stringify({
      questions: disc.questions,
      plan: disc.plan,
      reads: disc.reads
    }));
    const s = questionState(clone, 0, settings);
    return s;
  }

  /** Готовность дисциплины в процентах (0..100) по всем прогонам. */
  function completion(disc, settings) {
    const passes = Math.max(1, disc.plan.passes || 1);
    const total = disc.questions.length * passes;
    if (!total) return 0;
    let done = 0;
    disc.questions.forEach((q, i) => {
      done += questionState(disc, i, settings).done;
    });
    return done / total;
  }

  return {
    parseDate,
    fmtDate,
    todayStr,
    addDays,
    daysBetween,
    weekday,
    isValidDate,
    listActiveDays,
    weekdayFactor,
    isDayOff,
    questionMinutes,
    discSettings,
    questionTotalMinutes,
    questionState,
    reviewDate,
    remainingMinutes,
    totalMinutes,
    buildDisciplinePlan,
    computeAll,
    normalizeSettings,
    defaultPlan,
    dayItems,
    forecast,
    completion,
    orderedIndices
  };
});
