// Inscription : au lieu de la liste « Je suis », trois maquettes 3D
// réalistes à toucher (maison, ferme, entreprise). Un clic choisit le
// profil, puis le reste du formulaire apparaît. La vraie liste reste dans
// le formulaire (cachée), donc le serveur ne change pas. Sans WebGL, la
// liste classique reste affichée.
import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { RGBELoader } from "three/addons/loaders/RGBELoader.js";
import { GroundedSkybox } from "three/addons/objects/GroundedSkybox.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import * as T3 from "./twin3d.js?v=demo2";

const form = document.querySelector("form.auth-form");
const select = form && form.querySelector("select[name=role]");

// Panoramas HDR réels (Poly Haven, licence CC0) : la maison dans un
// paysage sec et ensoleillé, la ferme dans un champ au lever du soleil,
// l'entreprise sur une esplanade pavée. sunU = position du soleil.
const HDRI = {
  citizen: { file: "quarry_01_1k.hdr", sunU: 0.5996, height: 2.4, radius: 70, exposure: 0.85 },
  farmer: { file: "spruit_sunrise_1k.hdr", sunU: 0.5986, height: 2.4, radius: 70, exposure: 0.75 },
  business: { file: "venice_sunset_1k.hdr", sunU: 0.5996, height: 2.6, radius: 70, exposure: 0.95 },
};

const ROLES = {
  citizen: { title: "Citoyen", sub: "Je suis ma maison", color: "#4cc3ff" },
  farmer: { title: "Agriculteur", sub: "Je suis ma ferme", color: "#5fd38a" },
  business: { title: "Entreprise", sub: "Je suis mon activité", color: "#ffc94a" },
};

function webgl() {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch (e) {
    return false;
  }
}

/* ------------------------------------------------------------------ */
/* Matériaux en plus de ceux du jumeau                                 */
/* ------------------------------------------------------------------ */

const std = (o) => new THREE.MeshStandardMaterial(o);
let X = null;
function extra() {
  if (X) {
    return X;
  }
  X = {
    blue: std({ color: "#1d5fa6", roughness: 0.45 }),
    white: std({ color: "#f2f0ea", roughness: 0.4 }),
    terracotta: std({ color: "#b5562f", roughness: 0.75 }),
    barn: std({ color: "#9c3b2b", roughness: 0.8 }),
    sand: std({ color: "#d9c19a", roughness: 1 }),
    field: std({ color: "#7a5a3c", roughness: 1 }),
    crop: std({ color: "#7fae3f", roughness: 0.85 }),
    wheat: std({ color: "#d8b85a", roughness: 0.9 }),
    hay: std({ color: "#d6b467", roughness: 1 }),
    tractor: std({ color: "#2f8a3a", roughness: 0.4, metalness: 0.3 }),
    asphalt: std({ color: "#3a3d40", roughness: 0.95 }),
    line: std({ color: "#f4f4f0", roughness: 0.6 }),
    curtain: new THREE.MeshPhysicalMaterial({
      color: "#7fa9c4", roughness: 0.05, metalness: 0.6, clearcoat: 1, envMapIntensity: 1.4,
    }),
    sign: std({ color: "#0b5c5c", roughness: 0.4, emissive: "#0b5c5c", emissiveIntensity: 0.3 }),
    car2: new THREE.MeshPhysicalMaterial({ color: "#d9d9d6", metalness: 0.6, roughness: 0.3, clearcoat: 1 }),
    car3: new THREE.MeshPhysicalMaterial({ color: "#b8262b", metalness: 0.6, roughness: 0.3, clearcoat: 1 }),
  };
  return X;
}

/* ------------------------------------------------------------------ */
/* Maquettes                                                           */
/* ------------------------------------------------------------------ */

let SOFT = null;
function softAlpha() {
  if (SOFT) {
    return SOFT;
  }
  const c = document.createElement("canvas");
  c.width = 256;
  c.height = 256;
  const g = c.getContext("2d");
  const grad = g.createRadialGradient(128, 128, 60, 128, 128, 128);
  grad.addColorStop(0, "#fff");
  grad.addColorStop(1, "#000");
  g.fillStyle = grad;
  g.fillRect(0, 0, 256, 256);
  SOFT = new THREE.CanvasTexture(c);
  return SOFT;
}

