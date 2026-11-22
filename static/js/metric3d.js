/**
 * Small animated 3D pictures for metric cards.
 *
 * Each <canvas data-metric3d="kind" data-value="..."> gets a tiny scene that
 * shows the number: a running tap for water, a glowing bulb for electricity,
 * a sun over a solar panel, a battery and a tank that fill to the level, and
 * a ring gauge with a shield for the resilience score.
 *
 * One shared WebGL renderer draws every scene, then copies the picture into
 * each card's own canvas. Cards off screen are skipped. With reduced motion
 * turned on, each picture is drawn once and stays still.
 */

import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";

const SIZE = 132;
const REDUCED = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const CSS = `
.placeholder-card.has-3d{position:relative;padding-right:150px;min-height:150px}
.metric-3d{position:absolute;top:50%;right:12px;width:${SIZE}px;height:${SIZE}px;transform:translateY(-50%);pointer-events:none}
.dash-hero .metric-3d{position:static;transform:none;display:block;margin:0 auto .25rem;width:150px;height:150px}
@media (max-width:575px){.placeholder-card.has-3d{padding-right:110px}.metric-3d{width:96px;height:96px;right:6px}}
`;

function number(text) {
  const value = parseFloat(String(text || "0").replace(/\s/g, "").replace(",", "."));
  return Number.isFinite(value) ? value : 0;
}

const clamp01 = (x) => Math.max(0, Math.min(1, x));

function levelColor(pct) {
  if (pct < 20) {
    return new THREE.Color("#e5483b");
  }
  if (pct < 50) {
    return new THREE.Color("#f0a92e");
  }
  return new THREE.Color("#2fbf71");
}

function physical(opts) {
  return new THREE.MeshPhysicalMaterial(opts);
}

function baseScene() {
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 50);
  camera.position.set(2.5, 1.9, 3.3);
  camera.lookAt(0, 0.55, 0);
  const key = new THREE.DirectionalLight("#ffffff", 2.2);
  key.position.set(3, 5, 4);
  scene.add(key, new THREE.HemisphereLight("#ffffff", "#9aa6a0", 0.5));
  return { scene, camera };
}

function shadowDisc(scene, r = 0.9) {
  const canvas = document.createElement("canvas");
  canvas.width = 64;
  canvas.height = 64;
  const g = canvas.getContext("2d");
  const grad = g.createRadialGradient(32, 32, 2, 32, 32, 32);
  grad.addColorStop(0, "rgba(0,0,0,0.28)");
  grad.addColorStop(1, "rgba(0,0,0,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, 64, 64);
  const disc = new THREE.Mesh(
    new THREE.PlaneGeometry(r * 2, r * 2),
    new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(canvas), transparent: true, depthWrite: false }),
  );
  disc.rotation.x = -Math.PI / 2;
  disc.position.y = 0.001;
  scene.add(disc);
}

/* ------------------------------------------------------------------ */
/* Scenes                                                              */
/* ------------------------------------------------------------------ */

