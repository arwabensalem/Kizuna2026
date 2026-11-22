// Fond animé de la page d'accueil : un survol lent d'un paysage tunisien
// réaliste. Un village de maisons blanches avec panneaux solaires et
// citernes sur les toits, des oliveraies, une ferme solaire, un château
// d'eau et un bassin. Le soleil se déplace, les fenêtres s'allument au
// crépuscule, et l'eau (bleu), l'énergie (ambre) et les récoltes (vert)
// circulent doucement entre les lieux.
// Pause quand l'onglet est caché ou le bandeau hors écran. Image fixe si
// l'utilisateur préfère moins d'animations. Sans WebGL : simple dégradé.
import * as THREE from "three";
import { Sky } from "three/addons/objects/Sky.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import * as T3 from "./twin3d.js?v=demo2";

const canvas = document.getElementById("kz-home-bg");
const hero = canvas && canvas.closest(".kz-hero");

/* ------------------------------------------------------------------ */
/* Outils                                                              */
/* ------------------------------------------------------------------ */

function rng(seed) {
  let s = seed >>> 0 || 1;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function hash(i, j) {
  const v = Math.sin(i * 127.1 + j * 311.7) * 43758.5453;
  return v - Math.floor(v);
}

function noise(x, z) {
  const i = Math.floor(x);
  const j = Math.floor(z);
  const fx = x - i;
  const fz = z - j;
  const u = fx * fx * (3 - 2 * fx);
  const v = fz * fz * (3 - 2 * fz);
  const a = hash(i, j);
  const b = hash(i + 1, j);
  const c = hash(i, j + 1);
  const d = hash(i + 1, j + 1);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}

function fbm(x, z, oct = 4) {
  let sum = 0;
  let amp = 0.5;
  let f = 1;
  for (let o = 0; o < oct; o += 1) {
    sum += amp * noise(x * f, z * f);
    f *= 2.03;
    amp *= 0.5;
  }
  return sum;
}

const smooth = (a, b, x) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

// Zones aplanies (village, ferme solaire, bassin), le reste ondule
// doucement, puis des montagnes au loin.
const FLAT = [
  { x: 0, z: 0, r: 34 },
  { x: -68, z: -32, r: 34 },
  { x: -46, z: 34, r: 16 },
];

function height(x, z) {
  const r = Math.hypot(x, z);
  let h = (fbm(x * 0.012, z * 0.012) - 0.5) * 9;
  h += (fbm(x * 0.05 + 7, z * 0.05 + 3, 3) - 0.5) * 1.4;
  for (const f of FLAT) {
    const d = Math.hypot(x - f.x, z - f.z);
    h *= smooth(f.r * 0.7, f.r * 1.25, d);
  }
  const m = smooth(210, 360, r);
  h += m * (25 + fbm(x * 0.008 + 11, z * 0.008 - 5, 5) * 95);
  return h;
}

// Une route de terre qui traverse le village.
function roadDist(x, z) {
  const zr = Math.sin(x * 0.018) * 14 + 4;
  return Math.abs(z - zr);
}

function canvasTexture(size, draw, repeat) {
  const c = document.createElement("canvas");
  c.width = size;
  c.height = size;
  draw(c.getContext("2d"), size);
  const t = new THREE.CanvasTexture(c);
  t.wrapS = THREE.RepeatWrapping;
  t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(repeat, repeat);
  t.anisotropy = 8;
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

/* ------------------------------------------------------------------ */
/* Décor                                                               */
/* ------------------------------------------------------------------ */

function makeTerrain() {
  const size = 760;
  const seg = 190;
  const geo = new THREE.PlaneGeometry(size, size, seg, seg);
  geo.rotateX(-Math.PI / 2);
  const p = geo.attributes.position;
  const col = new Float32Array(p.count * 3);
  const sand = new THREE.Color("#c8a676");
  const dry = new THREE.Color("#a98a5f");
  const green = new THREE.Color("#7f8a4c");
  const soil = new THREE.Color("#8e6a48");
  const road = new THREE.Color("#d8c3a0");
  const rock = new THREE.Color("#8a7a68");
  const c = new THREE.Color();
  for (let i = 0; i < p.count; i += 1) {
    const x = p.getX(i);
    const z = p.getZ(i);
    const y = height(x, z);
    p.setY(i, y);
    const n = fbm(x * 0.03 + 50, z * 0.03 - 20, 3);
    c.copy(sand).lerp(dry, n);
    // Champs d'oliviers : terre labourée plus sombre.
    if (x > 28 && x < 140 && z > -75 && z < 80) {
      c.lerp(soil, 0.55 * smooth(28, 36, x) * (1 - smooth(132, 140, x)));
    }
    c.lerp(green, smooth(0.55, 0.75, fbm(x * 0.02 - 9, z * 0.02 + 4, 3)) * 0.6);
    c.lerp(rock, smooth(14, 40, y) * 0.7);
    const rd = roadDist(x, z);
    if (Math.abs(x) < 170) {
      c.lerp(road, (1 - smooth(2.2, 4.2, rd)) * 0.9);
    }
    col[i * 3] = c.r;
    col[i * 3 + 1] = c.g;
    col[i * 3 + 2] = c.b;
  }
  geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
  geo.computeVertexNormals();
  const detail = canvasTexture(256, (g, s) => {
    const rand = rng(5);
    g.fillStyle = "#d8d8d8";
    g.fillRect(0, 0, s, s);
    for (let i = 0; i < 9000; i += 1) {
      g.fillStyle = rand() > 0.5 ? "rgba(255,255,255,0.18)" : "rgba(60,40,20,0.16)";
      const r = 1 + rand() * 2.5;
      g.fillRect(rand() * s, rand() * s, r, r);
    }
  }, 140);
  const mat = new THREE.MeshStandardMaterial({ vertexColors: true, map: detail, roughness: 1, metalness: 0 });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.receiveShadow = true;
  return mesh;
}

// Oliviers en instances : un tronc tordu et trois masses de feuillage
// gris-vert, alignés en rangs comme dans le Sahel.
function makeOlives(scene) {
  const rand = rng(21);
  const spots = [];
  for (let x = 36; x < 132; x += 7) {
    for (let z = -70; z < 76; z += 7) {
      if (rand() < 0.08) {
        continue;
      }
      spots.push([x + (rand() - 0.5) * 1.4, z + (rand() - 0.5) * 1.4]);
    }
  }
  // Quelques oliviers isolés autour du village.
  for (let i = 0; i < 40; i += 1) {
    const a = rand() * Math.PI * 2;
    const r = 40 + rand() * 60;
    const x = Math.cos(a) * r;
    const z = Math.sin(a) * r;
    if (roadDist(x, z) > 6 && !(x < -30 && z < 5 && x > -110)) {
      spots.push([x, z]);
    }
  }
  const trunkGeo = new THREE.CylinderGeometry(0.22, 0.38, 2.2, 7);
  trunkGeo.translate(0, 1.1, 0);
  const leafGeo = new THREE.IcosahedronGeometry(1, 2);
  const lp = leafGeo.attributes.position;
  for (let i = 0; i < lp.count; i += 1) {
    const k = 1 + (noise(lp.getX(i) * 3 + 4, lp.getZ(i) * 3 + lp.getY(i) * 2) - 0.5) * 0.45;
    lp.setXYZ(i, lp.getX(i) * k, lp.getY(i) * k, lp.getZ(i) * k);
  }
  leafGeo.computeVertexNormals();
  const trunkMat = new THREE.MeshStandardMaterial({ color: "#5d4a3a", roughness: 0.95 });
  const leafMat = new THREE.MeshStandardMaterial({ color: "#7b8b5c", roughness: 0.9 });
  const trunks = new THREE.InstancedMesh(trunkGeo, trunkMat, spots.length);
  const leaves = new THREE.InstancedMesh(leafGeo, leafMat, spots.length * 3);
  trunks.castShadow = true;
  leaves.castShadow = true;
  leaves.receiveShadow = true;
  const m = new THREE.Matrix4();
  const q = new THREE.Quaternion();
  const e = new THREE.Euler();
  const s = new THREE.Vector3();
  const v = new THREE.Vector3();
  const tint = new THREE.Color();
  spots.forEach(([x, z], i) => {
    const y = height(x, z);
    const k = 0.8 + rand() * 0.5;
    e.set((rand() - 0.5) * 0.25, rand() * 6, (rand() - 0.5) * 0.25);
    q.setFromEuler(e);
    m.compose(v.set(x, y - 0.1, z), q, s.set(k, k, k));
    trunks.setMatrixAt(i, m);
    for (let j = 0; j < 3; j += 1) {
      const a = j * 2.1 + rand();
      const r = 0.7 * k;
      v.set(x + Math.cos(a) * r, y + 2.5 * k + rand() * 0.6 * k, z + Math.sin(a) * r);
      const w = (1.3 + rand() * 0.5) * k;
      m.compose(v, q, s.set(w, w * 0.72, w));
      leaves.setMatrixAt(i * 3 + j, m);
      tint.setHSL(0.2 + rand() * 0.04, 0.18 + rand() * 0.08, 0.36 + rand() * 0.08);
      leaves.setColorAt(i * 3 + j, tint);
    }
  });
  scene.add(trunks, leaves);
}

// Palmiers dattiers autour du village.
function palm(x, z, seed) {
  const rand = rng(seed);
  const g = new THREE.Group();
  const y = height(x, z);
  const h = 8 + rand() * 4;
  const lean = new THREE.Vector3((rand() - 0.5) * 1.6, 0, (rand() - 0.5) * 1.6);
  const curve = new THREE.QuadraticBezierCurve3(
    new THREE.Vector3(x, y, z),
    new THREE.Vector3(x + lean.x * 0.3, y + h * 0.55, z + lean.z * 0.3),
    new THREE.Vector3(x + lean.x, y + h, z + lean.z),
  );
  const trunk = new THREE.Mesh(
    new THREE.TubeGeometry(curve, 10, 0.28, 7, false),
    new THREE.MeshStandardMaterial({ color: "#7a6247", roughness: 1 }),
  );
  trunk.castShadow = true;
  g.add(trunk);
  const top = curve.getPoint(1);
  const frondGeo = new THREE.PlaneGeometry(1.1, 5.5, 1, 8);
  frondGeo.translate(0, 2.75, 0);
  const fp = frondGeo.attributes.position;
  for (let i = 0; i < fp.count; i += 1) {
    const t = fp.getY(i) / 5.5;
    fp.setZ(i, -t * t * 2.6);
    fp.setX(i, fp.getX(i) * (1 - t * 0.85));
  }
  frondGeo.computeVertexNormals();
  const frondMat = new THREE.MeshStandardMaterial({ color: "#5b7a3a", roughness: 0.85, side: THREE.DoubleSide });
  const n = 11;
  for (let i = 0; i < n; i += 1) {
    const f = new THREE.Mesh(frondGeo, frondMat);
    f.position.copy(top);
    f.rotation.set(-Math.PI / 2 + 0.55 + rand() * 0.4, (i / n) * Math.PI * 2 + rand() * 0.3, 0, "YXZ");
    f.castShadow = true;
    f.userData.sway = rand() * 6;
    g.add(f);
  }
  return g;
}

// Maison blanche à toit plat, menuiseries bleu de Sidi Bou Saïd,
// citerne et panneaux solaires sur le toit.
function house(x, z, w, d, floors, seed, windowMat, mats) {
  const rand = rng(seed);
  const g = new THREE.Group();
  const y = height(x, z);
  const hh = floors * 3.1;
  const add = (geo, mat, px, py, pz, shadow = true) => {
    const m = new THREE.Mesh(geo, mat);
    m.position.set(px, py, pz);
    m.castShadow = shadow;
    m.receiveShadow = true;
    g.add(m);
    return m;
  };
  add(new THREE.BoxGeometry(w, hh, d), mats.wall, 0, hh / 2, 0);
  // Acrotère.
  const pt = 0.25;
  add(new THREE.BoxGeometry(w, 0.6, pt), mats.wall, 0, hh + 0.3, d / 2 - pt / 2);
  add(new THREE.BoxGeometry(w, 0.6, pt), mats.wall, 0, hh + 0.3, -d / 2 + pt / 2);
  add(new THREE.BoxGeometry(pt, 0.6, d), mats.wall, w / 2 - pt / 2, hh + 0.3, 0);
  add(new THREE.BoxGeometry(pt, 0.6, d), mats.wall, -w / 2 + pt / 2, hh + 0.3, 0);
  // Fenêtres et porte sur chaque face.
  const winGeo = new THREE.BoxGeometry(1.1, 1.35, 0.12);
  const shutterGeo = new THREE.BoxGeometry(0.5, 1.45, 0.08);
  for (let f = 0; f < floors; f += 1) {
    const wy = f * 3.1 + 1.75;
    const nx = Math.max(1, Math.floor(w / 3.2));
    for (let i = 0; i < nx; i += 1) {
      const wx = -w / 2 + (w / nx) * (i + 0.5);
      for (const side of [1, -1]) {
        if (f === 0 && i === 0 && side === 1) {
          add(new THREE.BoxGeometry(1.2, 2.3, 0.12), mats.blue, wx, 1.15, side * (d / 2 + 0.02), false);
          continue;
        }
        add(winGeo, windowMat, wx, wy, side * (d / 2 + 0.02), false);
        add(shutterGeo, mats.blue, wx - 0.82, wy, side * (d / 2 + 0.05), false);
        add(shutterGeo, mats.blue, wx + 0.82, wy, side * (d / 2 + 0.05), false);
      }
    }
    const nz = Math.max(1, Math.floor(d / 3.4));
    for (let i = 0; i < nz; i += 1) {
      const wz = -d / 2 + (d / nz) * (i + 0.5);
      for (const side of [1, -1]) {
        const m = add(winGeo, windowMat, side * (w / 2 + 0.02), wy, wz, false);
        m.rotation.y = Math.PI / 2;
      }
    }
  }
  // Panneaux solaires inclinés plein sud.
  const rows = Math.max(1, Math.floor((d - 2) / 2.2));
  const cols = Math.max(1, Math.floor((w - 1.6) / 1.15));
  const panelGeo = new THREE.BoxGeometry(1.05, 0.05, 1.7);
  for (let r = 0; r < Math.min(rows, 2); r += 1) {
    for (let c = 0; c < Math.min(cols, 5); c += 1) {
      const pnl = add(panelGeo, mats.solar, -w / 2 + 0.9 + c * 1.15, hh + 0.7, -d / 2 + 1.6 + r * 2.3);
      pnl.rotation.x = 0.55;
      add(new THREE.BoxGeometry(0.06, 0.6, 0.06), mats.alu, -w / 2 + 0.9 + c * 1.15, hh + 0.3, -d / 2 + 2.2 + r * 2.3, false);
    }
  }
  // Citerne d'eau sur le toit (typique en Tunisie).
  if (rand() > 0.25) {
    const tx = w / 2 - 1.2;
    const tz = d / 2 - 1.3;
    add(new THREE.CylinderGeometry(0.62, 0.62, 1.4, 18), mats.tank, tx, hh + 0.75, tz);
    add(new THREE.CylinderGeometry(0.18, 0.18, 0.15, 10), mats.tank, tx, hh + 1.5, tz, false);
  }
  // Petite coupole sur certaines maisons.
  if (rand() > 0.7) {
    add(new THREE.SphereGeometry(1.5, 22, 12, 0, Math.PI * 2, 0, Math.PI / 2), mats.wall, -w / 4, hh, d / 4);
  }
  g.position.set(x, y - 0.05, z);
  g.rotation.y = (rand() - 0.5) * 0.25;
  return g;
}

function makeVillage(scene, windowMat, mats) {
  const rand = rng(33);
  const spots = [
    [-14, -14], [-2, -18], [11, -15], [22, -8], [-22, 2], [-9, 14], [6, 19], [19, 16],
    [-26, -16], [26, 24], [-17, 24], [3, -30], [-5, 32], [15, 32],
  ];
  spots.forEach(([x, z], i) => {
    if (roadDist(x, z) < 6.5) {
      z += z > Math.sin(x * 0.018) * 14 + 4 ? 4 : -4;
    }
    const w = 7 + rand() * 4;
    const d = 6.5 + rand() * 3;
    const floors = rand() > 0.6 ? 2 : 1;
    scene.add(house(x, z, w, d, floors, 100 + i, windowMat, mats));
  });
  const rp = rng(44);
  for (let i = 0; i < 16; i += 1) {
    const a = rp() * Math.PI * 2;
    const r = 8 + rp() * 30;
    const x = Math.cos(a) * r;
    const z = Math.sin(a) * r;
    if (spots.every(([sx, sz]) => Math.hypot(sx - x, sz - z) > 7)) {
      scene.add(palm(x, z, 200 + i));
    }
  }
}

// Ferme solaire : rangées de panneaux en instances.
function makeSolarFarm(scene, mats) {
  const cx = -68;
  const cz = -32;
  const list = [];
  for (let r = 0; r < 9; r += 1) {
    for (let c = 0; c < 14; c += 1) {
      list.push([cx - 26 + c * 4, cz - 20 + r * 5]);
    }
  }
  const panelGeo = new THREE.BoxGeometry(3.7, 0.08, 2.2);
  const legGeo = new THREE.BoxGeometry(0.1, 1.4, 0.1);
  const panels = new THREE.InstancedMesh(panelGeo, mats.solar, list.length);
  const legs = new THREE.InstancedMesh(legGeo, mats.alu, list.length * 2);
  panels.castShadow = true;
  panels.receiveShadow = true;
  const m = new THREE.Matrix4();
  const q = new THREE.Quaternion().setFromEuler(new THREE.Euler(0.5, 0, 0));
  const one = new THREE.Vector3(1, 1, 1);
  const v = new THREE.Vector3();
  const q0 = new THREE.Quaternion();
  list.forEach(([x, z], i) => {
    const y = height(x, z);
    m.compose(v.set(x, y + 1.5, z), q, one);
    panels.setMatrixAt(i, m);
    m.compose(v.set(x - 1.5, y + 0.7, z + 0.4), q0, one);
    legs.setMatrixAt(i * 2, m);
    m.compose(v.set(x + 1.5, y + 0.7, z + 0.4), q0, one);
    legs.setMatrixAt(i * 2 + 1, m);
  });
  scene.add(panels, legs);
  // Petit local onduleur.
  const hut = new THREE.Mesh(new THREE.BoxGeometry(4, 2.6, 3), mats.wall);
  hut.position.set(cx + 32, height(cx + 32, cz) + 1.3, cz);
  hut.castShadow = true;
  scene.add(hut);
}

function makeWater(scene, mats, envMat) {
  // Château d'eau.
  const tx = -22;
  const tz = 40;
  const ty = height(tx, tz);
  const g = new THREE.Group();
  for (let i = 0; i < 4; i += 1) {
    const a = (i / 4) * Math.PI * 2 + Math.PI / 4;
    const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.38, 11, 10), mats.concrete);
    leg.position.set(Math.cos(a) * 2.6, 5.5, Math.sin(a) * 2.6);
    leg.castShadow = true;
    g.add(leg);
  }
  const tank = new THREE.Mesh(new THREE.CylinderGeometry(4, 3.2, 4.5, 28), mats.concrete);
  tank.position.y = 13;
  tank.castShadow = true;
  g.add(tank);
  const lid = new THREE.Mesh(new THREE.ConeGeometry(4.2, 1.4, 28), mats.concrete);
  lid.position.y = 16;
  lid.castShadow = true;
  g.add(lid);
  g.position.set(tx, ty, tz);
  scene.add(g);
  // Bassin de rétention.
  const pond = new THREE.Mesh(new THREE.CircleGeometry(10, 48), envMat);
  pond.rotation.x = -Math.PI / 2;
  pond.position.set(-46, height(-46, 34) + 0.12, 34);
  pond.scale.set(1.3, 0.8, 1);
  scene.add(pond);
  const rim = new THREE.Mesh(new THREE.RingGeometry(10, 10.8, 48), mats.concrete);
  rim.rotation.x = -Math.PI / 2;
  rim.position.copy(pond.position).y += 0.05;
  rim.scale.copy(pond.scale);
  scene.add(rim);
  return pond;
}

