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
    // Первый повтор — близко (2–3 дня): именно он закрепляет прочитанное.
    // Дальше интервал растёт: 1×, 2.5×, 5× … Так повторения нужных вопросов
    // распределяются по всему сроку, а не сваливаются в последнюю неделю.
    const first = Math.max(1, Math.min(span - 1, Math.max(2, Math.round(span * ratio * 0.35))));
    let gap = first * Math.pow(2.5, Math.max(0, doneCount - 1));
    gap = Math.max(1, Math.min(Math.round(gap), span - 1));
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
    const bucket = days.map(() => []);
    const load = days.map(() => 0);

    // ------------------------------------------------------------------
    //  Ровное распределение по вашему дневному объёму
    // ------------------------------------------------------------------
    // Правило простое: есть N учебных дней и X минут работы. Каждый день
    // получает свою долю — не больше, чем вы готовы читать, и ровно столько
    // же, сколько соседние (с поправкой на вес дня недели). Никаких «сначала
    // густо, потом пусто». Если работы меньше места — она всё равно
    // размазывается по всему сроку, а не сваливается в первые дни.
    const mode = plan.mode || "even";
    const comfort = Number(plan.comfortMinutes) || Number(settings.comfortMinutes) || 0;
    const dayFactor = days.map((d) => Math.max(0.25, weekdayFactor(plan, d)));
    const factorTotal = dayFactor.reduce((a, b) => a + b, 0);
    const perDayEven = Math.max(5, minLeft / Math.max(1, days.length));
    // Сколько вы готовы в обычный день: сказали сами — берём это, иначе
    // считаем по объёму работы (ровно столько, чтобы успеть к экзамену).
    let baseCap = comfort > 0 ? comfort : perDayEven;
    if (mode === "minutes") baseCap = Math.max(5, plan.perDayMinutes || baseCap);
    if (settings.dailyCapMinutes > 0) baseCap = Math.min(baseCap, Math.max(5, settings.dailyCapMinutes));
    if (options.softCapMinutes && options.softCapMinutes > 0) {
      baseCap = Math.min(baseCap, Math.max(5, options.softCapMinutes));
    }
    // Сказанное человеком — его личный объём, и он не может быть меньше
    // доли, которая нужна, чтобы успеть: иначе половина работы просто не
    // попадёт в план. Программа в этом случае работает на полную и честно
    // предупреждает «не помещается», вместо того чтобы молча отбросить.
    const planFloor = minLeft / Math.max(1, days.length);
    baseCap = Math.max(baseCap, planFloor);

    /** Новые вопросы — строго по порядку номеров, с первого непрочитанного. */
    const newQueue = orderedIndices(disc).filter((i) => states[i].done === 0);
    let qi = 0;

    /**
     * Сколько минут уже прочитано сегодня. Эти минуты занимают место в
     * сегодняшнем дне: если человек прочёл больше нормы, программа не
     * поставит ему ещё столько же, а разложит остаток тоньше.
     */
    const doneToday = days.map(() => 0);
    questions.forEach((q, idx) => {
      const di = dayIndex[today];
      if (di === undefined) return;
      const reads = states[idx].reads;
      for (let k = 0; k < reads.length; k++) {
        if (reads[k] === days[di]) doneToday[di] += questionMinutes(disc, q, k + 1, settings);
      }
    });

    /**
     * Очередь повторений: когда какой вопрос «созревает».
     * Для уже прочитанных считаем от последнего чтения, для новых — от дня,
     * в который его поставим.
     */
    const due = [];
    function addReviews(idx, fromDate, doneCount) {
      let anchor = fromDate;
      for (let p = doneCount + 1; p <= passes; p++) {
        let when = reviewDate(anchor, exam, p - 1, settings);
        // Повтор не может стоять в тот же день, что и предыдущий прогон:
        // прочитать вопрос дважды за один вечер — не повторение, а путаница.
        // Поэтому следующий срок считается от фактического дня, с шагом не
        // меньше двух дней.
        if (when < addDays(anchor, 2)) when = addDays(anchor, 2);
        if (when > exam) when = exam;
        due.push({ idx: idx, pass: p, due: when, minutes: questionMinutes(disc, questions[idx], p, settings) });
        anchor = when;
      }
    }
    function sortDue() {
      due.sort((a, b) => (a.due < b.due ? -1 : a.due > b.due ? 1 : a.idx - b.idx));
    }
    questions.forEach((q, idx) => {
      const st = states[idx];
      if (st.done > 0 && st.done < passes) addReviews(idx, st.last || days[0], st.done);
    });
    sortDue();

    /** Поставить единицу работы в день di. */
    function put(di, item) {
      bucket[di].push(item);
      load[di] += item.minutes;
    }

    /**
     * Поставить повторение и пересчитать оставшиеся сроки этого вопроса.
     *
     * Раньше повтор вставал по «идеальной» дате, даже если предыдущий прогон
     * из-за нехватки места уезжал. Теперь сроки идут от того дня, в который
     * вопрос реально прочитан: второй прогон не может оказаться в один день
     * с третьим, и порядок «сначала — потом» всегда соблюдается.
     */
    function placeReview(it, di) {
      put(di, { qIndex: it.idx, pass: it.pass, kind: "review", minutes: it.minutes });
      for (let k = due.length - 1; k >= 0; k--) {
        if (due[k].idx === it.idx) due.splice(k, 1);
      }
      addReviews(it.idx, days[di], it.pass);
      sortDue();
    }

    const firstReadDay = {}; // вопрос → день первого чтения
    const quotaByDay = [];   // норма каждого дня: по ней видно ровность
    // Сколько всего осталось разложить: с каждой отметкой это число меньше,
    // поэтому план сам становится легче.
    let remaining = minLeft;

    /**
     * Раскладываем работу по дням от сегодняшнего к экзамену.
     *
     * Норма дня — ровная полоса: весь оставшийся объём делится на все
     * оставшиеся дни по весам. Вопрос ставится в день, только если он в эту
     * полосу влезает; если не влезает — день остаётся легче, а норма
     * переходит на следующий. Поэтому план одинаково ровный и для одного
     * вопроса в неделю, и для двух часов в день, а человек, прочитавший
     * сегодня больше нормы, завтра получит меньше — это и есть «вперёд».
     */
    let budget = 0;
    for (let di = 0; di < days.length; di++) {
      const day = days[di];
      const f = dayFactor[di];
      let factorLeft = 0;
      for (let k = di; k < days.length; k++) factorLeft += dayFactor[k];
      // Норма дня в минутах: доля остатка по весу дня.
      const quota = factorLeft > 0 ? (remaining * f) / factorLeft : 0;
      quotaByDay[di] = quota;
      budget += quota;

      // 1. Повторения, срок которых наступил, — первыми: они и так опаздывают.
      for (let k = 0; k < due.length; ) {
        const it = due[k];
        if (it.due > day) break;
        // Один вопрос дважды в день не читаем: «повторение» не должно
        // оказаться в тот же вечер, что и предыдущее чтение.
        if (firstReadDay[it.idx] === day) { k++; continue; }
        if (it.minutes > budget + 0.001) { k++; continue; }
        due.splice(k, 1);
        placeReview(it, di);
        budget -= it.minutes;
      }

      // 2. Новые вопросы — строго по порядку номеров, с первого непрочитанного.
      //    Если полоса дня ещё не занята, берём следующий вопрос, не дожидаясь
      //    «его» дня: это и есть чтение вперёд. Свободное место после этого
      //    автоматически уходит следующим дням.
      while (qi < newQueue.length) {
        const idx = newQueue[qi];
        const minutes = questionMinutes(disc, questions[idx], 1, settings);
        // Сегодняшний день не оставляем пустым: если вопрос длиннее полосы,
        // лучше прочитать его сейчас, чем открыть программу и увидеть
        // «делать нечего». Дальше такие вопросы ждут своей нормы.
        const todayOnly = di === 0 && load[di] === 0 && qi === 0;
        if (minutes > budget + 0.001 && !todayOnly) break;
        qi++;
        put(di, { qIndex: idx, pass: 1, kind: "new", minutes: minutes });
        budget -= minutes;
        firstReadDay[idx] = day;
        addReviews(idx, day, 1);
        sortDue();
      }

      // 3. Место осталось — подтягиваем ближайшие повторения: лучше прочитать
      //    сейчас, пока есть время, чем оставить на день, где его не будет.
      for (let k = 0; k < due.length; ) {
        const it = due[k];
        if (firstReadDay[it.idx] === day) { k++; continue; }
        if (it.minutes > budget + 0.001) { k++; continue; }
        due.splice(k, 1);
        placeReview(it, di);
        budget -= it.minutes;
      }

      remaining = Math.max(0, remaining - load[di]);
    }

    // Остаток: ровно по минутам вопросы не делятся, и что-то могло не попасть
    // в полосы. Докладываем в дни, где ещё есть место сверх нормы, — начиная
    // с последних, чтобы первые дни не разбухали. Новые вопросы ставим только
    // после последнего уже занятого дня: порядок важнее.
    if (qi < newQueue.length || due.length) {
      let lastNew = -1;
      for (let di = 0; di < days.length; di++) {
        if (bucket[di].some((it) => it.pass === 1)) lastNew = di;
      }
      for (let di = days.length - 1; di >= Math.max(0, lastNew); di--) {
        const room = () => Math.max(0, baseCap * dayFactor[di] * 1.2 - load[di]);
        while (due.length) {
          const it = due[0];
          if (firstReadDay[it.idx] === days[di] || it.minutes > room()) break;
          due.shift();
          placeReview(it, di);
        }
        while (qi < newQueue.length) {
          const idx = newQueue[qi];
          const minutes = questionMinutes(disc, questions[idx], 1, settings);
          if (minutes > room()) break;
          qi++;
          put(di, { qIndex: idx, pass: 1, kind: "new", minutes: minutes });
          firstReadDay[idx] = days[di];
          addReviews(idx, days[di], 1);
          sortDue();
        }
      }
    }

    // Последняя попытка: если место осталось хоть где-то в сроке — ставим
    // туда. Лучше чуть плотнее, чем «вопрос не прочитан». Порядок новых
    // вопросов при этом не ломается: их дни уже идут по возрастанию.
    if (qi < newQueue.length || due.length) {
      const order = days.map((d, i) => i).sort((a, b) => load[a] - load[b]);
      for (const di of order) {
        const room = () => Math.max(0, baseCap * dayFactor[di] * 1.5 - load[di]);
        while (due.length) {
          const it = due[0];
          if (firstReadDay[it.idx] === days[di] || it.minutes > room()) break;
          due.shift();
          placeReview(it, di);
        }
        while (qi < newQueue.length) {
          const idx = newQueue[qi];
          const minutes = questionMinutes(disc, questions[idx], 1, settings);
          if (minutes > room()) break;
          qi++;
          put(di, { qIndex: idx, pass: 1, kind: "new", minutes: minutes });
          firstReadDay[idx] = days[di];
          addReviews(idx, days[di], 1);
          sortDue();
        }
      }
    }

    // Что не поместилось — честно считаем невыполненным.
    let unplanned = 0;
    while (qi < newQueue.length) {
      const idx = newQueue[qi++];
      for (let p = 1; p <= passes; p++) unplanned += questionMinutes(disc, questions[idx], p, settings);
    }
    for (const it of due) unplanned += it.minutes;
    // Внутри дня: сначала новые вопросы по возрастанию, потом повторения.
    for (let di = 0; di < bucket.length; di++) {
      bucket[di].sort((a, b) => (a.pass === 1 ? 0 : 1) - (b.pass === 1 ? 0 : 1) || a.qIndex - b.qIndex || a.pass - b.pass);
    }

    balance(bucket, load, days, questionMinutes, disc, questions, settings);
    const leftQuestions = newQueue.filter((idx) => firstReadDay[idx] === undefined).length;

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
      newDayCount: days.length,
      // Сколько выходит в обычный день и сколько всего по плану: по этим
      // числам человек проверяет, что план ровный.
      dayQuota: Math.round(
        quotaByDay.reduce((a, b) => a + b, 0) / Math.max(1, quotaByDay.length)
      ),
      capMinutes: Math.round(baseCap * 100) / 100,
      // Сколько места в сроке осталось неиспользованным: при ровном плане это
      // ноль, а большой остаток значит «можно читать спокойнее».
      unusedMinutes: Math.max(0, baseCap * factorTotal - plannedMinutes),
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
    // Ровность: если какой-то день выбивается из общего ритма — говорим прямо.
    const typical = quotaByDay.reduce((a, b) => a + b, 0) / Math.max(1, quotaByDay.length);
    if (!behind && typical > 0 && peakMinutes > Math.max(typical * 1.6, typical + 30)) {
      warnings.push({
        type: "peak",
        text:
          "Один день выходит тяжелее остальных — " + peakDay + ": " + Math.round(peakMinutes) +
          " мин при обычных " + Math.round(typical) + " мин. Так бывает, когда совпадают повторения."
      });
    }
    // Перегрузка. Порог не выдумываем за человека: если он указал, сколько
    // готов читать в обычный день, сравниваем именно с этой цифрой. Без
    // настройки предупреждаем только о совсем тяжёлом режиме (4 часа в день),
    // потому что «2 часа» для одного норма, а для другого много.
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
