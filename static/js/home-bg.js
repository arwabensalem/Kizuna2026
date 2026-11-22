// Animation du bandeau d'accueil : un réseau de maisons, fermes, panneaux
// solaires et réservoirs. L'eau (bleu), l'énergie (ambre) et les récoltes
// (vert) circulent sur les liens. Légère, et figée si l'utilisateur
// préfère moins d'animations.
(function () {
  const canvas = document.getElementById("kz-home-bg");
  if (!canvas) return;
  const host = canvas.parentElement;
  const ctx = canvas.getContext("2d");
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const COLORS = { water: "#4cc3ff", energy: "#ffc94a", food: "#5fd38a" };
  const FLOWS = {
    solar: ["energy"], tank: ["water"], farm: ["food", "water"],
    home: ["energy", "water"], city: ["energy", "water", "food"],
  };
  let W = 0, H = 0, nodes = [], links = [], particles = [], running = false;

  function seeded(seed) {
    let s = seed;
    return () => (s = (s * 16807) % 2147483647) / 2147483647;
  }

  function build() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = host.clientWidth; H = host.clientHeight;
    canvas.width = W * dpr; canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const r = seeded(7);
    const cols = Math.max(5, Math.round(W / 170));
    const rows = Math.max(3, Math.round(H / 150));
    const kinds = ["home", "home", "farm", "solar", "tank", "home", "farm"];
    nodes = [];
    for (let i = 0; i < cols; i++) {
      for (let j = 0; j < rows; j++) {
        const x = (i + 0.5) * (W / cols) + (r() - 0.5) * (W / cols) * 0.6;
        const y = (j + 0.5) * (H / rows) + (r() - 0.5) * (H / rows) * 0.6;
        // Le côté gauche, sous le texte, reste plus calme.
        const quiet = (W < 768 || x < W * 0.5) ? 0.22 : 1;
        nodes.push({ x, y, kind: kinds[Math.floor(r() * kinds.length)], glow: 0, quiet, phase: r() * 6.28 });
      }
    }
    nodes.push({ x: W * 0.76, y: H * 0.5, kind: "city", glow: 0, quiet: 1, phase: 0 });

    links = [];
    const seen = new Set();
    nodes.forEach((a, ia) => {
      nodes.map((b, ib) => ({ ib, d: Math.hypot(a.x - b.x, a.y - b.y) }))
        .filter((o) => o.ib !== ia)
        .sort((p, q) => p.d - q.d)
        .slice(0, a.kind === "city" ? 6 : 2)
        .forEach(({ ib }) => {
          const key = Math.min(ia, ib) + "-" + Math.max(ia, ib);
          if (seen.has(key)) return;
          seen.add(key);
          const b = nodes[ib], bend = (r() - 0.5) * 0.3;
          links.push({ a, b, cx: (a.x + b.x) / 2 - (b.y - a.y) * bend, cy: (a.y + b.y) / 2 + (b.x - a.x) * bend });
        });
    });
    particles = Array.from({ length: Math.min(80, links.length * 2) }, () => spawn(Math.random()));
  }

  function spawn(progress) {
    const link = links[Math.floor(Math.random() * links.length)];
    const fromA = Math.random() < 0.5;
    const flows = FLOWS[(fromA ? link.a : link.b).kind];
    return { link, fromA, p: progress || 0, speed: 0.0012 + Math.random() * 0.0018,
      color: COLORS[flows[Math.floor(Math.random() * flows.length)]] };
  }

  function at(l, p) {
    const q = 1 - p;
    return { x: q * q * l.a.x + 2 * q * p * l.cx + p * p * l.b.x, y: q * q * l.a.y + 2 * q * p * l.cy + p * p * l.b.y };
  }

  function icon(n) {
    ctx.lineWidth = 1.6;
    ctx.lineCap = ctx.lineJoin = "round";
    if (n.kind === "home") {
      ctx.beginPath(); ctx.moveTo(-7, 0); ctx.lineTo(0, -7); ctx.lineTo(7, 0); ctx.moveTo(-5, -1); ctx.lineTo(-5, 6); ctx.lineTo(5, 6); ctx.lineTo(5, -1); ctx.stroke();
    } else if (n.kind === "farm") {
      ctx.strokeStyle = COLORS.food;
      for (let i = -5; i <= 5; i += 5) { ctx.beginPath(); ctx.moveTo(i, 6); ctx.lineTo(i, -2); ctx.moveTo(i, 1); ctx.lineTo(i + 3, -3); ctx.stroke(); }
    } else if (n.kind === "solar") {
      ctx.strokeStyle = COLORS.energy;
      ctx.strokeRect(-7, -4, 14, 8);
      ctx.beginPath(); ctx.moveTo(0, -4); ctx.lineTo(0, 4); ctx.moveTo(-7, 0); ctx.lineTo(7, 0); ctx.stroke();
    } else if (n.kind === "tank") {
      ctx.strokeStyle = COLORS.water;
      ctx.beginPath(); ctx.moveTo(0, -7); ctx.quadraticCurveTo(7, 2, 0, 7); ctx.quadraticCurveTo(-7, 2, 0, -7); ctx.stroke();
    } else {
      [[-8, 9], [-2, 14], [4, 7]].forEach(([x, h]) => ctx.strokeRect(x, 7 - h, 4.5, h));
    }
  }

  function frame(now) {
    ctx.clearRect(0, 0, W, H);

    ctx.lineWidth = 1;
    links.forEach((l) => {
      ctx.strokeStyle = `rgba(255, 255, 255, ${0.10 * Math.min(l.a.quiet, l.b.quiet) + 0.03})`;
      ctx.beginPath(); ctx.moveTo(l.a.x, l.a.y); ctx.quadraticCurveTo(l.cx, l.cy, l.b.x, l.b.y); ctx.stroke();
    });

    if (!still) {
      particles.forEach((pt, i) => {
        pt.p += pt.speed;
        if (pt.p >= 1) { (pt.fromA ? pt.link.b : pt.link.a).glow = 1; particles[i] = spawn(0); return; }
        const pos = at(pt.link, pt.fromA ? pt.p : 1 - pt.p);
        const fade = Math.sin(pt.p * Math.PI) * Math.min(pt.link.a.quiet, pt.link.b.quiet) ** 0.5;
        ctx.fillStyle = pt.color;
        ctx.globalAlpha = 0.18 * fade; ctx.beginPath(); ctx.arc(pos.x, pos.y, 7, 0, 6.29); ctx.fill();
        ctx.globalAlpha = 0.95 * fade; ctx.beginPath(); ctx.arc(pos.x, pos.y, 2.2, 0, 6.29); ctx.fill();
      });
      ctx.globalAlpha = 1;
    }

    const t = still ? 0 : now;
    nodes.forEach((n) => {
      const s = n.kind === "city" ? 1.6 : 1;
      const x = n.x, y = n.y + Math.sin(t / 1600 + n.phase) * 1.5;
      ctx.save();
      ctx.translate(x, y);
      ctx.globalAlpha = n.quiet;
      if (n.glow > 0.02) {
        ctx.fillStyle = `rgba(255, 255, 255, ${0.16 * n.glow})`;
        ctx.beginPath(); ctx.arc(0, 0, 24 * s, 0, 6.29); ctx.fill();
        n.glow *= 0.95;
      }
      ctx.scale(s, s);
      ctx.fillStyle = "rgba(9, 38, 40, 0.85)";
      ctx.strokeStyle = "rgba(255, 255, 255, 0.28)";
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.arc(0, 0, 15, 0, 6.29); ctx.fill(); ctx.stroke();
      ctx.strokeStyle = "rgba(255, 255, 255, 0.85)";
      icon(n);
      ctx.restore();
    });

    if (!still && !document.hidden) requestAnimationFrame(frame); else running = false;
  }

  function start() { if (!running) { running = true; requestAnimationFrame(frame); } }

  build();
  start();
  let timer;
  window.addEventListener("resize", () => { clearTimeout(timer); timer = setTimeout(() => { build(); if (still) requestAnimationFrame(frame); }, 150); });
  document.addEventListener("visibilitychange", () => { if (!document.hidden && !still) start(); });
})();