function waterScene(value) {
  const { scene, camera } = baseScene();
  shadowDisc(scene);
  const chrome = physical({ color: "#dfe4e8", metalness: 1, roughness: 0.15 });
  const porcelain = physical({ color: "#ffffff", roughness: 0.15, clearcoat: 1 });
  const basin = new THREE.Mesh(new THREE.CylinderGeometry(0.75, 0.6, 0.28, 48, 1, true), porcelain);
  basin.position.y = 0.14;
  basin.material.side = THREE.DoubleSide;
  scene.add(basin);
  const bottom = new THREE.Mesh(new THREE.CircleGeometry(0.6, 48), porcelain);
  bottom.rotation.x = -Math.PI / 2;
  bottom.position.y = 0.01;
  scene.add(bottom);
  const flow = clamp01(value / 120);
  const pool = new THREE.Mesh(
    new THREE.CircleGeometry(0.6, 48),
    physical({ color: "#3aa7e0", roughness: 0.05, transparent: true, opacity: 0.8, clearcoat: 1 }),
  );
  pool.rotation.x = -Math.PI / 2;
  pool.position.y = 0.03 + flow * 0.18;
  pool.visible = value > 0;
  scene.add(pool);
  // Faucet.
  const post = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.09, 1.1, 24), chrome);
  post.position.set(-0.55, 0.55, -0.35);
  scene.add(post);
  const spout = new THREE.Mesh(new THREE.TorusGeometry(0.4, 0.06, 16, 32, Math.PI), chrome);
  spout.position.set(-0.15, 1.1, -0.35);
  scene.add(spout);
  const handle = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.36, 12), chrome);
  handle.rotation.z = Math.PI / 2;
  handle.position.set(-0.55, 1.08, -0.35);
  scene.add(handle);
  // Stream and droplets.
  const water = physical({ color: "#5cc2ff", roughness: 0.05, transparent: true, opacity: 0.75, emissive: "#1d6fa8", emissiveIntensity: 0.3 });
  const width = 0.02 + flow * 0.07;
  const stream = new THREE.Mesh(new THREE.CylinderGeometry(width, width * 1.3, 1.0, 16, 1, true), water);
  stream.position.set(0.25, 0.6, -0.35);
  stream.visible = value > 0;
  scene.add(stream);
  const drops = [];
  const count = value > 0 ? 6 + Math.round(flow * 14) : 0;
  for (let i = 0; i < count; i += 1) {
    const d = new THREE.Mesh(new THREE.SphereGeometry(0.035, 8, 6), water);
    d.userData.phase = Math.random();
    d.userData.dx = (Math.random() - 0.5) * 0.5;
    d.userData.dz = (Math.random() - 0.5) * 0.5;
    scene.add(d);
    drops.push(d);
  }
  return {
    scene,
    camera,
    update(t) {
      handle.rotation.y = value > 0 ? 0.6 : 0;
      stream.scale.x = 1 + Math.sin(t * 20) * 0.08;
      drops.forEach((d) => {
        const p = (t * 1.6 + d.userData.phase) % 1;
        d.position.set(0.25 + d.userData.dx * p, 0.1 + Math.sin(p * Math.PI) * 0.3 + pool.position.y, -0.35 + d.userData.dz * p);
      });
    },
  };
}

function bulbScene(value) {
  const { scene, camera } = baseScene();
  shadowDisc(scene, 0.7);
  const level = clamp01(value / 1500);
  const on = value > 0;
  const glass = physical({
    color: on ? "#ffe08a" : "#d8dde0",
    roughness: 0.05,
    transmission: 0.6,
    transparent: true,
    opacity: on ? 0.9 : 0.55,
    emissive: on ? "#ffcf5a" : "#000000",
    emissiveIntensity: on ? 0.6 + level * 2.2 : 0,
  });
  const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.5, 40, 28), glass);
  bulb.position.y = 1.0;
  bulb.scale.set(1, 1.08, 1);
  scene.add(bulb);
  const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.32, 0.3, 32), glass);
  neck.position.y = 0.55;
  scene.add(neck);
  const metal = physical({ color: "#b8bcc0", metalness: 1, roughness: 0.25 });
  for (let i = 0; i < 4; i += 1) {
    const ring = new THREE.Mesh(new THREE.CylinderGeometry(0.21, 0.21, 0.07, 24), metal);
    ring.position.y = 0.37 - i * 0.075;
    scene.add(ring);
  }
  const tip = new THREE.Mesh(new THREE.SphereGeometry(0.1, 16, 8), physical({ color: "#333", roughness: 0.6 }));
  tip.position.y = 0.08;
  scene.add(tip);
  const filament = new THREE.Mesh(
    new THREE.TorusKnotGeometry(0.13, 0.015, 64, 6, 2, 5),
    new THREE.MeshStandardMaterial({ color: "#222", emissive: on ? "#ffb12e" : "#000", emissiveIntensity: on ? 3 + level * 6 : 0 }),
  );
  filament.position.y = 1.0;
  scene.add(filament);
  const light = new THREE.PointLight("#ffcc70", on ? 2 + level * 6 : 0, 4, 2);
  light.position.y = 1.0;
  scene.add(light);
  const halo = new THREE.Mesh(
    new THREE.RingGeometry(0.62, 0.66, 48),
    new THREE.MeshBasicMaterial({ color: "#ffd166", transparent: true, opacity: on ? 0.6 : 0, side: THREE.DoubleSide }),
  );
  halo.position.y = 1.0;
  scene.add(halo);
  return {
    scene,
    camera,
    update(t) {
      if (!on) {
        return;
      }
      const flicker = 1 + Math.sin(t * 9) * 0.04 + Math.sin(t * 23) * 0.02;
      filament.material.emissiveIntensity = (3 + level * 6) * flicker;
      halo.lookAt(camera.position);
      halo.scale.setScalar(1 + ((t * 0.8) % 1) * 0.25);
      halo.material.opacity = 0.6 * (1 - ((t * 0.8) % 1));
      filament.rotation.y = t * 0.6;
    },
  };
}