// Flux lumineux : un fil discret le long du sol, et des perles qui
// avancent (eau en bleu, énergie en ambre, récoltes en vert).
function makeFlows(scene) {
  const routes = [
    { color: "#ffc94a", pts: [[-50, -30], [-34, -18], [-18, -8], [-6, -10], [10, -6]] },
    { color: "#ffc94a", pts: [[-42, -26], [-30, 4], [-16, 14], [4, 16], [18, 12]] },
    { color: "#4cc3ff", pts: [[-22, 40], [-12, 28], [-4, 12], [-2, -4]] },
    { color: "#4cc3ff", pts: [[-46, 34], [-30, 38], [-22, 40]] },
    { color: "#4cc3ff", pts: [[-22, 40], [10, 44], [40, 30], [70, 20]] },
    { color: "#5fd38a", pts: [[96, -10], [60, -4], [34, 2], [16, 4]] },
  ];
  const flows = [];
  const pearlGeo = new THREE.SphereGeometry(0.42, 12, 8);
  for (const r of routes) {
    const pts = [];
    for (let i = 0; i < r.pts.length; i += 1) {
      const [x, z] = r.pts[i];
      pts.push(new THREE.Vector3(x, height(x, z) + 1.1, z));
    }
    const base = new THREE.CatmullRomCurve3(pts);
    // Échantillonne et colle au relief.
    const fine = base.getSpacedPoints(80).map((p) => p.setY(height(p.x, p.z) + 1.1));
    const curve = new THREE.CatmullRomCurve3(fine);
    const color = new THREE.Color(r.color);
    const line = new THREE.Mesh(
      new THREE.TubeGeometry(curve, 160, 0.09, 5, false),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.35, toneMapped: false }),
    );
    scene.add(line);
    const n = Math.round(curve.getLength() / 9);
    const pearls = new THREE.InstancedMesh(
      pearlGeo,
      new THREE.MeshBasicMaterial({ color: color.clone().multiplyScalar(2.6), toneMapped: false }),
      n,
    );
    scene.add(pearls);
    flows.push({ curve, pearls, n, offset: Math.random() });
  }
  return flows;
}