// Sol local aux bords fondus, pour se mêler à la photo du panorama.
function base(g, mat, w = 12, d = 11, x0 = 0, z0 = 0, op = 1) {
  if (!mat) {
    return;
  }
  const m = mat.clone();
  m.alphaMap = softAlpha();
  m.transparent = true;
  m.opacity = op;
  m.depthWrite = false;
  if (m.map) {
    m.map = m.map.clone();
    m.map.repeat.set(w / 3, d / 3);
    m.map.needsUpdate = true;
  }
  const plane = new THREE.Mesh(new THREE.PlaneGeometry(w, d), m);
  plane.rotation.x = -Math.PI / 2;
  plane.position.set(x0, 0.01, z0);
  plane.receiveShadow = true;
  plane.renderOrder = -1;
  g.add(plane);
}

// Arbre réaliste : tronc ramifié et feuillage fait de dizaines de petites
// touffes irrégulières, avec des nuances de vert.
function realTree(x, z, seed, scale = 1, olive = false) {
  const rand = rng(seed);
  const g = new THREE.Group();
  const bark = std({ color: olive ? "#6b5a48" : "#5a4535", roughness: 1 });
  const h = (1.6 + rand() * 0.5) * scale;
  const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.07 * scale, 0.16 * scale, h, 9), bark);
  trunk.position.set(x, h / 2, z);
  trunk.rotation.z = (rand() - 0.5) * 0.15;
  trunk.castShadow = true;
  g.add(trunk);
  for (let i = 0; i < 3; i += 1) {
    const br = new THREE.Mesh(new THREE.CylinderGeometry(0.03 * scale, 0.06 * scale, 0.9 * scale, 6), bark);
    const a = rand() * Math.PI * 2;
    br.position.set(x + Math.cos(a) * 0.25 * scale, h * 0.85, z + Math.sin(a) * 0.25 * scale);
    br.rotation.set(Math.sin(a) * 0.7, 0, -Math.cos(a) * 0.7);
    br.castShadow = true;
    g.add(br);
  }
  const parts = [];
  const color = new THREE.Color();
  const n = 34;
  const R = (olive ? 1.05 : 0.95) * scale;
  for (let i = 0; i < n; i += 1) {
    const geo = new THREE.IcosahedronGeometry((0.26 + rand() * 0.22) * scale, 1);
    const p = geo.attributes.position;
    for (let k = 0; k < p.count; k += 1) {
      const f = 0.75 + rand() * 0.5;
      p.setXYZ(k, p.getX(k) * f, p.getY(k) * f, p.getZ(k) * f);
    }
    const u = rand() * Math.PI * 2;
    const v = Math.acos(2 * rand() - 1);
    const r = R * Math.cbrt(rand());
    geo.translate(
      x + Math.sin(v) * Math.cos(u) * r,
      h + 0.35 * scale + Math.cos(v) * r * 0.7,
      z + Math.sin(v) * Math.sin(u) * r,
    );
    if (olive) {
      color.setHSL(0.2 + rand() * 0.04, 0.2 + rand() * 0.1, 0.17 + rand() * 0.06);
    } else {
      color.setHSL(0.24 + rand() * 0.06, 0.5 + rand() * 0.15, 0.1 + rand() * 0.06);
    }
    const cols = new Float32Array(p.count * 3);
    for (let k = 0; k < p.count; k += 1) {
      const shade = 0.85 + rand() * 0.3;
      cols[k * 3] = color.r * shade;
      cols[k * 3 + 1] = color.g * shade;
      cols[k * 3 + 2] = color.b * shade;
    }
    geo.setAttribute("color", new THREE.BufferAttribute(cols, 3));
    geo.deleteAttribute("uv");
    parts.push(geo.toNonIndexed ? geo : geo);
  }
  const merged = mergeGeometries(parts.map((q) => (q.index ? q.toNonIndexed() : q)));
  // Normales orientées depuis le centre du houppier : feuillage doux,
  // sans facettes.
  const np = merged.attributes.position;
  const nn = new Float32Array(np.count * 3);
  const cy = h + 0.35 * scale;
  const tmp = new THREE.Vector3();
  for (let k = 0; k < np.count; k += 1) {
    tmp.set(np.getX(k) - x, (np.getY(k) - cy) * 1.3, np.getZ(k) - z).normalize();
    nn[k * 3] = tmp.x;
    nn[k * 3 + 1] = tmp.y;
    nn[k * 3 + 2] = tmp.z;
  }
  merged.setAttribute("normal", new THREE.BufferAttribute(nn, 3));
  const leaves = new THREE.Mesh(merged, std({ vertexColors: true, roughness: 0.85, flatShading: false }));
  leaves.castShadow = true;
  leaves.receiveShadow = true;
  g.add(leaves);
  return g;
}