function solarScene(value) {
  const { scene, camera } = baseScene();
  shadowDisc(scene);
  const level = clamp01(value / 1500);
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 128;
  const g = canvas.getContext("2d");
  g.fillStyle = "#0c1d3d";
  g.fillRect(0, 0, 128, 128);
  g.strokeStyle = "#6f86a8";
  g.lineWidth = 2;
  for (let i = 0; i <= 4; i += 1) {
    g.beginPath();
    g.moveTo((i * 128) / 4, 0);
    g.lineTo((i * 128) / 4, 128);
    g.stroke();
  }
  for (let j = 0; j <= 6; j += 1) {
    g.beginPath();
    g.moveTo(0, (j * 128) / 6);
    g.lineTo(128, (j * 128) / 6);
    g.stroke();
  }
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  const panel = new THREE.Mesh(
    new THREE.BoxGeometry(1.3, 0.05, 0.9),
    physical({ map: tex, roughness: 0.15, metalness: 0.3, clearcoat: 1 }),
  );
  panel.position.set(-0.1, 0.45, 0.2);
  panel.rotation.x = 0.55;
  scene.add(panel);
  const alu = physical({ color: "#c0c5ca", metalness: 0.9, roughness: 0.3 });
  [[-0.65, 0.25], [0.45, 0.25]].forEach(([x, h]) => {
    const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.5, 8), alu);
    leg.position.set(x, h, -0.1);
    scene.add(leg);
  });
  const day = value > 0;
  const sun = new THREE.Mesh(
    new THREE.SphereGeometry(0.28, 32, 16),
    new THREE.MeshStandardMaterial({
      color: day ? "#ffcf3f" : "#cfd6e0",
      emissive: day ? "#ffb300" : "#7d8ba1",
      emissiveIntensity: day ? 1.2 + level * 1.5 : 0.4,
    }),
  );
  sun.position.set(0.55, 1.25, -0.5);
  scene.add(sun);
  const rays = new THREE.Group();
  if (day) {
    const rayMat = new THREE.MeshStandardMaterial({ color: "#ffd34d", emissive: "#ffb300", emissiveIntensity: 1.2 });
    for (let i = 0; i < 10; i += 1) {
      const ray = new THREE.Mesh(new THREE.ConeGeometry(0.05, 0.18 + level * 0.12, 8), rayMat);
      const a = (i / 10) * Math.PI * 2;
      ray.position.set(Math.cos(a) * 0.42, Math.sin(a) * 0.42, 0);
      ray.rotation.z = a - Math.PI / 2;
      rays.add(ray);
    }
  }
  rays.position.copy(sun.position);
  scene.add(rays);
  const glint = new THREE.PointLight("#fff1b0", day ? 1.5 + level * 3 : 0, 5, 2);
  glint.position.set(0.6, 1.2, 0);
  scene.add(glint);
  return {
    scene,
    camera,
    update(t) {
      rays.lookAt(camera.position);
      rays.rotateZ(t * 0.5);
      sun.scale.setScalar(1 + Math.sin(t * 2) * 0.04);
    },
  };
}

function batteryScene(value) {
  const { scene, camera } = baseScene();
  shadowDisc(scene, 0.7);
  let pct = clamp01(value / 100);
  const shell = new THREE.Mesh(
    new RoundedBoxGeometry(0.8, 1.4, 0.8, 4, 0.12),
    physical({ color: "#eef2f4", roughness: 0.1, transparent: true, opacity: 0.35, clearcoat: 1, depthWrite: false }),
  );
  shell.position.y = 0.72;
  scene.add(shell);
  const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.16, 0.14, 24), physical({ color: "#9aa0a6", metalness: 0.9, roughness: 0.3 }));
  cap.position.y = 1.48;
  scene.add(cap);
  const color = levelColor(value);
  const fillMat = physical({ color, emissive: color, emissiveIntensity: 0.25, roughness: 0.35 });
  const fill = new THREE.Mesh(new RoundedBoxGeometry(0.66, 1, 0.66, 3, 0.08).translate(0, 0.5, 0), fillMat);
  fill.position.y = 0.09;
  scene.add(fill);
  const bolt = new THREE.Shape();
  bolt.moveTo(0.05, 0.25);
  bolt.lineTo(-0.12, -0.02);
  bolt.lineTo(0.0, -0.02);
  bolt.lineTo(-0.05, -0.25);
  bolt.lineTo(0.12, 0.04);
  bolt.lineTo(0.0, 0.04);
  bolt.closePath();
  const boltMesh = new THREE.Mesh(
    new THREE.ExtrudeGeometry(bolt, { depth: 0.04, bevelEnabled: false }),
    new THREE.MeshStandardMaterial({ color: "#ffffff", emissive: "#ffffff", emissiveIntensity: 0.6 }),
  );
  boltMesh.position.set(0, 0.75, 0.42);
  scene.add(boltMesh);
  let shown = 0;
  return {
    scene,
    camera,
    setValue(v) {
      pct = clamp01(v / 100);
      const c = levelColor(v);
      fillMat.color.copy(c);
      fillMat.emissive.copy(c);
    },
    update(t) {
      shown += (pct - shown) * 0.06;
      if (REDUCED) {
        shown = pct;
      }
      fill.scale.y = Math.max(0.01, shown * 1.24);
      fillMat.emissiveIntensity = 0.2 + Math.sin(t * 3) * 0.1;
    },
  };
}

