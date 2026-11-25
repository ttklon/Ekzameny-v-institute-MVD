/*
 * ui.js — маленький набор инструментов для интерфейса.
 *
 * Здесь всё, что повторяется на всех экранах: создание элементов, иконки,
 * уведомления, модальные окна, анимация чисел и колец прогресса.
 * Без фреймворка: элементов немного, а так приложение остаётся лёгким
 * и запускается мгновенно.
 */
(function (root) {
  "use strict";

  // ---------- Создание элементов ----------

  /**
   * h("div.card", {onclick}, [children])
   * Первый аргумент — селектор в стиле CSS: тег, классы, #id.
   */
  function h(selector, props, children) {
    const m = /^([a-z0-9-]+)?((?:[.#][\w-]+)*)$/i.exec(selector || "div");
    const tag = (m && m[1]) || "div";
    const el = document.createElement(tag);
    if (m && m[2]) {
      const parts = m[2].match(/[.#][\w-]+/g) || [];
      for (const p of parts) {
        if (p[0] === ".") el.classList.add(p.slice(1));
        else el.id = p.slice(1);
      }
    }
    if (props && (typeof props !== "object" || props instanceof Node || Array.isArray(props))) {
      children = props;
      props = null;
    }
    if (props) {
      for (const [k, v] of Object.entries(props)) {
        if (v == null || v === false) continue;
        if (k === "class" || k === "className") el.className += (el.className ? " " : "") + v;
        else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
        else if (k === "dataset" && typeof v === "object") Object.assign(el.dataset, v);
        else if (k === "html") el.innerHTML = v;
        else if (k.startsWith("on") && typeof v === "function") {
          el.addEventListener(k.slice(2).toLowerCase(), v);
        } else if (k === "text") el.textContent = v;
        else if (k in el && typeof el[k] !== "undefined" && k !== "list" && k !== "form") {
          try {
            el[k] = v;
          } catch (e) {
            el.setAttribute(k, v);
          }
        } else el.setAttribute(k, v);
      }
    }
    append(el, children);
    return el;
  }

  function append(parent, children) {
    if (children == null || children === false) return parent;
    if (Array.isArray(children)) {
      for (const c of children) append(parent, c);
      return parent;
    }
    if (children instanceof Node) parent.appendChild(children);
    else parent.appendChild(document.createTextNode(String(children)));
    return parent;
  }

  function clear(el) {
    while (el && el.firstChild) el.removeChild(el.firstChild);
    return el;
  }

  function frag(children) {
    const f = document.createDocumentFragment();
    append(f, children);
    return f;
  }

  // ---------- Иконки (по 24×24, тонкий штрих) ----------

  const PATHS = {
    dashboard: "M4 13h6V4H4v9Zm0 7h6v-5H4v5Zm10 0h6V11h-6v9Zm0-16v5h6V4h-6Z",
    import: "M12 16V4m0 0 4 4m-4-4-4 4M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3",
    library: "M4 19V6a2 2 0 0 1 2-2h1v15M9 19V4h3v15M14 19l2.6-14 3.4.7L17.4 20",
    today: "M9 11.5l2.2 2.2L15.5 9.5M12 3.5l8 3.5v5c0 4.4-3.2 7.8-8 8.5-4.8-.7-8-4.1-8-8.5v-5l8-3.5Z",
    calendar: "M7 4v3M17 4v3M4 9h16M5 6h14a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1Z",
    stats: "M5 19V9m7 10V5m7 14v-7",
    tips: "M12 3a6 6 0 0 0-3.6 10.8c.5.4.6.9.6 1.2v.5h6v-.5c0-.3.1-.8.6-1.2A6 6 0 0 0 12 3ZM9.5 19h5M10.5 21h3",
    settings: "M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Zm8-3.2c0 .5 0 .9-.1 1.3l1.8 1.4-1.9 3.3-2.1-.8c-.6.5-1.3.9-2 1.2l-.3 2.2h-3.8l-.3-2.2c-.7-.3-1.4-.7-2-1.2l-2.1.8-1.9-3.3 1.8-1.4a9 9 0 0 1 0-2.6L3.1 8.9l1.9-3.3 2.1.8c.6-.5 1.3-.9 2-1.2L9.4 3h3.8l.3 2.2c.7.3 1.4.7 2 1.2l2.1-.8 1.9 3.3-1.8 1.4c.1.4.1.8.1 1.3Z",
    plus: "M12 5v14M5 12h14",
    check: "M4.5 12.5 9 17l10.5-10.5",
    close: "M6 6l12 12M18 6 6 18",
    chevronLeft: "M14.5 6 9 12l5.5 6",
    chevronRight: "M9.5 6 15 12l-5.5 6",
    chevronDown: "M6 9.5 12 15l6-5.5",
    cloud: "M17.5 19a4.5 4.5 0 0 0 .5-8.97A6 6 0 0 0 6.3 9.2A3.9 3.9 0 0 0 6.8 19h10.7Z",
    file: "M13 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9l-6-6Zm0 0v6h6",
    clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-13v5l3.5 2",
    spark: "M12 3v3m0 12v3M3 12h3m12 0h3M6 6l2 2m8 8 2 2M18 6l-2 2M8 16l-2 2",
    target: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-4.5a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9Zm0-3a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z",
    book: "M4 5.5A2.5 2.5 0 0 1 6.5 3H19v15H6.5A2.5 2.5 0 0 0 4 20.5V5.5ZM4 20.5A2.5 2.5 0 0 1 6.5 18H19",
    trash: "M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 12a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-12M10 11v6M14 11v6",
    edit: "M4 20h4l10-10-4-4L4 16v4Zm10-14 4 4",
    volume: "M11 5 6.5 9H3v6h3.5L11 19V5Zm4.5 3.5a5 5 0 0 1 0 7M18 6a9 9 0 0 1 0 12",
    volumeOff: "M11 5 6.5 9H3v6h3.5L11 19V5Zm5 5 5 5m0-5-5 5",
    search: "M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13Zm5-1.5L20 20",
    filter: "M4 6h16M7 12h10M10 18h4",
    export: "M12 4v12m0 0-4-4m4 4 4-4M4 18v1a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-1",
    warn: "M12 9v4m0 3h.01M10.3 4.3 2.9 17.4A1.5 1.5 0 0 0 4.2 20h15.6a1.5 1.5 0 0 0 1.3-2.6L13.7 4.3a1.5 1.5 0 0 0-2.6 0Z",
    info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-10v5m0-8h.01",
    flame: "M12 21c3.9 0 6.5-2.5 6.5-6 0-4.5-4.5-6.5-4.5-12-3 1.5-4.5 5-4.5 7 0 1-1 1.5-1.5.5-.4-.8-.5-1.5-.5-1.5-1 1.3-2 3.3-2 6 0 3.5 2.6 6 6.5 6Z",
    play: "M8 5.5v13l11-6.5-11-6.5Z",
    pause: "M9 5v14M15 5v14",
    reset: "M4 12a8 8 0 1 0 3-6.2M4 4v5h5",
    eye: "M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Zm9.5 3a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
    link: "M10 14a4 4 0 0 0 5.7 0l3-3A4 4 0 0 0 13 5.3l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3A4 4 0 0 0 11 18.7l1-1"
  };

  function icon(name, size) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "1.7");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    if (size) {
      svg.setAttribute("width", size);
      svg.setAttribute("height", size);
    }
    const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
    p.setAttribute("d", PATHS[name] || PATHS.info);
    svg.appendChild(p);
    return svg;
  }

  // ---------- Форматирование ----------

  const MONTHS = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря"
  ];
  const MONTHS_NOM = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
  ];
  const WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"];
  const WEEKDAYS_SHORT = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"];

  function plural(n, one, few, many) {
    const abs = Math.abs(Math.round(n)) % 100;
    const last = abs % 10;
    if (abs > 10 && abs < 20) return many;
    if (last === 1) return one;
    if (last >= 2 && last <= 4) return few;
    return many;
  }

  function num(n) {
    return String(Math.round(Number(n) || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, "\u202F");
  }

  function dur(minutes) {
    const m = Math.round(Number(minutes) || 0);
    if (m <= 0) return "0 мин";
    if (m < 1) return "меньше минуты";
    const h = Math.floor(m / 60);
    const rest = m % 60;
    if (h === 0) return m + " мин";
    if (rest === 0) return h + " ч";
    return h + " ч " + rest + " мин";
  }

  function durLong(minutes) {
    const m = Math.round(Number(minutes) || 0);
    if (m < 60) return m + " " + plural(m, "минута", "минуты", "минут");
    const h = Math.floor(m / 60);
    const rest = m % 60;
    const hs = h + " " + plural(h, "час", "часа", "часов");
    if (rest === 0) return hs;
    return hs + " " + rest + " " + plural(rest, "минута", "минуты", "минут");
  }

  /** «24 ноября 2026, вторник» */
  function dateLong(iso) {
    const d = new Date(iso + "T00:00:00");
    const wd = (d.getDay() + 6) % 7; // 0 = понедельник
    return d.getDate() + " " + MONTHS[d.getMonth()] + " " + d.getFullYear() + ", " + WEEKDAYS[wd];
  }

  /** «24 ноября» — без года, для ближайших дней. */
  function dateShort(iso) {
    if (!iso) return "—";
    const d = new Date(iso + "T00:00:00");
    return d.getDate() + " " + MONTHS[d.getMonth()];
  }

  /** «сегодня / завтра / через 5 дней». */
  function relativeDay(iso, today) {
    const a = new Date(iso + "T00:00:00").getTime();
    const b = new Date((today || root.ExamCore.planner.todayStr()) + "T00:00:00").getTime();
    const days = Math.round((a - b) / 86400000);
    if (days === 0) return "сегодня";
    if (days === 1) return "завтра";
    if (days === 2) return "послезавтра";
    if (days === -1) return "вчера";
    if (days < 0) return Math.abs(days) + " " + plural(days, "день", "дня", "дней") + " назад";
    if (days < 30) return "через " + days + " " + plural(days, "день", "дня", "дней");
    const months = Math.round(days / 30);
    return "через " + months + " " + plural(months, "месяц", "месяца", "месяцев");
  }

  function weekDayShort(iso) {
    const d = new Date(iso + "T00:00:00");
    return WEEKDAYS_SHORT[(d.getDay() + 6) % 7];
  }

  // ---------- Числовая анимация ----------

  /**
   * Плавно «набегает» от текущего значения к новому.
   * Используется для крупных цифр — так пересчёт виден, а не появляется рывком.
   */
  function animateNumber(el, to, opts) {
    opts = opts || {};
    const from = Number(el.dataset.last != null ? el.dataset.last : opts.from != null ? opts.from : 0) || 0;
    const target = Number(to) || 0;
    el.dataset.last = target;
    const suffix = opts.suffix || "";
    const format = opts.format || num;
    if (Math.abs(target - from) < 0.01 || (root.matchMedia && root.matchMedia("(prefers-reduced-motion: reduce)").matches)) {
      el.textContent = format(target) + suffix;
      return;
    }
    const duration = opts.duration || 780;
    const t0 = performance.now();
    if (el._anim) cancelAnimationFrame(el._anim);
    const tick = (t) => {
      const p = Math.min(1, (t - t0) / duration);
      // Soft ease-out — значение «догоняет» цель и мягко останавливается.
      const e = 1 - Math.pow(1 - p, 3);
      const v = from + (target - from) * e;
      el.textContent = format(v) + suffix;
      if (p < 1) el._anim = requestAnimationFrame(tick);
      else {
        el.textContent = format(target) + suffix;
        el._anim = null;
      }
    };
    el._anim = requestAnimationFrame(tick);
  }

  /** Кольцо прогресса: circle с длиной окружности и dashoffset. */
  function ring(percent, opts) {
    opts = opts || {};
    const size = opts.size || 120;
    const stroke = opts.stroke || 9;
    const r = (size - stroke) / 2;
    const c = 2 * Math.PI * r;
    const pct = Math.max(0, Math.min(100, percent || 0));
    const color = opts.color || "url(#ringGrad)";

    const wrap = h("div.ring", { style: { width: size + "px", height: size + "px" } });
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("width", size);
    svg.setAttribute("height", size);
    svg.setAttribute("viewBox", "0 0 " + size + " " + size);

    const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    const grad = document.createElementNS("http://www.w3.org/2000/svg", "linearGradient");
    grad.setAttribute("id", "ringGrad");
    grad.setAttribute("x1", "0%");
    grad.setAttribute("y1", "0%");
    grad.setAttribute("x2", "100%");
    grad.setAttribute("y2", "100%");
    const s1 = document.createElementNS("http://www.w3.org/2000/svg", "stop");
    s1.setAttribute("offset", "0%");
    s1.setAttribute("stop-color", opts.from || "#6fc3e8");
    const s2 = document.createElementNS("http://www.w3.org/2000/svg", "stop");
    s2.setAttribute("offset", "100%");
    s2.setAttribute("stop-color", opts.to || "#2f7cbe");
    grad.appendChild(s1);
    grad.appendChild(s2);
    defs.appendChild(grad);
    svg.appendChild(defs);

    const bg = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    bg.setAttribute("class", "ring-bg");
    bg.setAttribute("cx", size / 2);
    bg.setAttribute("cy", size / 2);
    bg.setAttribute("r", r);
    bg.setAttribute("stroke-width", stroke);
    svg.appendChild(bg);

    const fg = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    fg.setAttribute("class", "ring-fg");
    fg.setAttribute("cx", size / 2);
    fg.setAttribute("cy", size / 2);
    fg.setAttribute("r", r);
    fg.setAttribute("stroke-width", stroke);
    fg.setAttribute("stroke", color);
    fg.setAttribute("stroke-dasharray", c.toFixed(2));
    fg.setAttribute("stroke-dashoffset", c.toFixed(2));
    svg.appendChild(fg);
    wrap.appendChild(svg);

    const center = h("div.ring-center", [
      h("div", [
        h("div.ring-value", { dataset: { last: pct } }, Math.round(pct) + "%"),
        opts.label ? h("div.ring-label", opts.label) : null
      ])
    ]);
    wrap.appendChild(center);

    // Запуск анимации после вставки в документ — иначе transition не сработает.
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        fg.setAttribute("stroke-dashoffset", (c * (1 - pct / 100)).toFixed(2));
      });
    });

    wrap._fg = fg;
    wrap._c = c;
    wrap._value = center.querySelector(".ring-value");
    wrap.setPercent = function (next) {
      const p = Math.max(0, Math.min(100, next));
      fg.setAttribute("stroke-dashoffset", (c * (1 - p / 100)).toFixed(2));
      animateNumber(wrap._value, p, { suffix: "%", duration: 620 });
    };
    return wrap;
  }

  // ---------- Уведомления ----------

  function toast(opts) {
    const rootEl = document.getElementById("toasts");
    if (!rootEl) return;
    const kind = opts.kind || "info";
    const iconName = kind === "ok" ? "check" : kind === "warn" ? "warn" : kind === "err" ? "warn" : "info";
    const el = h("div.toast." + kind, [
      h("span.t-icon", [icon(kind === "ok" ? "check" : iconName)]),
      h("div", [opts.title ? h("b", opts.title) : null, h("div.t-text", opts.text || "")]),
      // Действие прямо в плашке: ошибочную отметку можно вернуть одним
      // нажатием, не разыскивая вопрос в списке.
      opts.action
        ? h("button.t-action", {
            onclick: (e) => {
              e.stopPropagation();
              try {
                opts.action.onClick();
              } finally {
                clearTimeout(timer);
                kill();
              }
            }
          }, opts.action.label)
        : null
    ]);
    rootEl.appendChild(el);
    const life = opts.duration || 4200;
    const kill = () => {
      el.classList.add("out");
      setTimeout(() => el.remove(), 340);
    };
    const timer = setTimeout(kill, life);
    el.addEventListener("click", () => {
      clearTimeout(timer);
      kill();
    });
    return el;
  }

  // ---------- Модальные окна ----------

  let modalStack = [];

  /**
   * openModal({ title, subtitle, body, footer, wide, onClose })
   * Возвращает { root, close, body }.
   */
  function openModal(opts) {
    const rootEl = document.getElementById("modal-root");
    const veil = h("div.modal-veil");
    const bodyEl = h("div.modal-body", opts.body);
    const modal = h("div.modal" + (opts.wide ? ".wide" : ""), [
      h("div.modal-head", [
        h("div", [
          h("h2", opts.title || ""),
          opts.subtitle ? h("p", opts.subtitle) : null
        ]),
        h("button.close-btn", { onclick: () => close(), title: "Закрыть" }, [icon("close")])
      ]),
      bodyEl,
      opts.footer ? h("div.modal-foot", opts.footer) : null
    ]);

    const entry = { root: null, body: bodyEl, close: null };
    function close() {
      modal.style.animation = "none";
      modal.style.opacity = "0";
      modal.style.transform = "translateY(10px) scale(0.99)";
      modal.style.transition = "all .24s cubic-bezier(.22,.72,.24,1)";
      veil.style.transition = "opacity .24s";
      veil.style.opacity = "0";
      setTimeout(() => {
        if (modal.parentNode) modal.parentNode.removeChild(modal);
        if (veil.parentNode) veil.parentNode.removeChild(veil);
        modalStack = modalStack.filter((m) => m !== entry);
        if (!modalStack.length) rootEl.classList.remove("on");
        if (opts.onClose) opts.onClose();
      }, 230);
    }
    entry.close = close;
    entry.root = modal;

    veil.addEventListener("click", () => {
      if (opts.dismissible !== false) close();
    });
    rootEl.appendChild(veil);
    rootEl.appendChild(modal);
    rootEl.classList.add("on");
    modalStack.push(entry);

    // Esc закрывает верхнее окно.
    const onKey = (e) => {
      if (e.key === "Escape" && modalStack[modalStack.length - 1] === entry) {
        close();
        document.removeEventListener("keydown", onKey);
      }
    };
    document.addEventListener("keydown", onKey);

    root.Sound.play("whoosh");
    return entry;
  }

  function closeAllModals() {
    for (const m of modalStack.slice()) m.close();
  }

  // ---------- Мелкие помощники ----------

  /** Кнопка со звуком нажатия. */
  function button(label, opts) {
    opts = opts || {};
    const el = h("button.btn" + (opts.kind ? ".btn-" + opts.kind : "") + (opts.size === "sm" ? ".btn-sm" : ""), {
      title: opts.title || "",
      onclick: (e) => {
        root.Sound.play(opts.sound || "tap");
        if (opts.onClick) opts.onClick(e);
      }
    }, [opts.icon ? icon(opts.icon) : null, label ? h("span", label) : null]);
    if (opts.disabled) el.disabled = true;
    return el;
  }

  /** Поле с подписью. */
  function field(label, control, hint) {
    return h("div.field", [
      label ? h("label", { text: label }) : null,
      control,
      hint ? h("div.muted", { style: { fontSize: "11.5px", marginTop: "2px" } }, hint) : null
    ]);
  }

  /** Числовое поле со степпером. */
  function stepper(value, opts) {
    opts = opts || {};
    const input = h("input", {
      type: "number",
      value: String(value),
      min: opts.min != null ? opts.min : 0,
      max: opts.max != null ? opts.max : 9999,
      step: opts.step || 1,
      onchange: () => commit(),
      onblur: () => commit()
    });
    function commit() {
      let v = Number(input.value);
      if (!isFinite(v)) v = opts.min || 0;
      v = Math.max(opts.min != null ? opts.min : 0, Math.min(opts.max != null ? opts.max : 9999, v));
      input.value = String(v);
      if (opts.onChange) opts.onChange(v);
    }
    const dec = h("button", { type: "button", title: "Меньше", onclick: () => {
      input.value = String(Math.max(opts.min != null ? opts.min : 0, Number(input.value) - (opts.step || 1)));
      root.Sound.play("tick");
      commit();
    } }, [icon("chevronDown", 16)]);
    const inc = h("button", { type: "button", title: "Больше", onclick: () => {
      input.value = String(Math.min(opts.max != null ? opts.max : 9999, Number(input.value) + (opts.step || 1)));
      root.Sound.play("tick");
      commit();
    } }, [icon("chevronDown", 16)]);
    inc.firstChild.style.transform = "rotate(180deg)";
    return h("div.stepper", [dec, input, inc]);
  }

  /** Плавное появление списка: элементы «поднимаются» по очереди. */
  function stagger(container, staggerMs) {
    const kids = Array.from(container.children);
    kids.forEach((el, i) => {
      el.style.opacity = "0";
      el.style.transform = "translateY(10px)";
      el.style.transition =
        "opacity .42s cubic-bezier(.16,1,.3,1) " + i * (staggerMs || 34) + "ms, transform .5s cubic-bezier(.16,1,.3,1) " + i * (staggerMs || 34) + "ms";
      requestAnimationFrame(() => {
        el.style.opacity = "1";
        el.style.transform = "none";
      });
    });
  }

  /** Мини-диаграмма нагрузки: столбики по дням. */
  function sparkline(values, opts) {
    opts = opts || {};
    const max = Math.max.apply(null, values.concat([1]));
    const wrap = h("div.spark", { title: opts.title || "" });
    values.forEach((v, i) => {
      const height = Math.max(2, (v / max) * 100);
      const bar = h("i", {
        style: { height: height + "%" },
        title: (opts.labels ? opts.labels[i] + ": " : "") + dur(v)
      });
      if (opts.todayIndex === i) bar.classList.add("today");
      if (opts.over != null && v > opts.over) bar.classList.add("over");
      wrap.appendChild(bar);
    });
    return wrap;
  }

  root.UI = {
    h,
    append,
    clear,
    frag,
    icon,
    button,
    field,
    stepper,
    toast,
    openModal,
    closeAllModals,
    ring,
    animateNumber,
    stagger,
    sparkline,
    num,
    dur,
    durLong,
    dateLong,
    dateShort,
    relativeDay,
    weekDayShort,
    plural,
    MONTHS,
    MONTHS_NOM,
    WEEKDAYS,
    WEEKDAYS_SHORT
  };
})(typeof window !== "undefined" ? window : globalThis);