function realBush(x, z, seed, s = 1) {
  const t = realTree(x, z, seed, 0.38 * s);
  t.children.slice(0, 4).forEach((c) => { c.visible = false; });
  t.position.y = -0.55 * s;
  return t;
}

function rng(seed) {
  let v = seed >>> 0 || 1;
  return () => {
    v = (Math.imul(v, 1664525) + 1013904223) >>> 0;
    return v / 4294967296;
  };
}

function windowAt(g, x, y, z, rotY, w = 0.9, h = 1.1) {
  const m = T3.materials();
  const x2 = extra();
  const win = new THREE.Group();
  win.add(T3.box(w + 0.12, h + 0.12, 0.06, x2.white, 0, -0.06, 0));
  win.add(T3.box(w, h, 0.08, m.glass, 0, 0, 0.01));
  win.add(T3.box(w * 0.5, h + 0.1, 0.05, x2.blue, -w * 0.78, -0.05, 0.04));
  win.add(T3.box(w * 0.5, h + 0.1, 0.05, x2.blue, w * 0.78, -0.05, 0.04));
  win.position.set(x, y, z);
  win.rotation.y = rotY;
  g.add(win);
}

function solarRow(g, n, x, y, z) {
  const m = T3.materials();
  for (let i = 0; i < n; i += 1) {
    const p = T3.box(0.85, 0.04, 1.35, m.solar, 0, 0, 0);
    p.position.set(x + i * 0.92, y + 0.45, z);
    p.rotation.x = -0.55;
    g.add(p);
    g.add(T3.box(0.05, 0.42, 0.05, m.alu, x + i * 0.92, y, z - 0.45));
  }
}

function house() {
  const m = T3.materials();
  const x = extra();
  const g = new THREE.Group();
  base(g, m.lawn, 13, 12, 0, 0, 0.9);
  // Terrasse et allée.
  g.add(T3.box(7.2, 0.05, 5.4, m.paving, -0.3, 0, -0.6, 0.6));
  g.add(T3.box(1.3, 0.05, 3, m.paving, -1.2, 0, 3.4, 0.6));
  // Maison blanche, deux volumes.
  g.add(T3.box(5, 3, 4, m.wall, -0.8, 0.05, -1.2, 0.5));
  g.add(T3.box(2.6, 2.4, 2.6, m.wall, 2.4, 0.05, -1.9, 0.5));
  // Acrotère.
  const par = (w, d, px, py, pz) => g.add(T3.box(w, 0.4, d, m.wall, px, py, pz, 0.5));
  par(5, 0.18, -0.8, 3.05, 0.71);
  par(5, 0.18, -0.8, 3.05, -3.11);
  par(0.18, 4, -3.21, 3.05, -1.2);
  par(0.18, 4, 1.61, 3.05, -1.2);
  // Porte bleue avec arc et marche.
  g.add(T3.box(1.05, 2.1, 0.1, x.blue, -1.2, 0.05, 0.82));
  const arch = new THREE.Mesh(new THREE.CylinderGeometry(0.53, 0.53, 0.1, 24, 1, false, 0, Math.PI), x.blue);
  arch.rotation.set(Math.PI / 2, 0, Math.PI / 2);
  arch.position.set(-1.2, 2.15, 0.82);
  g.add(arch);
  g.add(T3.box(1.5, 0.12, 0.5, m.paving, -1.2, 0.05, 1.05));
  windowAt(g, 0.6, 1.2, 0.84, 0);
  windowAt(g, -2.5, 1.2, 0.84, 0, 0.7);
  windowAt(g, 2.6, 1.0, -0.56, 0, 0.8, 1);
  windowAt(g, 1.64, 1.2, -1.7, Math.PI / 2, 0.8);
  windowAt(g, -3.24, 1.2, -1.2, -Math.PI / 2, 0.8);
  // Toit : panneaux solaires et citerne.
  solarRow(g, 4, -2.6, 3.05, -2.2);
  g.add(T3.cyl(0.45, 1, x.white, 0.9, 3.05, -0.1, 24));
  g.add(T3.cyl(0.12, 0.12, x.white, 0.9, 4.05, -0.1, 12));
  // Petite piscine.
  g.add(T3.box(2.6, 0.25, 1.7, x.white, 2.6, 0.02, 1.4));
  const pool = T3.box(2.3, 0.2, 1.4, m.water, 2.6, 0.1, 1.4);
  pool.castShadow = false;
  g.add(pool);
  // Jardin.
  g.add(realTree(-4.2, 2.2, 7, 1.3));
  g.add(realTree(4.2, -2.8, 9, 1.1));
  for (let i = 0; i < 5; i += 1) {
    g.add(realBush(-4.6 + i * 0.6, 4, i + 3));
  }
  // Muret blanc.
  g.add(T3.box(0.15, 0.6, 3.5, x.white, -5, 0, 1.6));
  return g;
}