function tankScene(value) {
  const { scene, camera } = baseScene();
  shadowDisc(scene);
  let pct = clamp01(value / 100);
  const shell = new THREE.Mesh(
    new THREE.CylinderGeometry(0.65, 0.65, 1.3, 48, 1, true),
    physical({ color: "#e9f3f7", roughness: 0.1, transparent: true, opacity: 0.3, side: THREE.DoubleSide, depthWrite: false, clearcoat: 1 }),
  );
  shell.position.y = 0.67;
  scene.add(shell);
  const steel = physical({ color: "#c4c9cd", metalness: 0.9, roughness: 0.3 });
  [0.03, 1.32].forEach((y) => {
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.66, 0.035, 10, 48), steel);
    ring.rotation.x = Math.PI / 2;
    ring.position.y = y;
    scene.add(ring);
  });
  const color = pct < 0.2 ? "#e5483b" : "#2a8fd0";
  const waterMat = physical({ color, roughness: 0.05, transparent: true, opacity: 0.85, clearcoat: 1 });
  const water = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.62, 1, 48).translate(0, 0.5, 0), waterMat);
  water.position.y = 0.04;
  scene.add(water);
  const surfaceGeo = new THREE.CircleGeometry(0.62, 40, 0, Math.PI * 2);
  const surface = new THREE.Mesh(surfaceGeo, physical({ color: "#7fd0ff", roughness: 0.02, transparent: true, opacity: 0.9, clearcoat: 1 }));
  surface.rotation.x = -Math.PI / 2;
  scene.add(surface);
  const base = surfaceGeo.attributes.position.array.slice();
  let shown = 0;
  return {
    scene,
    camera,
    setValue(v) {
      pct = clamp01(v / 100);
      waterMat.color.set(pct < 0.2 ? "#e5483b" : "#2a8fd0");
    },
    update(t) {
      shown += (pct - shown) * 0.05;
      if (REDUCED) {
        shown = pct;
      }
      const h = Math.max(0.01, shown * 1.24);
      water.scale.y = h;
      surface.position.y = 0.04 + h + 0.002;
      const pos = surfaceGeo.attributes.position;
      for (let i = 0; i < pos.count; i += 1) {
        const x = base[i * 3];
        const y = base[i * 3 + 1];
        pos.setZ(i, Math.sin(x * 9 + t * 3) * 0.012 + Math.cos(y * 8 + t * 2.4) * 0.012);
      }
      pos.needsUpdate = true;
    },
  };
}

