/*
 * sky.js — живое небо.
 *
 * Рисуется на одном canvas и состоит из слоёв, от дальнего к ближнему:
 *   • градиент времени суток (меняется по часам, плавно переходит);
 *   • звёзды и луна (ночью), солнце с лучами (днём);
 *   • три слоя облаков с разной скоростью — отсюда ощущение глубины;
 *   • птицы, редкие искры и «пыль» в воздухе;
 *   • мягкий свет от курсора (параллакс).
 *
 * Всё на requestAnimationFrame, с ограничением по fps и остановкой, когда
 * окно скрыто. При системном «уменьшить движение» анимация замирает.
 */
(function (root) {
  "use strict";

  const state = {
    canvas: null,
    ctx: null,
    w: 0,
    h: 0,
    dpr: 1,
    raf: null,
    lastFrame: 0,
    targetFps: 60,
    running: false,
    reduced: false,
    paused: false,
    quality: 1,
    mouse: { x: 0.5, y: 0.4, tx: 0.5, ty: 0.4 },
    time: 0,
    clouds: [],
    stars: [],
    birds: [],
    dust: [],
    sun: { x: 0.78, y: 0.2, r: 78 },
    theme: "day",
    hourOverride: null
  };

  // ---------- Палитры по времени суток ----------
  // Каждая — четыре цвета: верх неба, середина, низ и цвет «света».
  const PALETTES = {
    night: ["#071427", "#0d2340", "#1b3a5c", "#7fa7c9"],
    dawn: ["#1b2a52", "#5b4a7a", "#c98a86", "#ffd9ba"],
    morning: ["#4a90c9", "#7fb6dd", "#c9e2f2", "#fff4dd"],
    day: ["#3d84c6", "#69aee0", "#b6ddf2", "#ffffff"],
    evening: ["#2c4a7a", "#6b6ea8", "#e5a07d", "#ffe0b3"],
    dusk: ["#101c3a", "#2a3566", "#6b4a7a", "#f0b9a3"]
  };

  function lerpColor(a, b, t) {
    const pa = hexToRgb(a);
    const pb = hexToRgb(b);
    return (
      "rgb(" +
      Math.round(pa[0] + (pb[0] - pa[0]) * t) + "," +
      Math.round(pa[1] + (pb[1] - pa[1]) * t) + "," +
      Math.round(pa[2] + (pb[2] - pa[2]) * t) + ")"
    );
  }
  function hexToRgb(h) {
    const s = h.replace("#", "");
    return [parseInt(s.slice(0, 2), 16), parseInt(s.slice(2, 4), 16), parseInt(s.slice(4, 6), 16)];
  }
  function lerpPalette(a, b, t) {
    return a.map((c, i) => lerpColor(c, b[i], t));
  }

  /** Палитра по часу суток (0..24) с плавными переходами. */
  function paletteForHour(hour) {
    const stops = [
      { h: 0, p: PALETTES.night },
      { h: 5, p: PALETTES.night },
      { h: 6.5, p: PALETTES.dawn },
      { h: 8, p: PALETTES.morning },
      { h: 11, p: PALETTES.day },
      { h: 16, p: PALETTES.day },
      { h: 18, p: PALETTES.evening },
      { h: 20, p: PALETTES.dusk },
      { h: 22, p: PALETTES.night },
      { h: 24, p: PALETTES.night }
    ];
    for (let i = 0; i < stops.length - 1; i++) {
      const a = stops[i];
      const b = stops[i + 1];
      if (hour >= a.h && hour <= b.h) {
        const t = b.h === a.h ? 0 : (hour - a.h) / (b.h - a.h);
        // Сглаживание — переход не «дёргается» на границе.
        const e = t * t * (3 - 2 * t);
        return { colors: lerpPalette(a.p, b.p, e), night: hour < 6 || hour > 20 };
      }
    }
    return { colors: PALETTES.day, night: false };
  }

  // ---------- Объекты ----------

  function makeCloud(scale) {
    const puffs = [];
    const n = 4 + Math.floor(Math.random() * 4);
    for (let i = 0; i < n; i++) {
      puffs.push({
        dx: (i - n / 2) * 0.34 + (Math.random() - 0.5) * 0.2,
        dy: (Math.random() - 0.5) * 0.22,
        r: 0.34 + Math.random() * 0.3
      });
    }
    return {
      x: Math.random() * 1.4 - 0.2,
      y: 0.08 + Math.random() * 0.62,
      w: 0.16 + Math.random() * 0.22,
      speed: (0.004 + Math.random() * 0.012) * (0.6 + scale * 0.7),
      alpha: 0.26 + Math.random() * 0.4,
      scale: scale,
      puffs: puffs,
      phase: Math.random() * Math.PI * 2,
      drift: (Math.random() - 0.5) * 0.0006
    };
  }

  function initClouds() {
    state.clouds = [];
    const layers = [
      { count: Math.max(3, Math.round(6 * state.quality)), scale: 0.55 },
      { count: Math.max(3, Math.round(5 * state.quality)), scale: 0.8 },
      { count: Math.max(2, Math.round(4 * state.quality)), scale: 1.15 }
    ];
    for (const L of layers) {
      for (let i = 0; i < L.count; i++) {
        const c = makeCloud(L.scale);
        // Дальние — выше и прозрачнее, ближние — ниже и плотнее.
        c.y = L.scale < 0.7 ? 0.06 + Math.random() * 0.3 : 0.16 + Math.random() * 0.55;
        c.alpha *= L.scale < 0.7 ? 0.65 : 1;
        state.clouds.push(c);
      }
    }
  }

  function initStars() {
    state.stars = [];
    const n = Math.round(120 * state.quality);
    for (let i = 0; i < n; i++) {
      state.stars.push({
        x: Math.random(),
        y: Math.random() * 0.75,
        r: 0.4 + Math.random() * 1.3,
        phase: Math.random() * Math.PI * 2,
        speed: 0.4 + Math.random() * 1.6
      });
    }
  }

  function initBirds() {
    state.birds = [];
    for (let i = 0; i < 3; i++) {
      state.birds.push({
        x: Math.random() * 1.2 - 0.1,
        y: 0.12 + Math.random() * 0.3,
        speed: 0.012 + Math.random() * 0.014,
        size: 6 + Math.random() * 5,
        phase: Math.random() * Math.PI * 2
      });
    }
  }

  function initDust() {
    state.dust = [];
    const n = Math.round(40 * state.quality);
    for (let i = 0; i < n; i++) {
      state.dust.push({
        x: Math.random(),
        y: Math.random(),
        r: 0.6 + Math.random() * 1.6,
        vy: -0.006 - Math.random() * 0.012,
        vx: (Math.random() - 0.5) * 0.008,
        phase: Math.random() * Math.PI * 2,
        alpha: 0.1 + Math.random() * 0.3
      });
    }
  }

  // ---------- Рисование ----------

  function resize() {
    const c = state.canvas;
    if (!c) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = window.innerWidth;
    const h = window.innerHeight;
    state.dpr = dpr;
    state.w = w;
    state.h = h;
    c.width = Math.round(w * dpr);
    c.height = Math.round(h * dpr);
    c.style.width = w + "px";
    c.style.height = h + "px";
    state.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    state.sun.r = Math.max(52, Math.min(w, h) * 0.075);
  }

  function currentHour() {
    if (state.hourOverride != null) return state.hourOverride;
    const d = new Date();
    return d.getHours() + d.getMinutes() / 60;
  }

  function drawSky(colors, night) {
    const { ctx, w, h } = state;
    const g = ctx.createLinearGradient(0, 0, 0, h);
    g.addColorStop(0, colors[0]);
    g.addColorStop(0.42, colors[1]);
    g.addColorStop(0.78, colors[2]);
    g.addColorStop(1, mix(colors[2], colors[3], 0.35));
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);

    // Мягкое свечение у горизонта.
    const hg = ctx.createRadialGradient(w * 0.5, h * 1.05, 0, w * 0.5, h * 1.05, h * 0.9);
    hg.addColorStop(0, "rgba(255,255,255," + (night ? 0.05 : 0.28) + ")");
    hg.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = hg;
    ctx.fillRect(0, 0, w, h);
  }

  function mix(a, b, t) {
    const pa = hexToRgb(a);
    const pb = hexToRgb(b);
    return (
      "rgb(" +
      Math.round(pa[0] + (pb[0] - pa[0]) * t) + "," +
      Math.round(pa[1] + (pb[1] - pa[1]) * t) + "," +
      Math.round(pa[2] + (pb[2] - pa[2]) * t) + ")"
    );
  }

  function drawStars(alpha) {
    if (alpha <= 0.01) return;
    const { ctx, w, h } = state;
    ctx.save();
    for (const s of state.stars) {
      const twinkle = 0.55 + 0.45 * Math.sin(state.time * s.speed + s.phase);
      ctx.globalAlpha = alpha * twinkle * 0.9;
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(s.x * w, s.y * h, s.r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawSun(x, y, r, colors, night) {
    const { ctx } = state;
    ctx.save();
    const glow = ctx.createRadialGradient(x, y, r * 0.2, x, y, r * 5.5);
    glow.addColorStop(0, night ? "rgba(214,232,255,0.55)" : "rgba(255,246,214,0.85)");
    glow.addColorStop(0.28, night ? "rgba(200,222,255,0.16)" : "rgba(255,228,170,0.34)");
    glow.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(x, y, r * 5.5, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = night ? "#f4f8ff" : "#fffdf4";
    ctx.beginPath();
    ctx.arc(x, y, r * (night ? 0.72 : 0.62), 0, Math.PI * 2);
    ctx.fill();

    if (night) {
      // Лунные «моря» — мягкие пятна, чтобы диск не выглядел плоским.
      ctx.globalAlpha = 0.16;
      ctx.fillStyle = "#8fa6c9";
      for (let i = 0; i < 4; i++) {
        const a = (i / 4) * Math.PI * 2 + state.time * 0.02;
        ctx.beginPath();
        ctx.arc(x + Math.cos(a) * r * 0.26, y + Math.sin(a) * r * 0.22, r * 0.16, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.restore();
  }

  function drawCloud(c, light) {
    const { ctx, w, h } = state;
    const cx = c.x * w;
    const cy = c.y * h;
    const cw = c.w * w;
    ctx.save();
    ctx.globalAlpha = c.alpha;
    ctx.translate(cx, cy);

    // Тень снизу: облако объёмнее.
    const shades = ["rgba(255,255,255,0.96)", "rgba(255,255,255,0.86)", "rgba(232,242,252,0.6)"];
    for (let i = 0; i < c.puffs.length; i++) {
      const p = c.puffs[i];
      const r = cw * p.r;
      const px = p.dx * cw;
      const py = p.dy * cw * 0.6;
      const g = ctx.createRadialGradient(px, py - r * 0.25, r * 0.1, px, py, r);
      g.addColorStop(0, shades[0]);
      g.addColorStop(0.55, shades[1]);
      g.addColorStop(1, "rgba(226,238,250,0)");
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(px, py, r, 0, Math.PI * 2);
      ctx.fill();
    }

    // Подсветка сверху — от солнца/луны.
    ctx.globalAlpha = c.alpha * (light.night ? 0.16 : 0.3);
    ctx.fillStyle = light.color;
    for (const p of c.puffs) {
      const r = cw * p.r * 0.62;
      ctx.beginPath();
      ctx.arc(p.dx * cw, p.dy * cw * 0.6 - r * 0.4, r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawBird(b, alpha) {
    const { ctx, w, h } = state;
    const wing = Math.sin(state.time * 4.5 + b.phase);
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = "rgba(60,85,115,0.55)";
    ctx.lineWidth = 1.5;
    ctx.lineCap = "round";
    const x = b.x * w;
    const y = b.y * h + Math.sin(state.time * 0.7 + b.phase) * 6;
    const s = b.size;
    ctx.beginPath();
    ctx.moveTo(x - s, y + wing * s * 0.35);
    ctx.quadraticCurveTo(x - s * 0.35, y - s * 0.3 * wing, x, y);
    ctx.quadraticCurveTo(x + s * 0.35, y - s * 0.3 * wing, x + s, y + wing * s * 0.35);
    ctx.stroke();
    ctx.restore();
  }

  function drawDust(dt) {
    const { ctx, w, h } = state;
    ctx.save();
    for (const d of state.dust) {
      d.x += d.vx * dt;
      d.y += d.vy * dt;
      if (d.y < -0.05) {
        d.y = 1.05;
        d.x = Math.random();
      }
      if (d.x < -0.05) d.x = 1.05;
      if (d.x > 1.05) d.x = -0.05;
      const a = d.alpha * (0.6 + 0.4 * Math.sin(state.time * 1.4 + d.phase));
      ctx.globalAlpha = a;
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(d.x * w, d.y * h, d.r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawVignette() {
    const { ctx, w, h } = state;
    const g = ctx.createRadialGradient(w * 0.5, h * 0.42, Math.min(w, h) * 0.25, w * 0.5, h * 0.42, Math.max(w, h) * 0.78);
    g.addColorStop(0, "rgba(0,0,0,0)");
    g.addColorStop(1, "rgba(8,24,44,0.22)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
  }

  // ---------- Цикл ----------

  function frame(ts) {
    if (!state.running) return;
    const minInterval = 1000 / state.targetFps;
    if (ts - state.lastFrame < minInterval - 1) {
      state.raf = requestAnimationFrame(frame);
      return;
    }
    const dt = Math.min(0.05, (ts - state.lastFrame) / 1000 || 0.016);
    state.lastFrame = ts;
    if (!state.paused && !state.reduced) state.time += dt;

    const hour = currentHour();
    const pal = paletteForHour(hour);
    state.theme = pal.night ? "night" : "day";

    drawSky(pal.colors, pal.night);

    // Положение солнца/луны по часу: дуга от востока к западу.
    const dayT = (hour - 6) / 12; // 0 в 6:00, 1 в 18:00
    const arc = Math.max(-0.3, Math.min(1.3, dayT));
    const sunX = state.w * (0.1 + arc * 0.8);
    const sunY = state.h * (0.62 - Math.sin(Math.max(0, Math.min(1, arc)) * Math.PI) * 0.5);
    const nightT = ((hour + 6) % 24) / 12;
    const moonArc = Math.max(-0.3, Math.min(1.3, hour >= 18 ? (hour - 18) / 12 : (hour + 6) / 12));
    const moonX = state.w * (0.12 + moonArc * 0.76);
    const moonY = state.h * (0.6 - Math.sin(Math.max(0, Math.min(1, moonArc)) * Math.PI) * 0.46);

    // Параллакс от курсора.
    state.mouse.x += (state.mouse.tx - state.mouse.x) * 0.05;
    state.mouse.y += (state.mouse.ty - state.mouse.y) * 0.05;
    const px = (state.mouse.x - 0.5) * 26;
    const py = (state.mouse.y - 0.5) * 14;

    drawStars(pal.night ? 1 : Math.max(0, (hour < 6 ? 1 - hour / 6 : hour > 19 ? (hour - 19) / 3 : 0)), );

    if (pal.night) drawSun(moonX - px * 0.4, moonY - py * 0.4, state.sun.r, pal.colors, true);
    else drawSun(sunX - px * 0.5, sunY - py * 0.5, state.sun.r, pal.colors, false);

    // Облака: дальние быстрее «отстают» от курсора.
    for (const c of state.clouds) {
      if (!state.paused && !state.reduced) {
        c.x += (c.speed * dt) / Math.max(1, c.scale * 1.6);
        c.drift += (Math.random() - 0.5) * 0.00002;
        c.y += Math.sin(state.time * 0.15 + c.phase) * 0.00008 + c.drift * dt;
        if (c.x > 1.45) {
          c.x = -0.35;
          c.y = 0.06 + Math.random() * 0.62;
        }
      }
      drawCloud(
        Object.assign({}, c, {
          x: c.x + (px * 0.0009) / c.scale,
          y: c.y + (py * 0.0007) / c.scale
        }),
        { night: pal.night, color: pal.colors[3] }
      );
    }

    if (!pal.night) {
      for (const b of state.birds) {
        if (!state.paused && !state.reduced) {
          b.x += b.speed * dt;
          if (b.x > 1.2) {
            b.x = -0.2;
            b.y = 0.1 + Math.random() * 0.32;
          }
        }
        drawBird(b, 0.5);
      }
    }

    drawDust(dt);
    drawVignette();

    state.raf = requestAnimationFrame(frame);
  }

  // ---------- Публичный интерфейс ----------

  function start() {
    if (state.running) return;
    state.running = true;
    state.lastFrame = performance.now();
    state.raf = requestAnimationFrame(frame);
  }

  function stop() {
    state.running = false;
    if (state.raf) cancelAnimationFrame(state.raf);
    state.raf = null;
  }

  function init(canvas) {
    state.canvas = canvas;
    state.ctx = canvas.getContext("2d", { alpha: false });
    state.reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // Качество по числу ядер и размеру экрана: на слабом ноутбуке меньше облаков.
    const cores = navigator.hardwareConcurrency || 4;
    state.quality = cores >= 8 ? 1 : cores >= 4 ? 0.85 : 0.7;
    state.targetFps = cores >= 8 ? 60 : 45;

    resize();
    initClouds();
    initStars();
    initBirds();
    initDust();

    window.addEventListener("resize", debounce(resize, 140));
    window.addEventListener("pointermove", (e) => {
      state.mouse.tx = e.clientX / Math.max(1, window.innerWidth);
      state.mouse.ty = e.clientY / Math.max(1, window.innerHeight);
    });
    document.addEventListener("visibilitychange", () => {
      state.paused = document.hidden;
    });
    start();
  }

  function debounce(fn, ms) {
    let t = null;
    return function () {
      clearTimeout(t);
      t = setTimeout(fn, ms);
    };
  }

  root.Sky = {
    init,
    start,
    stop,
    setHour: (h) => {
      state.hourOverride = h;
    },
    clearHour: () => {
      state.hourOverride = null;
    },
    setQuality: (q) => {
      state.quality = q;
      initClouds();
      initStars();
      initDust();
    },
    isNight: () => state.theme === "night",
    state
  };
})(typeof window !== "undefined" ? window : globalThis);