function farm() {
  const m = T3.materials();
  const x = extra();
  const g = new THREE.Group();
  // Champ labouré avec cultures.
  base(g, x.field, 6.4, 4.4, 0.9, 2.2);
  for (let r = 0; r < 6; r += 1) {
    g.add(T3.box(5.0, 0.1, 0.28, x.field, 0.9, 0, 0.95 + r * 0.5));
  }
  const cropGeo = new THREE.IcosahedronGeometry(0.17, 1);
  const cp = cropGeo.attributes.position;
  for (let k = 0; k < cp.count; k += 1) {
    const f = 0.8 + Math.abs(Math.sin(k * 12.9898) * 0.45);
    cp.setXYZ(k, cp.getX(k) * f, cp.getY(k) * f * 0.8, cp.getZ(k) * f);
  }
  cropGeo.computeVertexNormals();
  const crops = new THREE.InstancedMesh(cropGeo, std({ color: "#ffffff", roughness: 0.8 }), 6 * 13);
  crops.castShadow = true;
  const cm = new THREE.Matrix4();
  const cc = new THREE.Color();
  const crand = rng(77);
  let ci = 0;
  for (let r = 0; r < 6; r += 1) {
    for (let c = 0; c < 13; c += 1) {
      const k = 0.8 + crand() * 0.45;
      cm.makeScale(k, k, k).setPosition(-1.45 + c * 0.39 + (crand() - 0.5) * 0.06, 0.2, 0.95 + r * 0.5);
      crops.setMatrixAt(ci, cm);
      cc.setHSL(0.24 + crand() * 0.05, 0.5 + crand() * 0.15, 0.16 + crand() * 0.06);
      crops.setColorAt(ci, cc);
      ci += 1;
    }
  }
  g.add(crops);
  // Oliviers en rangs.
  for (let i = 0; i < 3; i += 1) {
    for (let j = 0; j < 2; j += 1) {
      g.add(realTree(-4.4 + j * 1.5, -2.6 + i * 1.7, 30 + i * 2 + j, 0.6, true));
    }
  }
  // Grange au toit à deux pentes.
  g.add(T3.box(3, 2, 2.4, x.barn, 1.2, 0.03, -2.2));
  const tri = new THREE.Shape();
  tri.moveTo(-1.4, 0);
  tri.lineTo(1.4, 0);
  tri.lineTo(0, 1.05);
  tri.closePath();
  const roofGeo = new THREE.ExtrudeGeometry(tri, { depth: 3.3, bevelEnabled: false });
  roofGeo.translate(0, 0, -1.65);
  const gable = new THREE.Mesh(roofGeo, x.barn);
  gable.rotation.y = Math.PI / 2;
  gable.position.set(1.2, 2.03, -2.2);
  gable.castShadow = true;
  g.add(gable);
  const slope = Math.atan2(1.05, 1.4);
  const len = Math.hypot(1.05, 1.4) + 0.12;
  for (const side of [1, -1]) {
    const r = T3.box(3.5, 0.08, len, x.terracotta, 0, 0, 0);
    r.geometry.translate(0, -0.04, 0);
    r.position.set(1.2, 2.03 + 0.55, -2.2 + side * 0.7);
    r.rotation.x = side * slope;
    g.add(r);
  }
  g.add(T3.box(1.2, 1.5, 0.08, x.white, 1.2, 0.03, -0.96));
  // Petite maison de ferme.
  g.add(T3.box(2, 2.2, 1.8, m.wall, -1.8, 0.03, -2.6, 0.5));
  g.add(T3.box(0.7, 1.6, 0.08, x.blue, -1.8, 0.03, -1.67));
  solarRow(g, 2, -2.5, 2.23, -3.0);
  // Citerne d'irrigation.
  g.add(T3.cyl(0.8, 1.8, m.tankShell, 4.0, 0.03, -0.6, 32));
  g.add(T3.cyl(0.74, 1.2, m.tankWater, 4.0, 0.06, -0.6, 32));
  // Tracteur.
  const t = new THREE.Group();
  t.add(T3.rbox(1.3, 0.6, 0.7, 0.08, x.tractor, 0, 0.45, 0));
  t.add(T3.rbox(0.6, 0.7, 0.68, 0.05, m.carGlass, -0.3, 1.0, 0));
  t.add(T3.box(0.64, 0.06, 0.74, x.tractor, -0.3, 1.7, 0));
  const wheel = (r, w, px, pz) => {
    const wh = T3.cyl(r, w, m.tyre, 0, -w / 2, 0, 20);
    wh.rotation.x = Math.PI / 2;
    wh.position.set(px, r, pz);
    t.add(wh);
  };
  wheel(0.45, 0.25, -0.4, 0.42);
  wheel(0.45, 0.25, -0.4, -0.42);
  wheel(0.28, 0.18, 0.5, 0.38);
  wheel(0.28, 0.18, 0.5, -0.38);
  t.position.set(3.6, 0.03, 2.4);
  t.rotation.y = -0.6;
  g.add(t);
  // Bottes de foin.
  for (let i = 0; i < 3; i += 1) {
    const b = T3.cyl(0.35, 0.7, x.hay, 0, -0.35, 0, 18);
    b.rotation.z = Math.PI / 2;
    b.position.set(-4.3 + i * 0.8, 0.38, 3.0);
    g.add(b);
  }
  return g;
}

