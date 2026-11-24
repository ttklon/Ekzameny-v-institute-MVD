/*
 * clouds.js — живое небо: мягкие дрейфующие облака и парящие частицы.
 */
(function () {
  const canvas = document.getElementById("sky");
  const ctx = canvas.getContext("2d");
  let W = 0,
    H = 0,
    DPR = 1;
  let clouds = [];
  let particles = [];
  let raf = null;
  const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function resize() {
    DPR = Math.min(window.devicePixelRatio || 1, 2);
    W = canvas.clientWidth = window.innerWidth;
    H = canvas.clientHeight = window.innerHeight;
    canvas.width = W * DPR;
    canvas.height = H * DPR;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  }

  function makeClouds() {
    clouds = [];
    const n = 7;
    for (let i = 0; i < n; i++) {
      clouds.push({
        x: Math.random() * W,
        y: 40 + Math.random() * (H * 0.55),
        r: 90 + Math.random() * 160,
        speed: 0.05 + Math.random() * 0.22,
        alpha: 0.05 + Math.random() * 0.12,
        hue: Math.random() < 0.5 ? "255,255,255" : "200,225,255"
      });
    }
  }

  function makeParticles() {
    particles = [];
    const n = 36;
    for (let i = 0; i < n; i++) {
      particles.push({
        x: Math.random() * W,
        y: Math.random() * H,
        r: 0.6 + Math.random() * 1.8,
        speed: 0.1 + Math.random() * 0.5,
        drift: (Math.random() - 0.5) * 0.3,
        alpha: 0.15 + Math.random() * 0.4
      });
    }
  }

  function drawCloud(c) {
    const grad = ctx.createRadialGradient(c.x, c.y, 0, c.x, c.y, c.r);
    grad.addColorStop(0, `rgba(${c.hue},${c.alpha})`);
    grad.addColorStop(1, `rgba(${c.hue},0)`);
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(c.x, c.y, c.r, 0, Math.PI * 2);
    ctx.fill();
    // вторичные «кучевые» пухлости
    ctx.beginPath();
    ctx.arc(c.x - c.r * 0.4, c.y + c.r * 0.1, c.r * 0.6, 0, Math.PI * 2);
    ctx.arc(c.x + c.r * 0.45, c.y + c.r * 0.05, c.r * 0.7, 0, Math.PI * 2);
    ctx.fillStyle = grad;
    ctx.fill();
  }

  function frame() {
    ctx.clearRect(0, 0, W, H);
    for (const c of clouds) {
      c.x += c.speed;
      if (c.x - c.r > W) c.x = -c.r;
      drawCloud(c);
    }
    for (const p of particles) {
      p.y -= p.speed;
      p.x += p.drift;
      if (p.y < -5) {
        p.y = H + 5;
        p.x = Math.random() * W;
      }
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255,255,255,${p.alpha})`;
      ctx.fill();
    }
    raf = requestAnimationFrame(frame);
  }

  function start() {
    resize();
    makeClouds();
    makeParticles();
    if (raf) cancelAnimationFrame(raf);
    if (!reduced) frame();
    else {
      // Статичный кадр для тех, кто отключил анимации.
      for (const c of clouds) drawCloud(c);
    }
  }

  window.addEventListener("resize", () => {
    resize();
    makeClouds();
    makeParticles();
  });

  window.ExamClouds = { start };
})();
