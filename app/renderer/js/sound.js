/*
 * sound.js — звуки интерфейса.
 *
 * Никаких внешних файлов: всё синтезируется через Web Audio. Звуки мягкие,
 * короткие, в одной тональности (пентатоника ля-мажор), поэтому не надоедают
 * и не «звенят». Громкость и полное выключение — в настройках.
 *
 * Основные звуки:
 *   tick     — наведение на элемент;
 *   tap      — нажатие, обычное действие;
 *   check    — отметка «прочитано» (самый приятный);
 *   uncheck  — снятие отметки;
 *   complete — этап завершён, «праздник» (арпеджио вверх);
 *   chime    — общее уведомление, пересчёт плана;
 *   whoosh   — смена экрана;
 *   error    — мягкое предупреждение.
 */
(function (root) {
  "use strict";

  let ctx = null;
  let master = null;
  let enabled = true;
  let volume = 0.45;
  let lastPlay = {};

  // Пентатоника: A, C, D, E, G по октавам — любые сочетания звучат согласно.
  const SCALE = [440.0, 523.25, 587.33, 659.25, 783.99, 880.0, 1046.5, 1174.66, 1318.51];

  function ensure() {
    if (ctx) return ctx;
    const AC = root.AudioContext || root.webkitAudioContext;
    if (!AC) return null;
    ctx = new AC();
    master = ctx.createGain();
    master.gain.value = volume;
    // Мягкий фильтр срезает возможную резкость высоких частот.
    const filter = ctx.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.value = 6200;
    filter.Q.value = 0.4;
    master.connect(filter);
    filter.connect(ctx.destination);
    return ctx;
  }

  /** Разблокировка после первого действия пользователя (требование браузера). */
  function unlock() {
    const c = ensure();
    if (c && c.state === "suspended") c.resume();
  }

  function now() {
    return ctx ? ctx.currentTime : 0;
  }

  /**
   * Один тон с огибающей.
   * opts: { freq, dur, type, gain, delay, slideTo, attack }
   */
  function tone(opts) {
    if (!enabled) return;
    const c = ensure();
    if (!c) return;
    if (c.state === "suspended") c.resume();

    const t0 = now() + (opts.delay || 0);
    const dur = opts.dur || 0.16;
    const osc = c.createOscillator();
    const gain = c.createGain();
    osc.type = opts.type || "sine";
    osc.frequency.setValueAtTime(opts.freq, t0);
    if (opts.slideTo) {
      osc.frequency.exponentialRampToValueAtTime(Math.max(30, opts.slideTo), t0 + dur);
    }

    const peak = Math.max(0.0001, (opts.gain == null ? 0.14 : opts.gain));
    const attack = opts.attack == null ? 0.008 : opts.attack;
    gain.gain.setValueAtTime(0.0001, t0);
    gain.gain.exponentialRampToValueAtTime(peak, t0 + attack);
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);

    osc.connect(gain);
    gain.connect(master);
    osc.start(t0);
    osc.stop(t0 + dur + 0.03);
    osc.onended = () => {
      try {
        gain.disconnect();
        osc.disconnect();
      } catch (e) {
        /* уже отключено */
      }
    };
  }

  /** Мягкий шум для «воздушных» звуков (whoosh). */
  function noise(opts) {
    if (!enabled) return;
    const c = ensure();
    if (!c) return;
    const dur = opts.dur || 0.35;
    const t0 = now() + (opts.delay || 0);
    const frames = Math.floor(c.sampleRate * dur);
    const buffer = c.createBuffer(1, frames, c.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < frames; i++) {
      data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / frames, 2.2);
    }
    const src = c.createBufferSource();
    src.buffer = buffer;
    const bp = c.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.setValueAtTime(opts.from || 700, t0);
    bp.frequency.exponentialRampToValueAtTime(opts.to || 2200, t0 + dur);
    bp.Q.value = 1.1;
    const g = c.createGain();
    g.gain.value = opts.gain == null ? 0.06 : opts.gain;
    src.connect(bp);
    bp.connect(g);
    g.connect(master);
    src.start(t0);
    src.stop(t0 + dur + 0.02);
  }

  /** Ограничение частоты повторного звука — чтобы не «строчило». */
  function throttle(name, ms) {
    const t = Date.now();
    if (lastPlay[name] && t - lastPlay[name] < ms) return false;
    lastPlay[name] = t;
    return true;
  }

  const sounds = {
    tick() {
      if (!throttle("tick", 60)) return;
      tone({ freq: SCALE[5], dur: 0.05, type: "sine", gain: 0.035, attack: 0.004 });
    },
    tap() {
      if (!throttle("tap", 40)) return;
      tone({ freq: SCALE[2], dur: 0.1, type: "sine", gain: 0.09 });
      tone({ freq: SCALE[4], dur: 0.13, type: "sine", gain: 0.05, delay: 0.02 });
    },
    check() {
      // Две ноты вверх — «сделано».
      tone({ freq: SCALE[1], dur: 0.13, type: "sine", gain: 0.12 });
      tone({ freq: SCALE[3], dur: 0.2, type: "sine", gain: 0.1, delay: 0.07 });
      tone({ freq: SCALE[5], dur: 0.26, type: "triangle", gain: 0.045, delay: 0.14 });
    },
    uncheck() {
      tone({ freq: SCALE[3], dur: 0.11, type: "sine", gain: 0.075 });
      tone({ freq: SCALE[1], dur: 0.14, type: "sine", gain: 0.055, delay: 0.06 });
    },
    complete() {
      // Арпеджио и мягкий «колокольчик» сверху.
      const notes = [SCALE[0], SCALE[2], SCALE[3], SCALE[5], SCALE[7]];
      notes.forEach((f, i) => {
        tone({ freq: f, dur: 0.42, type: "sine", gain: 0.095, delay: i * 0.075 });
        tone({ freq: f * 2, dur: 0.3, type: "triangle", gain: 0.022, delay: i * 0.075 });
      });
      tone({ freq: SCALE[8], dur: 0.9, type: "sine", gain: 0.05, delay: 0.42 });
    },
    chime() {
      tone({ freq: SCALE[4], dur: 0.34, type: "sine", gain: 0.075 });
      tone({ freq: SCALE[6], dur: 0.5, type: "sine", gain: 0.038, delay: 0.11 });
    },
    whoosh() {
      noise({ dur: 0.32, from: 560, to: 2400, gain: 0.045 });
      tone({ freq: SCALE[3], dur: 0.09, type: "sine", gain: 0.03, delay: 0.02 });
    },
    error() {
      tone({ freq: 220, dur: 0.18, type: "sine", gain: 0.085 });
      tone({ freq: 185, dur: 0.24, type: "sine", gain: 0.06, delay: 0.09 });
    },
    import() {
      // Загрузка файла: восходящая гамма, ощущение «прибыло».
      [0, 2, 3].forEach((i, k) => {
        tone({ freq: SCALE[i], dur: 0.28, type: "sine", gain: 0.08, delay: k * 0.06 });
      });
      noise({ dur: 0.22, from: 900, to: 3000, gain: 0.02, delay: 0.1 });
    },
    page() {
      tone({ freq: SCALE[1], dur: 0.07, type: "sine", gain: 0.05 });
    }
  };

  /** Настройки: включён ли звук и насколько громко. */
  function configure(opts) {
    opts = opts || {};
    if (typeof opts.enabled === "boolean") enabled = opts.enabled;
    if (typeof opts.volume === "number") {
      volume = Math.max(0, Math.min(1, opts.volume));
      if (master) master.gain.value = volume;
    }
  }

  function play(name) {
    if (!enabled) return;
    const fn = sounds[name];
    if (fn) {
      try {
        fn();
      } catch (e) {
        /* звук не критичен */
      }
    }
  }

  root.Sound = {
    play,
    unlock,
    configure,
    isEnabled: () => enabled,
    names: Object.keys(sounds)
  };

  // Разблокировка при первом касании/клике — дальше звуки работают всегда.
  if (typeof document !== "undefined") {
    const un = () => {
      unlock();
      document.removeEventListener("pointerdown", un);
      document.removeEventListener("keydown", un);
    };
    document.addEventListener("pointerdown", un, { once: true });
    document.addEventListener("keydown", un, { once: true });
  }
})(typeof window !== "undefined" ? window : globalThis);