function office() {
  const m = T3.materials();
  const x = extra();
  const g = new THREE.Group();
  base(g, m.paving, 14, 13);
  // Parking.
  g.add(T3.box(4.2, 0.04, 4.6, x.asphalt, 2.6, 0, 1.2));
  for (let i = 0; i < 4; i += 1) {
    g.add(T3.box(0.06, 0.01, 1.6, x.line, 1.0 + i * 1.1, 0.04, 2.3));
  }
  // Tour vitrée.
  const W = 4.2;
  const D = 3.4;
  const floors = 4;
  const fh = 1.15;
  g.add(T3.box(W - 0.2, floors * fh, D - 0.2, x.curtain, -1.6, 0.03, -1.4));
  for (let f = 0; f <= floors; f += 1) {
    g.add(T3.box(W, 0.14, D, m.concrete, -1.6, 0.03 + f * fh - (f ? 0.07 : 0), -1.4, 0.5));
  }
  for (let i = 0; i <= 6; i += 1) {
    const px = -1.6 - W / 2 + (W / 6) * i;
    g.add(T3.box(0.05, floors * fh, 0.05, m.frame, px, 0.03, -1.4 + D / 2 - 0.08));
  }
  for (let i = 0; i <= 5; i += 1) {
    const pz = -1.4 - D / 2 + (D / 5) * i;
    g.add(T3.box(0.05, floors * fh, 0.05, m.frame, -1.6 + W / 2 - 0.08, 0.03, pz));
  }
  // Cage d'escalier en béton.
  g.add(T3.box(1.2, floors * fh + 0.6, 1.2, m.concrete, -3.2, 0.03, -2.6, 0.5));
  // Auvent d'entrée et enseigne.
  g.add(T3.box(1.8, 0.1, 1.1, m.steel, -1.2, 1.6, 0.75));
  g.add(T3.box(0.06, 1.6, 0.06, m.steel, -2.0, 0.03, 1.2));
  g.add(T3.box(0.06, 1.6, 0.06, m.steel, -0.4, 0.03, 1.2));
  g.add(T3.box(1.6, 0.35, 0.06, x.sign, -1.6, floors * fh - 0.4, 0.33));
  // Toit solaire.
  solarRow(g, 4, -3.0, floors * fh + 0.1, -1.6);
  // Voitures.
  const car = (mat, px, pz) => {
    const c = new THREE.Group();
    c.add(T3.rbox(0.8, 0.38, 1.7, 0.12, mat, 0, 0.14, 0));
    c.add(T3.rbox(0.7, 0.32, 0.9, 0.12, m.carGlass, 0, 0.48, -0.05));
    for (const [wx, wz] of [[-0.38, 0.55], [0.38, 0.55], [-0.38, -0.55], [0.38, -0.55]]) {
      const w = T3.cyl(0.16, 0.12, m.tyre, 0, -0.06, 0, 14);
      w.rotation.z = Math.PI / 2;
      w.position.set(wx, 0.16, wz);
      c.add(w);
    }
    c.position.set(px, 0.04, pz);
    g.add(c);
  };
  car(m.carPaint, 1.55, 2.3);
  car(x.car2, 2.65, 2.3);
  car(x.car3, 4.85, 2.3);
  // Borne de recharge.
  g.add(T3.rbox(0.3, 0.9, 0.2, 0.04, m.batteryBody, 3.75, 0.04, 3.4));
  // Arbres.
  g.add(realTree(-4.4, 2.6, 51, 0.9));
  g.add(realTree(-2.4, 3.6, 52, 0.8));
  g.add(realTree(4.6, -2.6, 53, 1));
  return g;
}