function resilienceScene(value) {
  const { scene, camera } = baseScene();
  camera.position.set(0, 0.75, 3.6);
  camera.lookAt(0, 0.75, 0);
  let pct = clamp01(value / 100);
  const track = new THREE.Mesh(
    new THREE.TorusGeometry(0.85, 0.07, 16, 96),
    physical({ color: "#dfe5e2", roughness: 0.5 }),
  );
  track.position.y = 0.75;
  scene.add(track);
  const color = levelColor(value);
  const arcMat = physical({ color, emissive: color, emissiveIntensity: 0.5, roughness: 0.25, clearcoat: 1 });
  let arc = null;
  const shield = new THREE.Shape();
  shield.moveTo(0, 0.48);
  shield.quadraticCurveTo(0.22, 0.4, 0.4, 0.42);
  shield.quadraticCurveTo(0.42, -0.1, 0, -0.5);
  shield.quadraticCurveTo(-0.42, -0.1, -0.4, 0.42);
  shield.quadraticCurveTo(-0.22, 0.4, 0, 0.48);
  const shieldMesh = new THREE.Mesh(
    new THREE.ExtrudeGeometry(shield, { depth: 0.12, bevelEnabled: true, bevelThickness: 0.04, bevelSize: 0.04, bevelSegments: 4 }),
    physical({ color: "#0f6e6e", metalness: 0.3, roughness: 0.3, clearcoat: 1 }),
  );
  shieldMesh.position.set(0, 0.78, -0.06);
  scene.add(shieldMesh);
  const tick = new THREE.Shape();
  tick.moveTo(-0.19, 0.02);
  tick.lineTo(-0.06, -0.13);
  tick.lineTo(0.2, 0.16);
  tick.lineTo(0.14, 0.21);
  tick.lineTo(-0.06, -0.01);
  tick.lineTo(-0.13, 0.07);
  tick.closePath();
  const check = new THREE.Mesh(
    new THREE.ExtrudeGeometry(tick, { depth: 0.05, bevelEnabled: false }),
    new THREE.MeshStandardMaterial({ color: "#ffffff", emissive: "#ffffff", emissiveIntensity: 0.5 }),
  );
  check.position.set(0, 0.8, 0.1);
  scene.add(check);
  let shown = 0;
  let built = -1;
  return {
    scene,
    camera,
    setValue(v) {
      pct = clamp01(v / 100);
      const c = levelColor(v);
      arcMat.color.copy(c);
      arcMat.emissive.copy(c);
    },
    update(t) {
      shown += (pct - shown) * 0.05;
      if (REDUCED) {
        shown = pct;
      }
      const step = Math.round(shown * 100);
      if (step !== built && step > 0) {
        built = step;
        if (arc) {
          scene.remove(arc);
          arc.geometry.dispose();
        }
        arc = new THREE.Mesh(new THREE.TorusGeometry(0.85, 0.09, 16, 96, (Math.PI * 2 * step) / 100), arcMat);
        arc.position.y = 0.75;
        arc.rotation.z = Math.PI / 2;
        arc.scale.x = -1;
        scene.add(arc);
      }
      shieldMesh.rotation.y = Math.sin(t * 0.9) * 0.35;
      check.rotation.y = shieldMesh.rotation.y;
    },
  };
}

function alertScene(value) {
  const { scene, camera } = baseScene();
  shadowDisc(scene, 0.7);
  const group = new THREE.Group();
  scene.add(group);
  let mode = null;
  let parts = {};
  function build(alert) {
    group.clear();
    parts = {};
    const base = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.5, 0.22, 40), physical({ color: "#2b3236", metalness: 0.6, roughness: 0.35 }));
    base.position.y = 0.11;
    group.add(base);
    if (alert) {
      const domeMat = physical({ color: "#ff3b2f", emissive: "#ff2a1a", emissiveIntensity: 1.6, roughness: 0.1, transparent: true, opacity: 0.9, clearcoat: 1 });
      const dome = new THREE.Mesh(new THREE.SphereGeometry(0.38, 40, 20, 0, Math.PI * 2, 0, Math.PI / 2), domeMat);
      dome.position.y = 0.22;
      dome.scale.y = 1.5;
      group.add(dome);
      const beam = new THREE.Mesh(
        new THREE.ConeGeometry(0.35, 0.9, 24, 1, true),
        new THREE.MeshBasicMaterial({ color: "#ff5a4a", transparent: true, opacity: 0.22, side: THREE.DoubleSide, depthWrite: false }),
      );
      beam.rotation.z = Math.PI / 2;
      beam.position.set(0.55, 0.45, 0);
      const pivot = new THREE.Group();
      pivot.add(beam);
      pivot.position.y = 0;
      group.add(pivot);
      const light = new THREE.PointLight("#ff3b2f", 4, 5, 2);
      light.position.y = 0.6;
      group.add(light);
      parts = { dome: domeMat, pivot, light };
    } else {
      const orbMat = physical({ color: "#2fbf71", emissive: "#1f9d5a", emissiveIntensity: 0.6, roughness: 0.15, clearcoat: 1 });
      const orb = new THREE.Mesh(new THREE.SphereGeometry(0.42, 40, 24), orbMat);
      orb.position.y = 0.72;
      group.add(orb);
      const tick = new THREE.Shape();
      tick.moveTo(-0.19, 0.02);
      tick.lineTo(-0.06, -0.13);
      tick.lineTo(0.2, 0.16);
      tick.lineTo(0.14, 0.21);
      tick.lineTo(-0.06, -0.01);
      tick.lineTo(-0.13, 0.07);
      tick.closePath();
      const check = new THREE.Mesh(
        new THREE.ExtrudeGeometry(tick, { depth: 0.05, bevelEnabled: false }),
        new THREE.MeshStandardMaterial({ color: "#ffffff", emissive: "#ffffff", emissiveIntensity: 0.6 }),
      );
      check.position.set(0, 0.72, 0.4);
      group.add(check);
      parts = { orb, check };
    }
  }
  function set(v) {
    const alert = v > 0;
    if (alert !== mode) {
      mode = alert;
      build(alert);
    }
  }
  set(value);
  return {
    scene,
    camera,
    setValue: set,
    update(t) {
      if (mode) {
        parts.pivot.rotation.y = t * 4;
        const blink = 0.5 + 0.5 * Math.sin(t * 8);
        parts.dome.emissiveIntensity = 0.8 + blink * 2;
        parts.light.intensity = 2 + blink * 5;
      } else {
        const y = 0.72 + Math.sin(t * 2) * 0.05;
        parts.orb.position.y = y;
        const dir = new THREE.Vector3(camera.position.x, 0, camera.position.z).normalize();
        parts.check.position.set(dir.x * 0.4, y, dir.z * 0.4);
        parts.check.lookAt(camera.position.x, y, camera.position.z);
      }
    },
  };
}

