/*
 * audio.js — мягкие синтезированные звуки через Web Audio API (без файлов).
 */
(function () {
  let ctx = null;
  let enabled = true;

  function ensure() {
    if (!ctx) {
      try {
        ctx = new (window.AudioContext || window.webkitAudioContext)();
      } catch (e) {
        ctx = null;
      }
    }
    if (ctx && ctx.state === "suspended") ctx.resume();
    return ctx;
  }

  function tone(freq, start, dur, type, gain) {
    const c = ensure();
    if (!c) return;
    const t0 = c.currentTime + start;
    const osc = c.createOscillator();
    const g = c.createGain();
    osc.type = type || "sine";
    osc.frequency.value = freq;
    g.gain.setValueAtTime(0, t0);
    g.gain.linearRampToValueAtTime(gain || 0.12, t0 + 0.012);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    osc.connect(g).connect(c.destination);
    osc.start(t0);
    osc.stop(t0 + dur + 0.02);
  }

  const Audio = {
    setEnabled(v) {
      enabled = !!v;
      if (enabled) ensure();
    },
    isEnabled() {
      return enabled;
    },
    // Мягкий перезвон при отметке выполненного.
    chime() {
      if (!enabled) return;
      tone(880, 0, 0.18, "sine", 0.1);
      tone(1320, 0.04, 0.22, "sine", 0.06);
    },
    // Перелив при завершении дня / достижении.
    sparkle() {
      if (!enabled) return;
      const notes = [659, 784, 988, 1319];
      notes.forEach((f, i) => tone(f, i * 0.07, 0.3, "triangle", 0.08));
    },
    // Тихий щелчок при навигации.
    nav() {
      if (!enabled) return;
      tone(523, 0, 0.09, "sine", 0.05);
    },
    // Мягкое «открытие».
    open() {
      if (!enabled) return;
      tone(392, 0, 0.18, "sine", 0.06);
      tone(587, 0.08, 0.22, "sine", 0.05);
    },
    // Лёгкое предупреждение.
    warn() {
      if (!enabled) return;
      tone(311, 0, 0.22, "sawtooth", 0.05);
    }
  };

  window.ExamAudio = Audio;
})();