const BUILD = { citizen: house, farmer: farm, business: office };

/* ------------------------------------------------------------------ */
/* Vue d'une carte                                                     */
/* ------------------------------------------------------------------ */

class RoleView {
  constructor(canvas, role, still) {
    this.canvas = canvas;
    this.role = role;
    this.still = still;
    this.hover = 0;
    this.hoverTarget = 0;
    this.selected = false;
    const r = new THREE.WebGLRenderer({ canvas, antialias: true });
    r.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    r.outputColorSpace = THREE.SRGBColorSpace;
    r.toneMapping = THREE.ACESFilmicToneMapping;
    r.toneMappingExposure = 1.0;
    r.shadowMap.enabled = true;
    r.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer = r;
    const scene = new THREE.Scene();
    const pm = new THREE.PMREMGenerator(r);
    // Lumière d'attente (studio) avant que le panorama ne soit chargé.
    scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environmentIntensity = 0.6;
    scene.background = new THREE.Color("#dfe9ec");
    const hd = HDRI[role];
    // Soleil placé là où il est dans la photo, un peu plus haut pour des
    // ombres lisibles.
    const phi = (hd.sunU - 0.5) * Math.PI * 2;
    const sunDir = new THREE.Vector3(Math.cos(phi), 0.62, Math.sin(phi)).normalize();
    const sun = new THREE.DirectionalLight("#ffe2c0", 2.6);
    sun.position.copy(sunDir).multiplyScalar(30);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    Object.assign(sun.shadow.camera, { left: -11, right: 11, top: 11, bottom: -11, near: 1, far: 80 });
    sun.shadow.bias = -0.0004;
    sun.shadow.normalBias = 0.03;
    sun.shadow.radius = 3;
    scene.add(sun);
    this.scene = scene;
    this.model = BUILD[role]();
    this.pivot = new THREE.Group();
    this.pivot.add(this.model);
    scene.add(this.pivot);
    // Ombres portées sur le sol de la photo.
    const shadow = new THREE.Mesh(
      new THREE.PlaneGeometry(60, 60),
      new THREE.ShadowMaterial({ opacity: 0.42 }),
    );
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.y = 0.005;
    shadow.receiveShadow = true;
    scene.add(shadow);
    this.camera = new THREE.PerspectiveCamera(34, 1, 0.3, 1000);
    // La caméra part du côté du soleil (modèle bien éclairé) et tourne
    // lentement autour : le paysage photo défile derrière.
    this.angle = phi + { citizen: 0.55, farmer: 0.4, business: 0.75 }[role];
    this.dist = 16.5;
    this.zoom = 0;
    this.place();
    this.resize();
    new RGBELoader().setDataType(THREE.FloatType).load(new URL(`../hdri/${hd.file}`, import.meta.url).href, (tex) => {
      // Le disque solaire de la photo est des milliers de fois plus fort que
      // le reste : on le plafonne, la lumière directe vient déjà du soleil.
      const data = tex.image.data;
      for (let i = 0; i < data.length; i += 1) {
        if (data[i] > 12) {
          data[i] = 12;
        }
      }
      tex.needsUpdate = true;
      tex.mapping = THREE.EquirectangularReflectionMapping;
      const env = pm.fromEquirectangular(tex).texture;
      scene.environment = env;
      scene.environmentIntensity = 1;
      scene.background = null;
      const sky = new GroundedSkybox(tex, hd.height, hd.radius);
      sky.position.y = hd.height - 0.01;
      scene.add(sky);
      r.toneMappingExposure = hd.exposure;
      this.dirty = true;
    });
  }

  place() {
    const d = this.dist - this.zoom * 3;
    this.camera.position.set(Math.cos(this.angle) * d, 5.4 + this.zoom * 0.3, Math.sin(this.angle) * d);
    this.camera.lookAt(0, 1.9, 0);
  }