/* ------------------------------------------------------------------ */
/* Scène                                                               */
/* ------------------------------------------------------------------ */

function injectCss() {
  const css = `
.kz-hero-bg { opacity: 0; transition: opacity 1.6s ease; }
.kz-hero-bg.is-ready { opacity: 1; }
.kz-hero-shade {
  position: absolute; inset: 0; pointer-events: none;
  background:
    linear-gradient(90deg, rgba(3, 26, 28, 0.8) 0%, rgba(3, 26, 28, 0.55) 36%, rgba(3, 26, 28, 0.1) 70%, rgba(3, 26, 28, 0) 100%),
    linear-gradient(0deg, rgba(3, 26, 28, 0.45) 0%, rgba(3, 26, 28, 0) 30%);
}
@media (max-width: 768px) {
  .kz-hero-shade { background: rgba(3, 26, 28, 0.7); }
}`;
  const style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);
  const shade = document.createElement("div");
  shade.className = "kz-hero-shade";
  shade.setAttribute("aria-hidden", "true");
  canvas.after(shade);
}

function supportsWebGL() {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch (e) {
    return false;
  }
}

function start() {
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const speed = window.KZ_HERO_SPEED || 1;
  injectCss();

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.55;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(42, 2, 0.5, 4000);

  // Ciel physique (diffusion de Rayleigh et Mie).
  const sky = new Sky();
  sky.scale.setScalar(3000);
  const su = sky.material.uniforms;
  su.turbidity.value = 3.2;
  su.rayleigh.value = 1.3;
  su.mieCoefficient.value = 0.004;
  su.mieDirectionalG.value = 0.82;
  scene.add(sky);

  const envScene = new THREE.Scene();
  const envSky = new Sky();
  envSky.scale.setScalar(1000);
  envSky.material.uniforms = su;
  envScene.add(envSky);
  const pmrem = new THREE.PMREMGenerator(renderer);
  let envRT = null;

  const fogColor = new THREE.Color("#d8c6a8");
  scene.fog = new THREE.FogExp2(fogColor, 0.0011);

  const sun = new THREE.DirectionalLight("#fff1dc", 2.6);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  const sc = sun.shadow.camera;
  sc.left = -150;
  sc.right = 150;
  sc.top = 150;
  sc.bottom = -150;
  sc.near = 10;
  sc.far = 700;
  sun.shadow.bias = -0.0004;
  sun.shadow.normalBias = 0.6;
  scene.add(sun, sun.target);
  const hemi = new THREE.HemisphereLight("#cfe2ff", "#a07d55", 0.35);
  scene.add(hemi);

  const base = T3.materials();
  const mats = {
    wall: base.wall,
    concrete: base.concrete,
    solar: base.solar,
    alu: base.alu,
    blue: new THREE.MeshStandardMaterial({ color: "#1d5fa6", roughness: 0.45 }),
    tank: new THREE.MeshStandardMaterial({ color: "#ececec", roughness: 0.35 }),
  };
  const windowMat = new THREE.MeshStandardMaterial({
    color: "#1b2a33", roughness: 0.1, metalness: 0.4, emissive: "#ffb766", emissiveIntensity: 0,
  });
  const pondMat = new THREE.MeshPhysicalMaterial({
    color: "#2f7fa6", roughness: 0.06, metalness: 0.1, clearcoat: 1, clearcoatRoughness: 0.04,
  });

  scene.add(makeTerrain());
  makeOlives(scene);
  makeVillage(scene, windowMat, mats);
  makeSolarFarm(scene, mats);
  const pond = makeWater(scene, mats, pondMat);
  const flows = makeFlows(scene);
  const fronds = [];
  scene.traverse((o) => {
    if (o.userData.sway !== undefined) {
      fronds.push(o);
      o.userData.rx = o.rotation.x;
    }
  });

  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), 0.35, 0.4, 1.0);
  composer.addPass(bloom);
  composer.addPass(new OutputPass());

  const sunDir = new THREE.Vector3();
  const warm = new THREE.Color("#ffb070");
  const white = new THREE.Color("#fff4e6");
  const fogLow = new THREE.Color("#e0b892");
  const fogHigh = new THREE.Color("#d3e0e8");
  let lastEnv = -1;

  function setSun(t, force) {
    // Le soleil oscille entre l'heure dorée et le plein jour.
    const p = (t / 140) * Math.PI * 2;
    const elev = 4 + 26 * (0.5 - 0.5 * Math.cos(p));
    const az = 215 + 35 * Math.sin(p * 0.5);
    const phi = THREE.MathUtils.degToRad(90 - elev);
    const theta = THREE.MathUtils.degToRad(az);
    sunDir.setFromSphericalCoords(1, phi, theta);
    su.sunPosition.value.copy(sunDir);
    sun.position.copy(sunDir).multiplyScalar(350);
    const k = smooth(4, 26, elev);
    sun.color.copy(warm).lerp(white, k);
    sun.intensity = 1.5 + 1.6 * k;
    hemi.intensity = 0.25 + 0.2 * k;
    renderer.toneMappingExposure = 0.62 + 0.1 * (1 - k);
    fogColor.copy(fogLow).lerp(fogHigh, k);
    scene.fog.color.copy(fogColor);
    windowMat.emissiveIntensity = 2.2 * (1 - smooth(4, 12, elev));
    // L'éclairage d'ambiance suit le ciel, recalculé de temps en temps.
    const step = Math.round(t / 2.5);
    if (force || step !== lastEnv) {
      lastEnv = step;
      if (envRT) {
        envRT.dispose();
      }
      envRT = pmrem.fromScene(envScene, 0, 1, 3000);
      scene.environment = envRT.texture;
      scene.environmentIntensity = 0.55;
    }
  }

  function resize() {
    const w = hero.clientWidth;
    const h = hero.clientHeight;
    renderer.setSize(w, h, false);
    composer.setSize(w, h);
    bloom.resolution.set(w / 2, h / 2);
    camera.aspect = w / h;
    // Sur un écran étroit on recule un peu.
    camera.fov = w / h < 1.1 ? 55 : 42;
    camera.updateProjectionMatrix();
  }

  const look = new THREE.Vector3();
  const mouse = { x: 0, y: 0, tx: 0, ty: 0 };
  hero.addEventListener("pointermove", (e) => {
    const r = hero.getBoundingClientRect();
    mouse.tx = (e.clientX - r.left) / r.width - 0.5;
    mouse.ty = (e.clientY - r.top) / r.height - 0.5;
  });

  function place(t) {
    // Survol lent en orbite autour du village, avec une légère houle.
    const a = 2.35 + t * 0.018;
    const rad = 104 + Math.sin(t * 0.05) * 14;
    mouse.x += (mouse.tx - mouse.x) * 0.03;
    mouse.y += (mouse.ty - mouse.y) * 0.03;
    camera.position.set(
      Math.cos(a) * rad + mouse.x * 6,
      27 + Math.sin(t * 0.07) * 4 - mouse.y * 4,
      Math.sin(a) * rad,
    );
    // Le regard vise un peu à droite du centre, pour laisser la place au texte.
    const side = new THREE.Vector3(-Math.sin(a), 0, Math.cos(a)).multiplyScalar(-16);
    look.set(side.x, 9, side.z);
    camera.lookAt(look);
    sun.target.position.set(0, 0, 0);
  }

  const tmp = new THREE.Vector3();
  const m4 = new THREE.Matrix4();
  function animateFlows(t) {
    for (const f of flows) {
      for (let i = 0; i < f.n; i += 1) {
        const u = (((i / f.n + t * 0.035 + f.offset) % 1) + 1) % 1;
        f.curve.getPointAt(u, tmp);
        const s = 0.6 + 0.4 * Math.sin(u * Math.PI);
        m4.makeScale(s, s, s).setPosition(tmp);
        f.pearls.setMatrixAt(i, m4);
      }
      f.pearls.instanceMatrix.needsUpdate = true;
    }
  }

  function frame(t) {
    place(t);
    setSun(t + 22, false);
    animateFlows(t);
    for (const fr of fronds) {
      fr.rotation.x = fr.userData.rx + Math.sin(t * 1.3 + fr.userData.sway) * 0.04;
    }
    pond.material.clearcoatRoughness = 0.04 + 0.02 * Math.sin(t);
    composer.render();
  }

  resize();
  setSun(22, true);
  frame(0);
  canvas.classList.add("is-ready");
  window.addEventListener("resize", () => {
    resize();
    if (still) {
      frame(0);
    }
  });
  if (still) {
    return;
  }

  let visible = true;
  let last = performance.now();
  let time = 0;
  new IntersectionObserver((entries) => {
    visible = entries[0].isIntersecting;
  }).observe(hero);
  function loop(now) {
    const dt = Math.max(0, Math.min(0.1, (now - last) / 1000));
    last = now;
    if (visible && !document.hidden) {
      time += dt * speed;
      frame(time);
    }
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);
}

if (canvas && hero && supportsWebGL()) {
  try {
    start();
  } catch (e) {
    console.warn("KIZUNA hero 3D indisponible :", e);
  }
}