const BUILDERS = {
  alert: alertScene,
  water: waterScene,
  electricity: bulbScene,
  solar: solarScene,
  battery: batteryScene,
  tank: tankScene,
  resilience: resilienceScene,
};

/* ------------------------------------------------------------------ */
/* Shared renderer                                                     */
/* ------------------------------------------------------------------ */

function boot() {
  const canvases = [...document.querySelectorAll("canvas[data-metric3d]")];
  if (!canvases.length) {
    return;
  }
  const probe = document.createElement("canvas");
  if (!probe.getContext("webgl2")) {
    return;
  }
  const style = document.createElement("style");
  style.textContent = CSS;
  document.head.appendChild(style);

  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(dpr);
  renderer.setSize(SIZE, SIZE, false);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.setClearColor(0x000000, 0);
  const env = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;

  const items = canvases.map((canvas) => {
    const build = BUILDERS[canvas.dataset.metric3d];
    if (!build) {
      return null;
    }
    canvas.closest(".placeholder-card")?.classList.add("has-3d");
    canvas.hidden = false;
    canvas.width = SIZE * dpr;
    canvas.height = SIZE * dpr;
    const view = build(number(canvas.dataset.value));
    view.scene.environment = env;
    view.scene.environmentIntensity = 0.6;
    const item = { canvas, ctx: canvas.getContext("2d"), view, visible: true };
    // Follow a live number on the page (live.js updates it every simulated hour).
    const source = canvas.dataset.liveSource && document.querySelector(`[data-live-text="${canvas.dataset.liveSource}"]`);
    if (source) {
      const read = () => {
        const text = source.textContent || "";
        const v = canvas.dataset.metric3d === "alert" ? (/calme/i.test(text) ? 0 : 1) : number(text);
        if (item.view.setValue) {
          item.view.setValue(v);
        } else {
          item.view = build(v);
          item.view.scene.environment = env;
          item.view.scene.environmentIntensity = 0.6;
        }
        if (REDUCED) {
          draw(item, 0);
        }
      };
      new MutationObserver(read).observe(source, { childList: true, characterData: true, subtree: true });
    }
    return item;
  }).filter(Boolean);

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      const item = items.find((i) => i.canvas === entry.target);
      if (item) {
        item.visible = entry.isIntersecting;
      }
    });
  });
  items.forEach((item) => observer.observe(item.canvas));

  const clock = new THREE.Clock();
  function draw(item, t) {
    item.view.update(t);
    renderer.render(item.view.scene, item.view.camera);
    item.ctx.clearRect(0, 0, item.canvas.width, item.canvas.height);
    item.ctx.drawImage(renderer.domElement, 0, 0, item.canvas.width, item.canvas.height);
  }

  if (REDUCED) {
    items.forEach((item) => draw(item, 0));
    return;
  }
  function frame() {
    if (!document.hidden) {
      const t = clock.getElapsedTime();
      items.forEach((item) => {
        if (item.visible) {
          draw(item, t);
        }
      });
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

boot();