  resize() {
    const w = this.canvas.clientWidth;
    const h = this.canvas.clientHeight;
    if (!w || !h) {
      return;
    }
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  frame(dt) {
    this.hover += (this.hoverTarget - this.hover) * Math.min(1, dt * 6);
    if (!this.still) {
      this.angle += dt * (0.07 + this.hover * 0.25 + (this.selected ? 0.08 : 0));
    }
    const z = Math.max(this.hover, this.selected ? 0.6 : 0);
    this.zoom += (z - this.zoom) * Math.min(1, dt * 5);
    this.place();
    this.renderer.render(this.scene, this.camera);
  }
}

/* ------------------------------------------------------------------ */
/* Mise en page                                                        */
/* ------------------------------------------------------------------ */

const CSS = `
.rp-step { margin: 0 0 .35rem; font-size: .85rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--kz-sea, #0b5c5c); }
.rp-head { margin: 0 0 1rem; font-size: 1.35rem; font-weight: 750; }
.rp { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; max-width: 62rem; margin-bottom: 2rem; }
.rp-card {
  position: relative; display: flex; flex-direction: column; align-items: center;
  padding: 0 0 1rem; text-align: center; cursor: pointer;
  background: linear-gradient(180deg, #eef6f8 0%, #ffffff 70%);
  border: 2px solid var(--kz-line, #dde5e4); border-radius: 18px; overflow: hidden;
  box-shadow: 0 6px 18px rgba(10, 60, 60, .07);
  transition: transform .25s ease, box-shadow .25s ease, border-color .25s ease;
}
.rp-card:hover, .rp-card:focus-visible { transform: translateY(-4px); box-shadow: 0 16px 34px rgba(10, 60, 60, .16); outline: none; }
.rp-card:focus-visible { border-color: #0b5c5c; }
.rp-card canvas { display: block; width: 100%; aspect-ratio: 1 / 0.9; margin-bottom: .8rem; }
.rp-text { display: flex; flex-direction: column; }
.rp-title { font-size: 1.2rem; font-weight: 750; color: #10302f; }
.rp-sub { font-size: .95rem; color: var(--kz-muted, #5b6b6a); }
.rp-check {
  position: absolute; top: .75rem; right: .75rem; display: grid; place-items: center;
  width: 2rem; height: 2rem; border-radius: 50%; color: #fff; font-weight: 800;
  background: var(--rp-c); transform: scale(0); transition: transform .25s cubic-bezier(.3,1.6,.5,1);
}
.rp-card[aria-checked="true"] { border-color: var(--rp-c); box-shadow: 0 0 0 4px color-mix(in srgb, var(--rp-c) 30%, transparent), 0 16px 34px rgba(10,60,60,.16); }
.rp-card[aria-checked="true"] .rp-check { transform: scale(1); }
.rp-chosen { display: flex; align-items: center; gap: .6rem; margin-bottom: 1.25rem; padding: .7rem 1rem; border-radius: 12px; background: #eef6f4; font-weight: 600; }
.rp-chosen button { margin-left: auto; border: 0; background: none; color: #0b5c5c; font-weight: 700; text-decoration: underline; cursor: pointer; }
.rp-form-hidden { display: none !important; }
.rp-reveal { animation: rp-in .5s ease both; }
@keyframes rp-in { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: none; } }
@media (max-width: 720px) {
  .rp { grid-template-columns: 1fr; }
  .rp-card { flex-direction: row; padding: 0 1rem 0 0; text-align: left; }
  .rp-card canvas { width: 9.5rem; flex: none; }
  .rp-card .rp-text { display: flex; flex-direction: column; }
}
`;

function setup() {
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const style = document.createElement("style");
  style.textContent = CSS;
  document.head.appendChild(style);

  const field = select.closest(".mb-3") || select.parentElement;
  const hasErrors = !!form.querySelector(".invalid-feedback, .alert-danger");

  const wrap = document.createElement("section");
  wrap.className = "rp-wrap";
  wrap.innerHTML = `
    <p class="rp-step">Étape 1 sur 2</p>
    <h2 class="rp-head">Qui êtes-vous ? Touchez votre modèle.</h2>
    <div class="rp" role="radiogroup" aria-label="Je suis"></div>`;
  const group = wrap.querySelector(".rp");
  const cards = {};
  const views = [];
  for (const [value, info] of Object.entries(ROLES)) {
    if (![...select.options].some((o) => o.value === value)) {
      continue;
    }
    const b = document.createElement("button");
    b.type = "button";
    b.className = "rp-card";
    b.setAttribute("role", "radio");
    b.setAttribute("aria-checked", "false");
    b.dataset.role = value;
    b.style.setProperty("--rp-c", info.color);
    b.innerHTML = `<canvas aria-hidden="true"></canvas><span class="rp-text"><span class="rp-title">${info.title}</span><span class="rp-sub">${info.sub}</span></span><span class="rp-check" aria-hidden="true">✓</span>`;
    group.appendChild(b);
    cards[value] = b;
  }
  form.before(wrap);

  // Bandeau « profil choisi » en haut du formulaire.
  const chosen = document.createElement("div");
  chosen.className = "rp-chosen";
  chosen.innerHTML = `<span class="rp-step" style="margin:0">Étape 2 sur 2</span><span class="rp-chosen-text"></span><button type="button">Changer</button>`;
  form.prepend(chosen);
  chosen.querySelector("button").addEventListener("click", () => {
    wrap.scrollIntoView({ behavior: still ? "auto" : "smooth", block: "start" });
  });

  field.hidden = true;
  field.classList.add("rp-form-hidden");

  let revealed = hasErrors;
  if (!revealed) {
    form.classList.add("rp-form-hidden");
  }

  for (const [value, b] of Object.entries(cards)) {
    const view = new RoleView(b.querySelector("canvas"), value, still);
    views.push(view);
    b._view = view;
    b.addEventListener("pointerenter", () => { view.hoverTarget = 1; });
    b.addEventListener("pointerleave", () => { view.hoverTarget = 0; });
    b.addEventListener("focus", () => { view.hoverTarget = 1; });
    b.addEventListener("blur", () => { view.hoverTarget = 0; });
    b.addEventListener("click", () => choose(value, true));
  }

  function choose(value, fromUser) {
    select.value = value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
    for (const [v, b] of Object.entries(cards)) {
      const on = v === value;
      b.setAttribute("aria-checked", on ? "true" : "false");
      b._view.selected = on;
    }
    const info = ROLES[value];
    chosen.querySelector(".rp-chosen-text").textContent = `Profil : ${info.title} · ${info.sub.toLowerCase()}`;
    if (fromUser) {
      if (!revealed) {
        revealed = true;
        form.classList.remove("rp-form-hidden");
        form.classList.add("rp-reveal");
      }
      setTimeout(() => {
        form.scrollIntoView({ behavior: still ? "auto" : "smooth", block: "start" });
        const first = form.querySelector("input:not([type=hidden])");
        if (first) {
          first.focus({ preventScroll: true });
        }
      }, 250);
    }
  }

  // Après une erreur, on garde le choix déjà fait.
  if (hasErrors && select.value) {
    choose(select.value, false);
  }
  // Après une erreur, on montre tout de suite ce qu'il faut corriger.
  if (hasErrors) {
    const summary = document.getElementById("kz-erreurs");
    const target = summary || form.querySelector(".invalid-feedback, .alert-danger");
    if (target) {
      setTimeout(() => {
        target.scrollIntoView({ behavior: "auto", block: "center" });
        if (summary) {
          summary.focus({ preventScroll: true });
        }
      }, 50);
    }
  }

  // Flèches du clavier dans le groupe, comme une vraie liste de choix.
  group.addEventListener("keydown", (e) => {
    const list = Object.values(cards);
    const i = list.indexOf(document.activeElement);
    if (i < 0) {
      return;
    }
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (step) {
      e.preventDefault();
      list[(i + step + list.length) % list.length].focus();
    }
  });

  window.addEventListener("resize", () => views.forEach((v) => v.resize()));
  let visible = true;
  new IntersectionObserver((en) => { visible = en[0].isIntersecting; }).observe(group);
  let last = performance.now();
  function loop(now) {
    const dt = Math.max(0, Math.min(0.1, (now - last) / 1000));
    last = now;
    if (visible && !document.hidden) {
      views.forEach((v) => v.frame(dt));
    }
    requestAnimationFrame(loop);
  }
  views.forEach((v) => v.frame(0));
  requestAnimationFrame(loop);
}

if (form && select && webgl()) {
  try {
    setup();
  } catch (e) {
    console.warn("KIZUNA choix 3D indisponible :", e);
    form.classList.remove("rp-form-hidden");
    const field = select.closest(".mb-3");
    if (field) {
      field.hidden = false;
      field.classList.remove("rp-form-hidden");
    }
  }
}
