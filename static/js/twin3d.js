/**
 * Realistic 3D view of one KIZUNA home.
 *
 * The house is built from the same records as the 2D plan: each stored room
 * becomes a floor, walls, windows, doors and furniture. Tank, battery, solar,
 * pump, valve, flows and rain follow /api/twin/homes/<id>/.
 *
 * Rendering: PBR materials with procedural textures, image-based lighting,
 * a sun that follows the shared clock, soft shadows, ACES tone mapping,
 * ambient occlusion (GTAO), light bloom and MSAA.
 * Everything is generated in code. No external model or texture files.
 */

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { CSS2DRenderer, CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { GTAOPass } from "three/addons/postprocessing/GTAOPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { COLS, layout } from "./twin-layout.js";

// World units are metres.
const CW = 4; // cell width (x)
const CD = 3.4; // cell depth (z)
const H = 2.7; // wall height
const T = 0.18; // wall thickness
const FLOOR = 0.12; // floor slab height
const ROOM_FR = {
  living_room: "Salon",
  kitchen: "Cuisine",
  bedroom: "Chambre",
  bathroom: "Salle de bain",
  garage: "Garage",
  garden: "Jardin",
  pool: "Piscine",
  other: "Pièce",
};
const ROOM_EN = new Set(["living room", "kitchen", "bedroom", "bathroom", "garage", "garden", "pool", "other", "room"]);
const BATTERY_FR = { charging: "en charge", discharging: "en décharge", idle: "au repos", on: "active", off: "arrêtée" };

// Default English names ("Bedroom 2") become French; names the owner typed stay as they are.
function roomName(room) {
  const name = String(room.name || "");
  const match = name.match(/^(.*?)(\s+\d+)?$/);
  if (match && ROOM_EN.has(match[1].trim().toLowerCase()) && ROOM_FR[room.kind]) {
    return ROOM_FR[room.kind] + (match[2] || "");
  }
  return name;
}

const INDOOR = new Set(["living_room", "kitchen", "bedroom", "bathroom", "garage", "other"]);

/* ------------------------------------------------------------------ */
/* Procedural textures                                                 */
/* ------------------------------------------------------------------ */

function rng(seed) {
  let s = seed >>> 0 || 1;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

function canvasTexture(size, draw, color = true) {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  draw(canvas.getContext("2d"), size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.anisotropy = 8;
  if (color) {
    texture.colorSpace = THREE.SRGBColorSpace;
  }
  return texture;
}

function speckle(g, size, count, rand, light, dark, max = 3) {
  for (let i = 0; i < count; i += 1) {
    g.fillStyle = rand() > 0.5 ? light : dark;
    const s = 1 + rand() * max;
    g.fillRect(rand() * size, rand() * size, s, s);
  }
}

const TEX = {};

function textures() {
  if (TEX.ready) {
    return TEX;
  }
  TEX.plaster = canvasTexture(512, (g, s) => {
    const rand = rng(11);
    g.fillStyle = "#ece6dc";
    g.fillRect(0, 0, s, s);
    speckle(g, s, 14000, rand, "rgba(255,255,255,0.10)", "rgba(80,60,40,0.06)");
  });
  TEX.plasterBump = canvasTexture(256, (g, s) => {
    const rand = rng(12);
    g.fillStyle = "#808080";
    g.fillRect(0, 0, s, s);
    speckle(g, s, 9000, rand, "rgba(255,255,255,0.25)", "rgba(0,0,0,0.25)", 2);
  }, false);
  TEX.wood = canvasTexture(1024, (g, s) => {
    const rand = rng(21);
    const rows = 8;
    const rh = s / rows;
    for (let r = 0; r < rows; r += 1) {
      let x = -rand() * s * 0.5;
      while (x < s) {
        const len = s * (0.45 + rand() * 0.4);
        const l = 38 + rand() * 12;
        g.fillStyle = `hsl(${26 + rand() * 6}, ${38 + rand() * 12}%, ${l}%)`;
        g.fillRect(x, r * rh, len, rh);
        for (let k = 0; k < 18; k += 1) {
          g.strokeStyle = `rgba(60,35,15,${0.05 + rand() * 0.12})`;
          g.lineWidth = 0.6 + rand() * 1.4;
          g.beginPath();
          const y = r * rh + rand() * rh;
          g.moveTo(x, y);
          g.bezierCurveTo(x + len * 0.3, y + (rand() - 0.5) * 8, x + len * 0.6, y + (rand() - 0.5) * 8, x + len, y);
          g.stroke();
        }
        g.fillStyle = "rgba(40,22,10,0.55)";
        g.fillRect(x, r * rh, 2, rh);
        x += len;
      }
      g.fillStyle = "rgba(40,22,10,0.6)";
      g.fillRect(0, r * rh, s, 2);
    }
  });
  const tile = (seed, base, grout, n) => canvasTexture(512, (g, s) => {
    const rand = rng(seed);
    const step = s / n;
    g.fillStyle = grout;
    g.fillRect(0, 0, s, s);
    for (let i = 0; i < n; i += 1) {
      for (let j = 0; j < n; j += 1) {
        const c = new THREE.Color(base).offsetHSL(0, 0, (rand() - 0.5) * 0.04);
        g.fillStyle = `#${c.getHexString()}`;
        g.fillRect(i * step + 3, j * step + 3, step - 6, step - 6);
      }
    }
    speckle(g, s, 3000, rand, "rgba(255,255,255,0.08)", "rgba(0,0,0,0.04)", 2);
  });
  TEX.tile = tile(31, "#e9e6e0", "#b9b3a8", 4);
  TEX.kitchenTile = tile(32, "#cfc4b4", "#8f8678", 6);
  TEX.poolTile = tile(33, "#3f9ac2", "#d9eef5", 10);
  TEX.concrete = canvasTexture(512, (g, s) => {
    const rand = rng(41);
    g.fillStyle = "#a3a29c";
    g.fillRect(0, 0, s, s);
    speckle(g, s, 20000, rand, "rgba(255,255,255,0.07)", "rgba(0,0,0,0.08)", 4);
  });
  TEX.paving = canvasTexture(512, (g, s) => {
    const rand = rng(51);
    g.fillStyle = "#8d877c";
    g.fillRect(0, 0, s, s);
    const n = 4;
    const step = s / n;
    for (let i = 0; i < n; i += 1) {
      for (let j = 0; j < n; j += 1) {
        const off = j % 2 ? step / 2 : 0;
        const c = new THREE.Color("#cfc6b5").offsetHSL(0, 0, (rand() - 0.5) * 0.08);
        g.fillStyle = `#${c.getHexString()}`;
        g.fillRect(((i * step + off) % s) + 3, j * step + 3, step - 6, step - 6);
        if (off) {
          g.fillRect(off - step + 3, j * step + 3, step - 6, step - 6);
        }
      }
    }
    speckle(g, s, 8000, rand, "rgba(255,255,255,0.07)", "rgba(0,0,0,0.07)", 3);
  });
  TEX.grass = canvasTexture(1024, (g, s) => {
    const rand = rng(61);
    g.fillStyle = "#58783a";
    g.fillRect(0, 0, s, s);
    for (let i = 0; i < 60000; i += 1) {
      const c = new THREE.Color().setHSL(0.22 + rand() * 0.06, 0.4 + rand() * 0.2, 0.22 + rand() * 0.18);
      g.strokeStyle = `#${c.getHexString()}`;
      g.lineWidth = 1 + rand();
      const x = rand() * s;
      const y = rand() * s;
      g.beginPath();
      g.moveTo(x, y);
      g.lineTo(x + (rand() - 0.5) * 4, y - 3 - rand() * 6);
      g.stroke();
    }
  });
  TEX.solar = canvasTexture(512, (g, s) => {
    g.fillStyle = "#0b1a33";
    g.fillRect(0, 0, s, s);
    const cols = 6;
    const rows = 10;
    g.strokeStyle = "#5b6f8e";
    g.lineWidth = 3;
    for (let i = 0; i <= cols; i += 1) {
      g.beginPath();
      g.moveTo((i * s) / cols, 0);
      g.lineTo((i * s) / cols, s);
      g.stroke();
    }
    for (let j = 0; j <= rows; j += 1) {
      g.beginPath();
      g.moveTo(0, (j * s) / rows);
      g.lineTo(s, (j * s) / rows);
      g.stroke();
    }
    g.strokeStyle = "rgba(120,140,170,0.25)";
    g.lineWidth = 1;
    for (let i = 0; i < cols * 3; i += 1) {
      g.beginPath();
      g.moveTo(((i + 0.5) * s) / (cols * 3), 0);
      g.lineTo(((i + 0.5) * s) / (cols * 3), s);
      g.stroke();
    }
  });
  TEX.ready = true;
  return TEX;
}

/* ------------------------------------------------------------------ */
/* Materials                                                           */
/* ------------------------------------------------------------------ */

const MAT = {};

function materials() {
  if (MAT.ready) {
    return MAT;
  }
  const t = textures();
  const std = (opts) => new THREE.MeshStandardMaterial(opts);
  MAT.wall = std({ map: t.plaster, bumpMap: t.plasterBump, bumpScale: 0.6, roughness: 0.92 });
  MAT.wood = std({ map: t.wood, roughness: 0.5, metalness: 0 });
  MAT.tile = std({ map: t.tile, roughness: 0.22 });
  MAT.kitchenTile = std({ map: t.kitchenTile, roughness: 0.3 });
  MAT.concrete = std({ map: t.concrete, bumpMap: t.plasterBump, bumpScale: 0.4, roughness: 0.88 });
  MAT.paving = std({ map: t.paving, roughness: 0.8 });
  MAT.grass = std({ map: t.grass, roughness: 0.95 });
  MAT.lawn = std({ map: t.grass, roughness: 0.95, color: "#cfe6a8" });
  MAT.poolTile = std({ map: t.poolTile, roughness: 0.2 });
  MAT.water = new THREE.MeshPhysicalMaterial({
    color: "#2f8fbf", roughness: 0.04, metalness: 0, transparent: true, opacity: 0.78,
    clearcoat: 1, clearcoatRoughness: 0.05,
  });
  MAT.glass = new THREE.MeshPhysicalMaterial({
    color: "#cfe3ea", roughness: 0.03, metalness: 0, transparent: true, opacity: 0.22,
    clearcoat: 1, side: THREE.DoubleSide, depthWrite: false,
  });
  MAT.frame = std({ color: "#2b3034", metalness: 0.7, roughness: 0.35 });
  MAT.alu = std({ color: "#b9bfc4", metalness: 0.9, roughness: 0.3 });
  MAT.steel = std({ color: "#c9cdd1", metalness: 0.85, roughness: 0.25 });
  MAT.pipe = std({ color: "#8fa3ad", metalness: 0.85, roughness: 0.3 });
  MAT.pipeClosed = std({ color: "#b23a2e", metalness: 0.4, roughness: 0.4 });
  MAT.cable = std({ color: "#1d1f21", roughness: 0.6 });
  MAT.fabric = std({ color: "#5f7d7b", roughness: 1 });
  MAT.fabricLight = std({ color: "#d9d2c5", roughness: 1 });
  MAT.duvet = std({ color: "#9fb4a8", roughness: 1 });
  MAT.linen = std({ color: "#f3f0ea", roughness: 0.95 });
  MAT.rug = std({ color: "#c7b391", roughness: 1 });
  MAT.darkWood = std({ map: t.wood, color: "#8c6a4f", roughness: 0.45 });
  MAT.cabinet = std({ color: "#dcd6cb", roughness: 0.45 });
  MAT.counter = std({ color: "#ecebe7", roughness: 0.18, metalness: 0 });
  MAT.porcelain = new THREE.MeshPhysicalMaterial({ color: "#fbfbf9", roughness: 0.12, clearcoat: 1 });
  MAT.screen = new THREE.MeshPhysicalMaterial({ color: "#0d0f12", roughness: 0.08, clearcoat: 1 });
  MAT.carPaint = new THREE.MeshPhysicalMaterial({
    color: "#2f6fed", metalness: 0.6, roughness: 0.32, clearcoat: 1, clearcoatRoughness: 0.08,
  });
  MAT.carGlass = new THREE.MeshPhysicalMaterial({ color: "#101418", roughness: 0.05, metalness: 0.2, clearcoat: 1 });
  MAT.tyre = std({ color: "#1a1a1a", roughness: 0.9 });
  MAT.trunk = std({ color: "#5b4130", roughness: 0.95 });
  MAT.pot = std({ color: "#b4673f", roughness: 0.8 });
  MAT.soil = std({ color: "#4a3626", roughness: 1 });
  MAT.leaf = [
    std({ color: "#3f6b2f", roughness: 0.85 }),
    std({ color: "#4f7d35", roughness: 0.85 }),
    std({ color: "#2f5a2a", roughness: 0.85 }),
  ];
  MAT.solar = new THREE.MeshPhysicalMaterial({
    map: t.solar, roughness: 0.15, metalness: 0.3, clearcoat: 1, clearcoatRoughness: 0.03,
  });
  MAT.tankShell = new THREE.MeshPhysicalMaterial({
    color: "#e8f1f4", roughness: 0.25, metalness: 0, transparent: true, opacity: 0.35,
    clearcoat: 1, side: THREE.DoubleSide, depthWrite: false,
  });
  MAT.tankWater = new THREE.MeshPhysicalMaterial({
    color: "#2a86c4", roughness: 0.1, transparent: true, opacity: 0.85, clearcoat: 1,
  });
  MAT.batteryBody = std({ color: "#eceeef", roughness: 0.35, metalness: 0.1 });
  MAT.pumpBody = std({ color: "#1f6f8b", roughness: 0.4, metalness: 0.5 });
  MAT.ready = true;
  return MAT;
}

function emissive(color, intensity) {
  return new THREE.MeshStandardMaterial({
    color: "#111111", emissive: color, emissiveIntensity: intensity, roughness: 0.5,
  });
}

/* ------------------------------------------------------------------ */
/* Geometry helpers                                                    */
/* ------------------------------------------------------------------ */

// Box-projected UVs in world units, so textures keep their real size.
function boxUV(geo, scale) {
  const p = geo.attributes.position;
  const n = geo.attributes.normal;
  const uv = geo.attributes.uv;
  for (let i = 0; i < p.count; i += 1) {
    const nx = Math.abs(n.getX(i));
    const ny = Math.abs(n.getY(i));
    const nz = Math.abs(n.getZ(i));
    let u;
    let v;
    if (nx >= ny && nx >= nz) {
      u = p.getZ(i);
      v = p.getY(i);
    } else if (ny >= nx && ny >= nz) {
      u = p.getX(i);
      v = p.getZ(i);
    } else {
      u = p.getX(i);
      v = p.getY(i);
    }
    uv.setXY(i, u * scale, v * scale);
  }
  uv.needsUpdate = true;
  return geo;
}

function mesh(geo, mat, shadow = true) {
  const m = new THREE.Mesh(geo, mat);
  m.castShadow = shadow;
  m.receiveShadow = true;
  return m;
}

// Box whose bottom sits at y.
function box(w, h, d, mat, x = 0, y = 0, z = 0, uvScale = 0) {
  const geo = new THREE.BoxGeometry(w, h, d);
  geo.translate(x, y + h / 2, z);
  if (uvScale) {
    boxUV(geo, uvScale);
  }
  return mesh(geo, mat);
}

function rbox(w, h, d, r, mat, x = 0, y = 0, z = 0) {
  const geo = new RoundedBoxGeometry(w, h, d, 3, Math.min(r, w / 2, h / 2, d / 2));
  geo.translate(x, y + h / 2, z);
  return mesh(geo, mat);
}

function cyl(r, h, mat, x = 0, y = 0, z = 0, seg = 32) {
  const geo = new THREE.CylinderGeometry(r, r, h, seg);
  geo.translate(x, y + h / 2, z);
  return mesh(geo, mat);
}

function label(text, kind = "") {
  const div = document.createElement("div");
  div.className = `twin3d-label ${kind}`.trim();
  div.textContent = text;
  return new CSS2DObject(div);
}

function disposeTree(root) {
  root.traverse((node) => {
    if (node.geometry) {
      node.geometry.dispose();
    }
    if (node.material && node.material.userData && node.material.userData.own) {
      node.material.dispose();
    }
    if (node.isCSS2DObject && node.element) {
      node.element.remove();
    }
  });
}

/* ------------------------------------------------------------------ */
/* Walls with openings                                                 */
/* ------------------------------------------------------------------ */

const OPENINGS = {
  window: { w: 1.5, y0: 0.9, y1: 2.15 },
  smallWindow: { w: 0.8, y0: 1.45, y1: 2.15 },
  door: { w: 0.95, y0: 0, y1: 2.15 },
  entrance: { w: 1.05, y0: 0, y1: 2.2 },
  garage: { w: 2.7, y0: 0, y1: 2.3 },
};

function wallSegment(a, b, type, room, glassFor) {
  const m = materials();
  const group = new THREE.Group();
  const horizontal = Math.abs(a.z - b.z) < 1e-6;
  const L = horizontal ? Math.abs(b.x - a.x) : Math.abs(b.z - a.z);
  group.position.set((a.x + b.x) / 2, FLOOR, (a.z + b.z) / 2);
  if (!horizontal) {
    group.rotation.y = Math.PI / 2;
  }
  const o = type ? OPENINGS[type] : null;
  if (!o) {
    group.add(box(L, H, T, m.wall, 0, 0, 0, 0.5));
    return group;
  }
  const side = (L - o.w) / 2;
  group.add(box(side, H, T, m.wall, -L / 2 + side / 2, 0, 0, 0.5));
  group.add(box(side, H, T, m.wall, L / 2 - side / 2, 0, 0, 0.5));
  if (o.y0 > 0) {
    group.add(box(o.w, o.y0, T, m.wall, 0, 0, 0, 0.5));
  }
  group.add(box(o.w, H - o.y1, T, m.wall, 0, o.y1, 0, 0.5));

  if (type === "window" || type === "smallWindow") {
    const hgt = o.y1 - o.y0;
    const f = 0.05;
    const glass = mesh(new THREE.BoxGeometry(o.w - f * 2, hgt - f * 2, 0.02), glassFor(room), false);
    glass.position.set(0, o.y0 + hgt / 2, 0);
    group.add(glass);
    group.add(box(o.w, f, T + 0.02, m.frame, 0, o.y0, 0));
    group.add(box(o.w, f, T + 0.02, m.frame, 0, o.y1 - f, 0));
    group.add(box(f, hgt, T + 0.02, m.frame, -o.w / 2 + f / 2, o.y0, 0));
    group.add(box(f, hgt, T + 0.02, m.frame, o.w / 2 - f / 2, o.y0, 0));
    group.add(box(f * 0.6, hgt, T * 0.6, m.frame, 0, o.y0, 0));
    group.add(box(o.w + 0.1, 0.04, T + 0.12, m.counter, 0, o.y0 - 0.04, 0));
  } else if (type === "entrance") {
    group.add(box(o.w - 0.04, o.y1 - 0.01, 0.05, m.darkWood, 0, 0, 0));
    group.add(cyl(0.025, 0.14, m.steel, o.w / 2 - 0.15, 1.0, T / 2));
  } else if (type === "garage") {
    // Sectional door, half open so the car shows.
    for (let i = 0; i < 2; i += 1) {
      group.add(box(o.w - 0.04, 0.42, 0.06, m.alu, 0, o.y1 - 0.44 * (i + 1), 0));
    }
  }
  return group;
}

/* ------------------------------------------------------------------ */
/* Furniture                                                           */
/* ------------------------------------------------------------------ */

function plant(x, z, scale = 1) {
  const m = materials();
  const g = new THREE.Group();
  g.add(cyl(0.16 * scale, 0.35 * scale, m.pot, x, 0, z, 20));
  const leaves = new THREE.IcosahedronGeometry(0.32 * scale, 1);
  const top = mesh(leaves, m.leaf[1]);
  top.position.set(x, 0.62 * scale, z);
  top.scale.set(1, 1.25, 1);
  g.add(top);
  return g;
}

function furnish(room, ws, ds) {
  const m = materials();
  const g = new THREE.Group();
  const back = -ds / 2 + T / 2 + 0.05;
  switch (room.kind) {
    case "bedroom": {
      const bz = back + 1.05;
      g.add(rbox(1.75, 0.3, 2.1, 0.04, m.darkWood, 0, 0, bz));
      g.add(rbox(1.62, 0.24, 2.0, 0.08, m.linen, 0, 0.3, bz));
      g.add(rbox(1.66, 0.08, 1.35, 0.04, m.duvet, 0, 0.5, bz + 0.33));
      g.add(rbox(0.62, 0.13, 0.36, 0.06, m.linen, -0.38, 0.53, back + 0.3));
      g.add(rbox(0.62, 0.13, 0.36, 0.06, m.linen, 0.38, 0.53, back + 0.3));
      g.add(rbox(1.8, 0.95, 0.08, 0.03, m.fabricLight, 0, 0.1, back + 0.02));
      g.add(rbox(0.48, 0.5, 0.42, 0.02, m.darkWood, -1.25, 0, back + 0.25));
      g.add(rbox(0.48, 0.5, 0.42, 0.02, m.darkWood, 1.25, 0, back + 0.25));
      g.add(rbox(1.6, 0.01, 1.0, 0.005, m.rug, 0, 0, bz + 1.3));
      g.add(rbox(1.3, 2.1, 0.6, 0.02, m.cabinet, ws / 2 - 0.9, 0, back + 0.3));
      g.add(plant(-ws / 2 + 0.5, ds / 2 - 0.5));
      break;
    }
    case "living_room": {
      const sz = ds * 0.12;
      g.add(rbox(3.4, 0.012, 2.4, 0.005, m.rug, 0, 0, sz - 0.3));
      g.add(rbox(2.5, 0.42, 0.95, 0.08, m.fabric, 0, 0, sz + 0.75));
      g.add(rbox(2.5, 0.5, 0.25, 0.08, m.fabric, 0, 0.35, sz + 1.12));
      g.add(rbox(0.22, 0.6, 0.95, 0.08, m.fabric, -1.36, 0, sz + 0.75));
      g.add(rbox(0.22, 0.6, 0.95, 0.08, m.fabric, 1.36, 0, sz + 0.75));
      g.add(rbox(0.75, 0.14, 0.65, 0.06, m.fabricLight, -0.42, 0.42, sz + 0.68));
      g.add(rbox(0.75, 0.14, 0.65, 0.06, m.fabricLight, 0.42, 0.42, sz + 0.68));
      g.add(rbox(1.2, 0.05, 0.62, 0.02, m.darkWood, 0, 0.38, sz - 0.35));
      [[-0.55, -0.26], [0.55, -0.26], [-0.55, 0.26], [0.55, 0.26]].forEach(([dx, dz]) => {
        g.add(cyl(0.025, 0.38, m.steel, dx, 0, sz - 0.35 + dz, 12));
      });
      g.add(rbox(2.0, 0.45, 0.42, 0.02, m.darkWood, 0, 0, back + 0.22));
      g.add(rbox(1.5, 0.86, 0.05, 0.01, m.screen, 0, 0.75, back + 0.1));
      g.add(plant(ws / 2 - 0.6, back + 0.5, 1.4));
      g.add(plant(-ws / 2 + 0.6, back + 0.5, 1.1));
      g.add(rbox(0.85, 0.42, 0.85, 0.12, m.fabricLight, 2.2, 0, sz - 0.2));
      break;
    }
    case "kitchen": {
      const run = Math.min(ws - 1.6, 4.4);
      g.add(rbox(run, 0.86, 0.62, 0.01, m.cabinet, -0.4, 0, back + 0.31));
      g.add(box(run + 0.04, 0.04, 0.66, m.counter, -0.4, 0.86, back + 0.33));
      g.add(box(0.6, 0.03, 0.42, m.steel, -0.9, 0.9, back + 0.33));
      g.add(rbox(0.8, 2.0, 0.72, 0.03, m.steel, -0.4 + run / 2 + 0.45, 0, back + 0.36));
      g.add(rbox(run, 0.7, 0.36, 0.01, m.cabinet, -0.4, 1.55, back + 0.18));
      g.add(rbox(1.9, 0.9, 0.9, 0.02, m.cabinet, 0, 0, back + 1.9));
      g.add(box(2.0, 0.05, 1.0, m.counter, 0, 0.9, back + 1.9));
      [-0.5, 0.5].forEach((dx) => {
        g.add(cyl(0.2, 0.05, m.darkWood, dx, 0.7, back + 2.6, 20));
        g.add(cyl(0.025, 0.7, m.steel, dx, 0, back + 2.6, 10));
      });
      break;
    }
    case "bathroom": {
      g.add(rbox(1.7, 0.56, 0.78, 0.1, m.porcelain, -ws / 2 + 1.0, 0, back + 0.4));
      const inner = new THREE.MeshStandardMaterial({ color: "#a9cfe0", roughness: 0.05 });
      g.add(rbox(1.45, 0.02, 0.55, 0.05, inner, -ws / 2 + 1.0, 0.5, back + 0.4));
      g.add(rbox(0.85, 0.82, 0.48, 0.02, m.darkWood, ws / 2 - 0.65, 0, back + 0.25));
      g.add(rbox(0.6, 0.12, 0.38, 0.05, m.porcelain, ws / 2 - 0.65, 0.82, back + 0.25));
      g.add(box(0.7, 0.85, 0.02, m.glass, ws / 2 - 0.65, 1.15, back + 0.01));
      g.add(rbox(0.4, 0.42, 0.56, 0.12, m.porcelain, ws / 2 - 0.45, 0, back + 1.4));
      g.add(rbox(0.42, 0.38, 0.18, 0.04, m.porcelain, ws / 2 - 0.45, 0.4, back + 1.15));
      break;
    }
    case "garage": {
      const car = new THREE.Group();
      car.add(rbox(4.1, 0.62, 1.82, 0.26, m.carPaint, 0, 0.24, 0));
      car.add(rbox(2.3, 0.52, 1.62, 0.22, m.carGlass, -0.25, 0.78, 0));
      [[-1.35, 0.82], [1.35, 0.82], [-1.35, -0.82], [1.35, -0.82]].forEach(([dx, dz]) => {
        const w = mesh(new THREE.CylinderGeometry(0.34, 0.34, 0.24, 28), m.tyre);
        w.rotation.x = Math.PI / 2;
        w.position.set(dx, 0.34, dz);
        car.add(w);
        const hub = mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.25, 20), m.steel);
        hub.rotation.x = Math.PI / 2;
        hub.position.set(dx, 0.34, dz);
        car.add(hub);
      });
      car.position.z = 0.15;
      g.add(car);
      g.add(rbox(2.2, 1.9, 0.45, 0.02, m.alu, -ws / 2 + 1.4, 0, back + 0.22));
      break;
    }
    default: {
      g.add(box(1.4, 0.04, 0.7, m.darkWood, 0, 0.74, back + 0.4));
      g.add(cyl(0.025, 0.74, m.steel, -0.65, 0, back + 0.1, 10));
      g.add(cyl(0.025, 0.74, m.steel, 0.65, 0, back + 0.1, 10));
      g.add(cyl(0.025, 0.74, m.steel, -0.65, 0, back + 0.7, 10));
      g.add(cyl(0.025, 0.74, m.steel, 0.65, 0, back + 0.7, 10));
      g.add(rbox(0.5, 0.5, 0.5, 0.1, m.fabric, 0, 0, back + 1.1));
      g.add(rbox(0.9, 1.9, 0.35, 0.02, m.darkWood, ws / 2 - 0.7, 0, back + 0.18));
      g.add(plant(-ws / 2 + 0.5, ds / 2 - 0.5));
    }
  }
  return g;
}

function tree(x, z, seed, scale = 1) {
  const m = materials();
  const rand = rng(seed);
  const g = new THREE.Group();
  const h = (1.3 + rand() * 0.6) * scale;
  const trunk = mesh(new THREE.CylinderGeometry(0.08 * scale, 0.13 * scale, h, 12), m.trunk);
  trunk.position.set(x, h / 2, z);
  g.add(trunk);
  for (let i = 0; i < 4; i += 1) {
    const r = (0.55 + rand() * 0.35) * scale;
    const leaf = mesh(new THREE.IcosahedronGeometry(r, 2), m.leaf[i % 3]);
    leaf.position.set(x + (rand() - 0.5) * 0.7 * scale, h + (rand() * 0.6 - 0.1) * scale, z + (rand() - 0.5) * 0.7 * scale);
    leaf.scale.y = 0.85;
    g.add(leaf);
  }
  return g;
}

function bush(x, z, seed) {
  const m = materials();
  const rand = rng(seed);
  const leaf = mesh(new THREE.IcosahedronGeometry(0.3 + rand() * 0.2, 2), m.leaf[seed % 3]);
  leaf.position.set(x, 0.25, z);
  leaf.scale.y = 0.75;
  return leaf;
}

function outdoor(room, cx, cz, ws, ds) {
  const m = materials();
  const g = new THREE.Group();
  if (room.kind === "pool") {
    const pw = ws - 1.2;
    const pd = ds - 1.0;
    const wall = 0.25;
    g.add(box(ws, 0.06, ds, m.darkWood, cx, 0, cz, 0.4));
    g.add(box(pw, 0.06, pd, m.poolTile, cx, 0.06, cz, 0.35));
    g.add(box(pw + wall * 2, 0.5, wall, m.counter, cx, 0.06, cz - pd / 2 - wall / 2));
    g.add(box(pw + wall * 2, 0.5, wall, m.counter, cx, 0.06, cz + pd / 2 + wall / 2));
    g.add(box(wall, 0.5, pd, m.counter, cx - pw / 2 - wall / 2, 0.06, cz));
    g.add(box(wall, 0.5, pd, m.counter, cx + pw / 2 + wall / 2, 0.06, cz));
    const water = mesh(new THREE.BoxGeometry(pw, 0.36, pd), m.water, false);
    water.position.set(cx, 0.12 + 0.18, cz);
    water.userData.pool = true;
    g.add(water);
    g.add(rbox(0.6, 0.3, 1.6, 0.05, m.fabricLight, cx + ws / 2 - 0.4, 0.06, cz));
  } else {
    g.add(box(ws - 0.3, 0.04, ds - 0.3, m.lawn, cx, 0, cz, 0.25));
    g.add(box(ws - 0.3, 0.12, 0.6, m.soil, cx, 0, cz - ds / 2 + 0.5));
    for (let i = 0; i < 6; i += 1) {
      g.add(bush(cx - ws / 2 + 0.6 + i * ((ws - 1.2) / 5), cz - ds / 2 + 0.5, 70 + i));
    }
    g.add(tree(cx - ws / 4, cz + 0.4, 81));
    g.add(tree(cx + ws / 4, cz + 0.2, 82, 1.15));
  }
  return g;
}

/* ------------------------------------------------------------------ */
/* Sky                                                                 */
/* ------------------------------------------------------------------ */

function skyTexture(top, bottom) {
  const canvas = document.createElement("canvas");
  canvas.width = 4;
  canvas.height = 256;
  const g = canvas.getContext("2d");
  const grad = g.createLinearGradient(0, 0, 0, 256);
  grad.addColorStop(0, top);
  grad.addColorStop(1, bottom);
  g.fillStyle = grad;
  g.fillRect(0, 0, 4, 256);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

/* ------------------------------------------------------------------ */
/* The twin                                                            */
/* ------------------------------------------------------------------ */

export class DigitalTwin3D {
  constructor(stage) {
    const probe = document.createElement("canvas");
    if (!probe.getContext("webgl2")) {
      throw new Error("WebGL2 is not available");
    }
    this.stage = stage;
    stage.classList.add("is-3d");
    stage.replaceChildren();

    const renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    stage.appendChild(renderer.domElement);
    this.renderer = renderer;

    this.labels = new CSS2DRenderer();
    this.labels.domElement.className = "twin3d-labels";
    stage.appendChild(this.labels.domElement);

    const hint = document.createElement("div");
    hint.className = "twin3d-hint";
    hint.textContent = "Glisser pour tourner · molette pour zoomer · clic droit pour déplacer";
    stage.appendChild(hint);
    this.setupDemo();

    const scene = new THREE.Scene();
    this.scene = scene;
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.fog = new THREE.Fog("#dfe8ec", 80, 220);

    this.camera = new THREE.PerspectiveCamera(35, 16 / 9, 0.1, 400);
    this.controls = new OrbitControls(this.camera, renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.06;
    this.controls.maxPolarAngle = 1.38;
    this.controls.minDistance = 6;
    this.controls.maxDistance = 60;
    this.controls.autoRotate = true;
    this.controls.autoRotateSpeed = 0.35;
    this.controls.addEventListener("start", () => {
      this.controls.autoRotate = false;
    });

    this.hemi = new THREE.HemisphereLight("#cfe6ff", "#6b7a4a", 0.6);
    scene.add(this.hemi);
    this.sun = new THREE.DirectionalLight("#fff3e0", 3);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(2048, 2048);
    this.sun.shadow.bias = -0.0003;
    this.sun.shadow.normalBias = 0.03;
    this.sun.shadow.radius = 4;
    scene.add(this.sun, this.sun.target);

    const ground = mesh(boxUV(new THREE.BoxGeometry(220, 0.1, 220).translate(0, -0.05, 0), 0.25), materials().grass, false);
    scene.add(ground);

    this.world = new THREE.Group();
    scene.add(this.world);
    this.dynamic = { pulses: [], lamps: [], glass: new Map() };

    const size = this.size();
    const rt = new THREE.WebGLRenderTarget(size.w, size.h, { type: THREE.HalfFloatType, samples: 4 });
    this.composer = new EffectComposer(renderer, rt);
    this.composer.addPass(new RenderPass(scene, this.camera));
    this.gtao = new GTAOPass(scene, this.camera, size.w, size.h);
    this.gtao.updateGtaoMaterial({ radius: 0.5, distanceExponent: 1.5, thickness: 1, scale: 1.2, samples: 16 });
    this.gtao.blendIntensity = 0.9;
    this.composer.addPass(this.gtao);
    this.bloom = new UnrealBloomPass(new THREE.Vector2(size.w, size.h), 0.22, 0.4, 2.2);
    this.composer.addPass(this.bloom);
    this.composer.addPass(new OutputPass());

    this.rain = this.makeRain();
    scene.add(this.rain);

    this.signature = null;
    this.hour = null;
    this.clock = new THREE.Clock();
    this.resize();
    new ResizeObserver(() => this.resize()).observe(stage);
    renderer.setAnimationLoop(() => this.frame());
  }

  size() {
    const w = Math.max(320, this.stage.clientWidth || 800);
    const h = Math.max(300, this.stage.clientHeight || Math.round(w * 0.56));
    return { w, h };
  }

  resize() {
    const { w, h } = this.size();
    this.renderer.setSize(w, h, false);
    this.labels.setSize(w, h);
    this.composer.setSize(w, h);
    this.composer.setPixelRatio(this.renderer.getPixelRatio());
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  setState(state) {
    const rooms = state.rooms || [];
    const signature = JSON.stringify(rooms.map((room) => [room.id, room.kind, room.name]));
    if (signature !== this.signature) {
      this.signature = signature;
      this.build(rooms);
    }
    this.base = state;
    if (this.demo) {
      return;
    }
    this.update(state);
  }

  /* ---------------- static build (rooms) ---------------- */

  build(rooms) {
    if (this.demo) {
      this.stopDemo(false);
    }
    disposeTree(this.world);
    this.world.clear();
    this.dynamic = { pulses: [], lamps: [], glass: new Map(), labels: {}, roomTags: {} };
    const m = materials();
    const plan = layout(rooms);
    const offX = (COLS * CW) / 2;
    const offZ = (plan.rows * CD) / 2;
    const rect = (room) => {
      const x0 = room.x * CW - offX;
      const z0 = room.y * CD - offZ;
      const ws = room.w * CW;
      const ds = room.h * CD;
      return { x0, z0, ws, ds, cx: x0 + ws / 2, cz: z0 + ds / 2 };
    };

    const owner = new Map();
    plan.placed.forEach((room) => {
      for (let dy = 0; dy < room.h; dy += 1) {
        for (let dx = 0; dx < room.w; dx += 1) {
          owner.set(`${room.x + dx},${room.y + dy}`, room);
        }
      }
    });
    const indoor = plan.placed.filter((room) => INDOOR.has(room.kind));
    this.rects = new Map(plan.placed.map((room) => [String(room.id), { ...rect(room), room }]));

    // Terrace under the house.
    let minX = Infinity;
    let maxX = -Infinity;
    let minZ = Infinity;
    let maxZ = -Infinity;
    plan.placed.forEach((room) => {
      const r = rect(room);
      minX = Math.min(minX, r.x0);
      maxX = Math.max(maxX, r.x0 + r.ws);
      minZ = Math.min(minZ, r.z0);
      maxZ = Math.max(maxZ, r.z0 + r.ds);
    });
    if (!plan.placed.length) {
      minX = -4;
      maxX = 4;
      minZ = -3;
      maxZ = 3;
    }
    this.bounds = { minX, maxX, minZ, maxZ };
    this.world.add(box(maxX - minX + 3, 0.04, maxZ - minZ + 2.4, m.paving, (minX + maxX) / 2, 0, (minZ + maxZ) / 2, 0.45));

    const glassFor = (room) => {
      const key = String(room.id);
      if (!this.dynamic.glass.has(key)) {
        const mat = m.glass.clone();
        mat.userData.own = true;
        this.dynamic.glass.set(key, mat);
      }
      return this.dynamic.glass.get(key);
    };

    // Floors, furniture, lamps, labels.
    indoor.forEach((room) => {
      const r = rect(room);
      const floorMat = room.kind === "bathroom" ? m.tile
        : room.kind === "kitchen" ? m.kitchenTile
          : room.kind === "garage" ? m.concrete : m.wood;
      const scale = room.kind === "bathroom" ? 0.36 : room.kind === "kitchen" ? 0.5 : 0.3;
      this.world.add(box(r.ws, FLOOR, r.ds, floorMat, r.cx, 0, r.cz, scale));
      const furniture = furnish(room, r.ws, r.ds);
      furniture.position.set(r.cx, FLOOR, r.cz);
      this.world.add(furniture);

      const lampMat = emissive("#ffd9a6", 0);
      lampMat.userData.own = true;
      const shade = mesh(new THREE.SphereGeometry(0.14, 24, 16), lampMat, false);
      shade.position.set(r.cx, FLOOR + H - 0.45, r.cz);
      this.world.add(shade);
      this.world.add(cyl(0.006, 0.31, m.cable, r.cx, FLOOR + H - 0.32, r.cz, 6));
      const light = new THREE.PointLight("#ffcf94", 0, Math.max(r.ws, r.ds) * 1.4, 2);
      light.position.set(r.cx, FLOOR + H - 0.6, r.cz);
      this.world.add(light);
      this.dynamic.lamps.push({ id: String(room.id), light, mat: lampMat });

      const tag = label(roomName(room));
      tag.position.set(r.cx, FLOOR + H + 0.45, r.cz);
      this.world.add(tag);
      this.dynamic.roomTags[String(room.id)] = tag;
    });

    // Walls: one segment per cell edge that separates two spaces.
    const exterior = new Map();
    const interior = new Map();
    const doors = new Set();
    const posts = new Set();
    const vx = (x) => x * CW - offX;
    const vz = (y) => y * CD - offZ;
    indoor.forEach((room) => {
      for (let dy = 0; dy < room.h; dy += 1) {
        for (let dx = 0; dx < room.w; dx += 1) {
          const x = room.x + dx;
          const y = room.y + dy;
          const edges = [
            ["N", x, y - 1, [x, y], [x + 1, y]],
            ["S", x, y + 1, [x, y + 1], [x + 1, y + 1]],
            ["W", x - 1, y, [x, y], [x, y + 1]],
            ["E", x + 1, y, [x + 1, y], [x + 1, y + 1]],
          ];
          edges.forEach(([dir, nx, ny, p, q]) => {
            const next = owner.get(`${nx},${ny}`);
            if (next === room) {
              return;
            }
            const key = `${p.join(",")}|${q.join(",")}`;
            if (next && INDOOR.has(next.kind)) {
              if (!interior.has(key)) {
                const pair = [String(room.id), String(next.id)].sort().join("|");
                const type = doors.has(pair) ? null : "door";
                doors.add(pair);
                interior.set(key, { p, q, type, room });
              }
            } else {
              const list = exterior.get(room) || [];
              list.push({ dir, p, q, key });
              exterior.set(room, list);
            }
          });
        }
      }
    });
    const segments = [...interior.values()];
    exterior.forEach((list, room) => {
      const front = list.find((s) => s.dir === "S") || list[0];
      list.forEach((s) => {
        let type = "window";
        if (room.kind === "bathroom") {
          type = "smallWindow";
        }
        if (room.kind === "garage") {
          type = s === front ? "garage" : null;
        }
        if (room.kind === "living_room" && s === front) {
          type = "entrance";
        }
        segments.push({ p: s.p, q: s.q, type, room });
      });
    });
    segments.forEach((s) => {
      const a = { x: vx(s.p[0]), z: vz(s.p[1]) };
      const b = { x: vx(s.q[0]), z: vz(s.q[1]) };
      this.world.add(wallSegment(a, b, s.type, s.room, glassFor));
      posts.add(s.p.join(","));
      posts.add(s.q.join(","));
    });
    posts.forEach((key) => {
      const [x, y] = key.split(",").map(Number);
      this.world.add(box(T, H, T, m.wall, vx(x), FLOOR, vz(y), 0.5));
    });

    // Garden and pool.
    plan.placed.filter((room) => !INDOOR.has(room.kind)).forEach((room) => {
      const r = rect(room);
      this.world.add(outdoor(room, r.cx, r.cz, r.ws, r.ds));
      const tag = label(roomName(room));
      tag.position.set(r.cx, 1.6, r.cz);
      this.world.add(tag);
    });

    this.buildEquipment();
    this.buildFlows();
    this.frameCamera();
  }

  buildEquipment() {
    const m = materials();
    const { minX, maxX, minZ, maxZ } = this.bounds;
    const ex = maxX + 2.4;
    const eq = {};

    // Equipment pad.
    this.world.add(box(3.2, 0.08, 7.2, m.concrete, ex + 0.4, 0, minZ + 3.4, 0.4));

    // Water tank: translucent shell, water level follows the tank percent.
    const tank = new THREE.Group();
    tank.position.set(ex + 0.6, 0.08, minZ + 1.4);
    tank.add(cyl(0.9, 0.14, m.concrete, 0, 0, 0));
    const shell = mesh(new THREE.CylinderGeometry(0.82, 0.82, 2.3, 48, 1, true).translate(0, 1.29, 0), m.tankShell, false);
    tank.add(shell);
    tank.add(cyl(0.84, 0.06, m.steel, 0, 2.44, 0, 48));
    [0.6, 1.3, 2.0].forEach((y) => {
      const ring = mesh(new THREE.TorusGeometry(0.83, 0.018, 8, 64), m.steel);
      ring.rotation.x = Math.PI / 2;
      ring.position.y = y;
      tank.add(ring);
    });
    const water = mesh(new THREE.CylinderGeometry(0.79, 0.79, 1, 48).translate(0, 0.5, 0), m.tankWater, false);
    water.position.y = 0.15;
    tank.add(water);
    this.world.add(tank);
    eq.tankWater = water;
    eq.tankPos = tank.position.clone();
    eq.tankLabel = label("Citerne", "is-equipment");
    eq.tankLabel.position.set(tank.position.x, 3.0, tank.position.z);
    this.world.add(eq.tankLabel);

    // Battery wall unit with a five-step LED gauge.
    const battery = new THREE.Group();
    battery.position.set(ex + 0.3, 0.08, minZ + 3.6);
    battery.add(rbox(0.75, 1.5, 0.32, 0.05, m.batteryBody, 0, 0, 0));
    eq.leds = [];
    for (let i = 0; i < 5; i += 1) {
      const mat = emissive("#3ddc84", 0);
      mat.userData.own = true;
      const led = mesh(new THREE.BoxGeometry(0.38, 0.05, 0.02), mat, false);
      led.position.set(0, 0.45 + i * 0.12, 0.17);
      battery.add(led);
      eq.leds.push(mat);
    }
    battery.rotation.y = -Math.PI / 2;
    this.world.add(battery);
    eq.batteryPos = battery.position.clone();
    eq.batteryLabel = label("Batterie", "is-equipment");
    eq.batteryLabel.position.set(battery.position.x, 2.1, battery.position.z);
    this.world.add(eq.batteryLabel);

    // Pump with a status light.
    const pump = new THREE.Group();
    pump.position.set(ex + 0.6, 0.08, minZ + 5.6);
    pump.add(rbox(0.7, 0.12, 0.45, 0.02, m.concrete, 0, 0, 0));
    const body = mesh(new THREE.CylinderGeometry(0.17, 0.17, 0.5, 24), m.pumpBody);
    body.rotation.z = Math.PI / 2;
    body.position.set(0, 0.32, 0);
    pump.add(body);
    pump.add(cyl(0.12, 0.25, m.steel, 0.3, 0.12, 0, 20));
    const pumpLed = emissive("#3ddc84", 0);
    pumpLed.userData.own = true;
    const led = mesh(new THREE.SphereGeometry(0.04, 12, 8), pumpLed, false);
    led.position.set(0, 0.52, 0);
    pump.add(led);
    this.world.add(pump);
    eq.pumpLed = pumpLed;
    eq.pumpPos = pump.position.clone();
    eq.pumpLabel = label("Pompe", "is-equipment");
    eq.pumpLabel.position.set(pump.position.x, 1.2, pump.position.z);
    this.world.add(eq.pumpLabel);

    // Ground-mounted solar array, tilted to the sun.
    const solar = new THREE.Group();
    const sx = minX - 3.6;
    const sz = (minZ + maxZ) / 2;
    solar.position.set(sx, 0, sz);
    const tilt = 0.45;
    for (let row = 0; row < 2; row += 1) {
      for (let col = 0; col < 3; col += 1) {
        const panel = new THREE.Group();
        panel.add(box(1.02, 0.04, 1.7, m.solar, 0, 0, 0));
        panel.add(box(1.06, 0.05, 0.03, m.alu, 0, -0.005, -0.85));
        panel.add(box(1.06, 0.05, 0.03, m.alu, 0, -0.005, 0.85));
        panel.rotation.x = tilt;
        panel.position.set(-1.1 + col * 1.1, 0.95, -1.4 + row * 2.6);
        solar.add(panel);
        solar.add(cyl(0.03, 0.62, m.alu, -1.1 + col * 1.1, 0, -1.4 + row * 2.6 + 0.7, 10));
        solar.add(cyl(0.03, 1.3, m.alu, -1.1 + col * 1.1, 0, -1.4 + row * 2.6 - 0.7, 10));
      }
    }
    this.world.add(solar);
    eq.solarPos = solar.position.clone();
    eq.solarLabel = label("Solaire", "is-equipment");
    eq.solarLabel.position.set(sx, 2.4, sz);
    this.world.add(eq.solarLabel);

    // Valve on the tank outlet.
    const valveMat = emissive("#3ddc84", 1.5);
    valveMat.userData.own = true;
    const wheel = mesh(new THREE.TorusGeometry(0.13, 0.025, 10, 32), valveMat, false);
    wheel.position.set(eq.tankPos.x - 1.0, 0.42, eq.tankPos.z);
    wheel.rotation.y = Math.PI / 2;
    this.world.add(wheel);
    this.world.add(cyl(0.02, 0.27, m.steel, wheel.position.x, 0.15, wheel.position.z, 8));
    eq.valveMat = valveMat;
    eq.valveLabel = label("Vanne", "is-equipment");
    eq.valveLabel.position.set(wheel.position.x, 0.95, wheel.position.z);
    this.world.add(eq.valveLabel);

    // Utility pole: the public grid connection.
    const pole = new THREE.Group();
    pole.position.set(maxX + 1.4, 0, minZ - 2.2);
    pole.add(cyl(0.11, 6.5, m.darkWood, 0, 0, 0, 14));
    pole.add(box(1.6, 0.1, 0.1, m.darkWood, 0, 6.0, 0));
    [-0.65, 0, 0.65].forEach((x) => pole.add(cyl(0.04, 0.16, m.porcelain, x, 6.1, 0, 10)));
    pole.add(rbox(0.45, 0.6, 0.4, 0.04, m.alu, 0, 4.6, 0.25));
    this.world.add(pole);
    eq.gridPos = pole.position.clone();
    eq.gridLabel = label("Réseau électrique", "is-equipment");
    eq.gridLabel.position.set(pole.position.x, 7.0, pole.position.z);
    this.world.add(eq.gridLabel);

    this.eq = eq;
  }

  roomCenter(kind) {
    const hit = [...this.rects.values()].find((r) => r.room.kind === kind);
    return hit ? new THREE.Vector3(hit.cx, 0, hit.cz) : null;
  }

  buildFlows() {
    const m = materials();
    const { minX, minZ } = this.bounds;
    const eq = this.eq;
    const y = 0.16;
    const V = (x, z) => new THREE.Vector3(x, y, z);
    const routes = {};
    const tx = eq.tankPos.x - 1.0;
    const bath = this.roomCenter("bathroom");
    if (bath) {
      routes.water_bathroom = [V(eq.tankPos.x - 0.8, eq.tankPos.z), V(tx, eq.tankPos.z), V(tx, bath.z), V(bath.x, bath.z)];
    }
    const garden = this.roomCenter("garden") || this.roomCenter("pool");
    if (garden) {
      routes.water_garden = [V(eq.pumpPos.x, eq.pumpPos.z), V(tx + 0.3, eq.pumpPos.z), V(tx + 0.3, garden.z), V(garden.x, garden.z)];
    }
    const home = this.roomCenter("living_room") || this.roomCenter("kitchen") || this.roomCenter("bedroom");
    const sx = eq.solarPos.x + 1.8;
    if (home) {
      routes.solar_home = [V(sx, eq.solarPos.z), V(home.x, eq.solarPos.z), V(home.x, home.z)];
    }
    const back = minZ - 1.0;
    routes.solar_battery = [V(eq.solarPos.x, eq.solarPos.z - 2.3), V(eq.solarPos.x, back), V(eq.batteryPos.x - 0.4, back), V(eq.batteryPos.x - 0.4, eq.batteryPos.z)];
    routes.battery_pump = [V(eq.batteryPos.x, eq.batteryPos.z + 0.4), V(eq.batteryPos.x, eq.pumpPos.z), V(eq.pumpPos.x - 0.3, eq.pumpPos.z)];
    if (home) {
      routes.grid_home = [V(eq.gridPos.x, eq.gridPos.z), V(home.x + 0.4, eq.gridPos.z), V(home.x + 0.4, home.z + 0.4)];
      routes.battery_home = [V(eq.batteryPos.x - 0.3, eq.batteryPos.z), V(home.x - 0.4, eq.batteryPos.z), V(home.x - 0.4, home.z - 0.4)];
    }
    routes.roof_tank = [V(minX + 0.5, back + 0.3), V(eq.tankPos.x, back + 0.3), V(eq.tankPos.x, eq.tankPos.z - 0.8)];

    this.flows = {};
    Object.entries(routes).forEach(([id, points]) => {
      const path = new THREE.CurvePath();
      for (let i = 0; i < points.length - 1; i += 1) {
        path.add(new THREE.LineCurve3(points[i], points[i + 1]));
      }
      const water = id.startsWith("water") || id === "roof_tank";
      const mat = water ? m.pipe : m.cable;
      const tube = mesh(new THREE.TubeGeometry(path, points.length * 24, water ? 0.04 : 0.025, 10, false), mat, false);
      this.world.add(tube);
      const length = path.getLength();
      const count = Math.max(4, Math.round(length / 1.2));
      const pulseMat = emissive(water ? "#4fc3ff" : "#ffc23d", 6);
      pulseMat.userData.own = true;
      const pulses = [];
      for (let i = 0; i < count; i += 1) {
        const dot = mesh(new THREE.SphereGeometry(water ? 0.065 : 0.05, 12, 8), pulseMat, false);
        dot.visible = false;
        this.world.add(dot);
        pulses.push(dot);
      }
      this.flows[id] = { path, tube, length, pulses, active: false, water };
    });
  }

  frameCamera() {
    const { minX, maxX, minZ, maxZ } = this.bounds;
    const cx = (minX + maxX) / 2;
    const cz = (minZ + maxZ) / 2;
    const span = Math.max(maxX - minX + 8, maxZ - minZ + 4);
    this.center = new THREE.Vector3(cx, 0, cz);
    this.span = span;
    this.controls.target.set(cx, 0.8, cz);
    this.camera.position.set(cx + span * 0.55, span * 0.6, cz + span * 0.8);
    this.controls.update();
    const cam = this.sun.shadow.camera;
    cam.left = -span;
    cam.right = span;
    cam.top = span;
    cam.bottom = -span;
    cam.near = 1;
    cam.far = span * 5;
    cam.updateProjectionMatrix();
  }

  /* ---------------- dynamic update (state) ---------------- */

  update(state) {
    const eq = this.eq;
    const flows = new Map((state.flows || []).map((flow) => [flow.id, flow]));
    const raining = Boolean(state.weather && state.weather.raining);
    let hour = Number.isFinite(state.clockHour) ? state.clockHour % 24 : new Date().getHours() + new Date().getMinutes() / 60;
    if (hour < 0) {
      hour += 24;
    }
    const weather = state.weather || {};
    this.applySky(hour, raining, Boolean(weather.heat));
    const dry = Boolean(weather.drought);
    this.world.traverse((node) => {
      if (node.userData.pool) {
        const low = weather.drought ? 0.45 : weather.heat ? 0.75 : 1;
        node.scale.y = low;
        node.position.y = 0.12 + 0.18 * low;
      }
    });
    const look = dry ? "dry" : weather.heat ? "hot" : "green";
    if (look !== this.look) {
      this.look = look;
      materials().grass.color.set(dry ? "#e0c98a" : look === "hot" ? "#f2e2b0" : "#ffffff");
      materials().lawn.color.set(dry ? "#d8c27e" : "#cfe6a8");
      materials().leaf.forEach((mat, i) => mat.color.set(dry ? ["#7a7a3a", "#8a8240", "#6b6a33"][i] : ["#3f6b2f", "#4f7d35", "#2f5a2a"][i]));
    }
    const night = this.night;

    const lit = new Set((state.rooms || []).filter((room) => room.lights_on).map((room) => String(room.id)));
    this.dynamic.lamps.forEach((lamp) => {
      const on = lit.has(lamp.id);
      lamp.light.intensity = on ? 9 + night * 9 : 0;
      lamp.mat.emissiveIntensity = on ? 5 : 0;
      const glass = this.dynamic.glass.get(lamp.id);
      if (glass) {
        glass.emissive.set("#ffb867");
        glass.emissiveIntensity = on ? 0.15 + night * 1.2 : 0;
      }
    });

    const tank = state.tank || {};
    const percent = Math.max(0, Math.min(100, Number(tank.percent) || 0));
    eq.tankWater.scale.y = Math.max(0.001, (percent / 100) * 2.25);
    eq.tankLabel.element.textContent = `Citerne ${percent} %${tank.liters != null ? ` · ${Math.round(tank.liters)} L` : ""}`;
    eq.tankLabel.element.classList.toggle("is-alert", percent < 20);

    const battery = state.battery || {};
    const bp = Math.max(0, Math.min(100, Number(battery.percent) || 0));
    const steps = Math.ceil(bp / 20);
    const color = bp < 20 ? "#ff4d3d" : bp < 50 ? "#ffb02e" : "#3ddc84";
    eq.leds.forEach((mat, i) => {
      mat.emissive.set(color);
      mat.emissiveIntensity = i < steps ? 3.5 : 0.05;
    });
    eq.batteryLabel.element.textContent = `Batterie ${bp} %${battery.state ? ` · ${BATTERY_FR[battery.state] || battery.state}` : ""}`;
    eq.batteryLabel.element.classList.toggle("is-alert", bp < 20);

    const running = Boolean(state.pump && state.pump.running);
    eq.pumpLed.emissive.set(running ? "#3ddc84" : "#ff4d3d");
    eq.pumpLed.emissiveIntensity = running ? 4 : 1.2;
    eq.pumpLabel.element.textContent = running ? "Pompe en marche" : "Pompe arrêtée";

    const watts = state.solar ? state.solar.watts : 0;
    eq.solarLabel.element.textContent = `Solaire ${watts} W`;

    const open = !(state.valve && state.valve.open === false);
    eq.valveMat.emissive.set(open ? "#3ddc84" : "#ff3b2f");
    eq.valveLabel.element.textContent = open ? "Vanne ouverte" : "Vanne fermée";
    eq.valveLabel.element.classList.toggle("is-alert", !open);
    const m = materials();
    ["water_bathroom", "water_garden"].forEach((id) => {
      if (this.flows[id]) {
        this.flows[id].tube.material = open ? m.pipe : m.pipeClosed;
      }
    });

    Object.entries(this.flows).forEach(([id, flow]) => {
      const data = flows.get(id);
      flow.active = Boolean(data && data.active);
      flow.pulses.forEach((dot) => {
        dot.visible = flow.active;
      });
    });

    if (eq.gridLabel) {
      const grid = state.grid || "ok";
      eq.gridLabel.element.textContent = grid === "down" ? "Réseau coupé" : "Réseau électrique";
      eq.gridLabel.element.classList.toggle("is-alert", grid === "down");
    }
    const alerts = new Set(state.alertRooms || []);
    Object.entries(this.dynamic.roomTags || {}).forEach(([id, tag]) => {
      tag.element.classList.toggle("is-alert", alerts.has(id));
    });

    this.rain.visible = raining;
  }

  applySky(hour, raining, heat = false) {
    const key = `${Math.round(hour * 4)}|${raining}|${heat}`;
    if (key === this.skyKey) {
      return;
    }
    this.skyKey = key;
    const angle = (Math.PI * (hour - 6)) / 12;
    const elevation = Math.sin(angle);
    const day = THREE.MathUtils.clamp(elevation * 1.6, 0, 1);
    const dusk = THREE.MathUtils.clamp(1 - Math.abs(elevation) * 3.5, 0, 1);
    this.night = 1 - day;
    const span = this.span || 20;
    const c = this.center || new THREE.Vector3();
    const sunY = Math.max(0.15, elevation) * span * 1.4;
    this.sun.position.set(c.x + Math.cos(angle) * span * 1.3, sunY, c.z + span * 0.9);
    this.sun.target.position.copy(c);
    const overcast = raining ? 0.3 : 1;
    const warm = new THREE.Color("#ff9a5a");
    const white = new THREE.Color("#fff4e2");
    const moon = new THREE.Color("#9db4ff");
    this.sun.color.copy(day > 0 ? white.clone().lerp(warm, dusk) : moon);
    this.sun.intensity = (day > 0 ? 0.3 + 2.2 * day : 0.1) * overcast;
    this.hemi.intensity = (0.04 + 0.36 * day) * (raining ? 0.8 : 1);
    this.scene.environmentIntensity = 0.04 + 0.51 * day * (raining ? 0.7 : 1);

    const lerp = (a, b, t) => new THREE.Color(a).lerp(new THREE.Color(b), t);
    let top = lerp("#06101f", "#5d9bd6", day);
    let bottom = lerp("#1b2840", "#e9f0ee", day);
    top = top.lerp(new THREE.Color("#7a6aa8"), dusk * 0.5);
    bottom = bottom.lerp(new THREE.Color("#f2b48a"), dusk * 0.6);
    if (heat) {
      top = top.lerp(new THREE.Color("#e3a861"), 0.45 * day);
      bottom = bottom.lerp(new THREE.Color("#f7d39a"), 0.6 * day);
      this.sun.color.lerp(new THREE.Color("#ffb060"), 0.35);
      this.sun.intensity *= 1.25;
      this.hemi.groundColor.set("#a08050");
    }
    if (raining) {
      top = top.lerp(new THREE.Color("#6d7782"), 0.7);
      bottom = bottom.lerp(new THREE.Color("#a7afb5"), 0.7);
    }
    if (this.scene.background) {
      this.scene.background.dispose();
    }
    this.scene.background = skyTexture(`#${top.getHexString()}`, `#${bottom.getHexString()}`);
    this.scene.fog.color.copy(bottom);
    this.scene.fog.near = span * 3;
    this.scene.fog.far = span * 8;
    if (!heat) {
      this.hemi.groundColor.set("#6b7a4a");
    }
    this.renderer.toneMappingExposure = 0.85 + this.night * 0.35 + (heat ? 0.12 : 0);
  }

  makeRain() {
    const count = 2500;
    const pos = new Float32Array(count * 6);
    const rand = rng(99);
    this.rainSeed = [];
    for (let i = 0; i < count; i += 1) {
      const x = (rand() - 0.5) * 50;
      const y = rand() * 18;
      const z = (rand() - 0.5) * 50;
      this.rainSeed.push([x, y, z]);
      pos.set([x, y, z, x - 0.03, y - 0.35, z], i * 6);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const lines = new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color: "#c7d9e8", transparent: true, opacity: 0.5 }));
    lines.visible = false;
    lines.frustumCulled = false;
    return lines;
  }

  frame() {
    const raw = this.clock.getDelta();
    const dt = Math.min(raw, 0.05);
    const time = this.clock.elapsedTime;
    // The demo runs on wall-clock time so it lasts the same on slow machines.
    this.demoFrame(Math.min(raw, 0.25) * (window.KZ_DEMO_SPEED || 1), time);
    this.controls.update();

    if (this.flows) {
      Object.values(this.flows).forEach((flow) => {
        if (!flow.active) {
          return;
        }
        const speed = (flow.water ? 1.1 : 1.8) / flow.length;
        flow.pulses.forEach((dot, i) => {
          const t = (time * speed + i / flow.pulses.length) % 1;
          dot.position.copy(flow.path.getPointAt(t));
        });
      });
    }

    if (this.rain.visible) {
      const attr = this.rain.geometry.attributes.position;
      const c = this.center || new THREE.Vector3();
      for (let i = 0; i < this.rainSeed.length; i += 1) {
        const seed = this.rainSeed[i];
        seed[1] -= dt * 11;
        if (seed[1] < 0) {
          seed[1] += 18;
        }
        const x = c.x + seed[0];
        const z = c.z + seed[2];
        attr.setXYZ(i * 2, x, seed[1], z);
        attr.setXYZ(i * 2 + 1, x - 0.03, seed[1] - 0.35, z);
      }
      attr.needsUpdate = true;
    }

    this.composer.render();
    this.labels.render(this.scene, this.camera);
  }
}

/* ------------------------------------------------------------------ */
/* Demo mode: scripted scenarios played in the 3D scene                */
/* ------------------------------------------------------------------ */
// Purely visual. It never writes to the server or the database: it plays a
// copy of the home's state forward, then gives the real state back.

const DEMO_CSS = `
.twin3d-demo{position:absolute;top:12px;left:12px;display:flex;flex-direction:column;gap:6px;z-index:5;max-width:230px}
.twin3d-demo button{all:unset;cursor:pointer;padding:7px 12px;border-radius:10px;background:rgba(22,48,42,.82);color:#f4efe6;font:600 13px/1.2 system-ui,-apple-system,"Segoe UI",sans-serif;box-shadow:0 2px 10px rgba(0,0,0,.2);backdrop-filter:blur(6px);transition:background .2s,transform .1s}
.twin3d-demo button:hover{background:rgba(15,110,110,.95)}
.twin3d-demo button:active{transform:scale(.97)}
.twin3d-demo button.is-on{background:#0f6e6e;outline:2px solid #9be3d3}
.twin3d-demo button.is-stop{background:rgba(192,57,43,.9)}
.twin3d-demo .twin3d-demo-title{color:#16302a;background:rgba(244,239,230,.88);padding:4px 10px;border-radius:8px;font:700 11px/1.2 system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase}
.twin3d-banner{position:absolute;top:14px;left:50%;transform:translateX(-50%);width:min(640px,calc(100% - 280px));z-index:5;pointer-events:none;opacity:0;transition:opacity .35s}
.twin3d-banner.is-on{opacity:1}
.twin3d-banner-box{background:rgba(10,24,20,.86);color:#fff;border-radius:14px;padding:12px 16px;box-shadow:0 6px 24px rgba(0,0,0,.3);backdrop-filter:blur(8px);font:500 15px/1.35 system-ui,-apple-system,"Segoe UI",sans-serif}
.twin3d-banner-tag{display:inline-block;font:700 11px/1 system-ui,sans-serif;letter-spacing:.08em;padding:4px 8px;border-radius:999px;background:#c0392b;margin-right:8px;vertical-align:2px}
.twin3d-banner-tag.is-ok{background:#1f8f6a}
.twin3d-banner-tag.is-info{background:#0f6e6e}
.twin3d-banner-meta{display:flex;gap:14px;margin-top:8px;font:600 12px/1.2 system-ui,sans-serif;color:#cfe6de}
.twin3d-banner-bar{height:3px;border-radius:2px;background:rgba(255,255,255,.18);margin-top:8px;overflow:hidden}
.twin3d-banner-bar>i{display:block;height:100%;width:0;background:#9be3d3}
.twin-stage.is-3d:fullscreen{height:100vh;border-radius:0}
@media (max-width:720px){.twin3d-banner{width:calc(100% - 24px);top:auto;bottom:40px}}
`;

const NIGHT = (h) => {
  const x = ((h % 24) + 24) % 24;
  return x < 6.5 || x >= 19;
};

function daylight(h) {
  const x = ((h % 24) + 24) % 24;
  return Math.max(0, Math.sin((Math.PI * (x - 6)) / 12));
}

function fmtHour(h) {
  const x = ((h % 24) + 24) % 24;
  const hh = Math.floor(x);
  const mm = Math.floor((x - hh) * 60);
  return `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
}

const SCENARIOS = {
  tour: {
    label: "Visite guidée",
    duration: 34,
    setup: (sim) => {
      sim.hour = 16;
    },
    steps: [
      { at: 0, tag: "info", say: "Bienvenue dans le jumeau numérique KIZUNA : chaque pièce est construite à partir des données réelles du foyer.", cam: "overview" },
      { at: 5, tag: "info", say: "Le salon et la cuisine : l'éclairage et les appareils suivent leur état en temps réel.", cam: "room:living_room|kitchen" },
      { at: 10, tag: "info", say: "La salle de bain : les capteurs de débit surveillent chaque litre consommé.", cam: "room:bathroom" },
      { at: 15, tag: "info", say: "Les panneaux solaires alimentent la maison et rechargent la batterie.", cam: "solar" },
      { at: 20, tag: "info", say: "La batterie stocke l'énergie pour les coupures et la nuit.", cam: "battery" },
      { at: 25, tag: "info", say: "La citerne récupère l'eau de pluie. La vanne intelligente peut couper l'eau en cas de fuite.", cam: "tank" },
      { at: 30, tag: "ok", say: "Eau et énergie, pièce par pièce : KIZUNA rend chaque foyer résilient.", cam: "overview" },
    ],
  },
  leak: {
    label: "Fuite d'eau",
    duration: 26,
    setup: (sim) => {
      sim.hour = 14;
      sim.tank = 78;
    },
    steps: [
      { at: 0, tag: "alert", say: "Scénario : une canalisation cède dans la salle de bain.", cam: "room:bathroom", run: (sim) => { sim.leak = true; sim.tankRate = -1.6; } },
      { at: 3, tag: "alert", say: "Les capteurs détectent un débit anormal alors qu'aucun appareil n'est allumé.", run: (sim) => { sim.alert = "bathroom"; } },
      { at: 10, tag: "info", say: "L'IA KIZUNA confirme la fuite et ferme la vanne automatiquement.", cam: "valve", run: (sim) => { sim.valveOpen = false; sim.leak = false; sim.tankRate = 0; } },
      { at: 16, tag: "ok", say: "Fuite stoppée en quelques secondes. Le propriétaire reçoit une alerte sur son téléphone.", cam: "overview", run: (sim) => { sim.alert = null; } },
      { at: 22, tag: "ok", say: "Sans KIZUNA, la fuite aurait continué toute la journée.", cam: "tank" },
    ],
  },
  storm: {
    label: "Orage",
    duration: 22,
    setup: (sim) => {
      sim.hour = 15;
      sim.tank = 35;
    },
    steps: [
      { at: 0, tag: "info", say: "Un orage arrive sur le quartier.", cam: "overview", run: (sim) => { sim.raining = true; } },
      { at: 4, tag: "info", say: "Le toit collecte l'eau de pluie et l'envoie vers la citerne.", cam: "tank", run: (sim) => { sim.collecting = true; sim.tankRate = 2.2; } },
      { at: 12, tag: "ok", say: "La citerne se remplit : cette eau servira au jardin et aux sanitaires.", cam: "room:garden|pool" },
      { at: 18, tag: "ok", say: "Fin de l'orage. Réserve d'eau reconstituée sans toucher au réseau public.", cam: "overview", run: (sim) => { sim.raining = false; sim.collecting = false; sim.tankRate = 0; } },
    ],
  },
  outage: {
    label: "Coupure de courant",
    duration: 26,
    setup: (sim) => {
      sim.hour = 21;
      sim.battery = 86;
      sim.lights = "all";
    },
    steps: [
      { at: 0, tag: "info", say: "21 h : la maison est alimentée par le réseau électrique.", cam: "overview", run: (sim) => { sim.gridHome = true; } },
      { at: 4, tag: "alert", say: "Coupure du réseau électrique dans tout le quartier !", cam: "grid", run: (sim) => { sim.grid = "down"; sim.gridHome = false; sim.lights = "off"; } },
      { at: 7, tag: "info", say: "La batterie prend le relais : seules les charges essentielles restent alimentées.", cam: "battery", run: (sim) => { sim.batteryHome = true; sim.lights = "essential"; sim.batteryRate = -0.9; } },
      { at: 14, tag: "info", say: "Le délestage intelligent coupe les appareils non essentiels pour tenir toute la nuit.", cam: "room:living_room|kitchen" },
      { at: 20, tag: "ok", say: "Retour du réseau. Les habitants n'ont pas été plongés dans le noir.", cam: "overview", run: (sim) => { sim.grid = "ok"; sim.batteryHome = false; sim.gridHome = true; sim.lights = "all"; sim.batteryRate = 0; } },
    ],
  },
  heatwave: {
    label: "Canicule",
    duration: 24,
    setup: (sim) => {
      sim.hour = 13;
      sim.tank = 62;
      sim.heat = true;
    },
    steps: [
      { at: 0, tag: "alert", say: "Canicule : 44 °C à l'ombre sur le quartier.", cam: "overview" },
      { at: 4, tag: "alert", say: "La demande en eau explose : arrosage du jardin et climatisation à fond.", cam: "room:garden|pool", run: (sim) => { sim.gardenWater = true; sim.tankRate = -1.5; sim.lights = "off"; } },
      { at: 10, tag: "info", say: "L'IA KIZUNA décale l'arrosage à la nuit, quand l'eau s'évapore moins.", cam: "tank", run: (sim) => { sim.gardenWater = false; sim.tankRate = -0.15; } },
      { at: 15, tag: "info", say: "Les panneaux solaires couvrent la climatisation : pas de surcharge du réseau.", cam: "solar", run: (sim) => { sim.batteryRate = 0.8; } },
      { at: 20, tag: "ok", say: "Canicule maîtrisée : réserve d'eau protégée et confort maintenu.", cam: "overview" },
    ],
  },
  drought: {
    label: "Sécheresse",
    duration: 24,
    setup: (sim) => {
      sim.hour = 11;
      sim.tank = 24;
      sim.drought = true;
      sim.gardenWater = true;
      sim.tankRate = -0.6;
    },
    steps: [
      { at: 0, tag: "alert", say: "Sécheresse : aucune pluie depuis 40 jours, la végétation jaunit.", cam: "overview" },
      { at: 5, tag: "alert", say: "La citerne passe sous les 20 % : niveau critique.", cam: "tank" },
      { at: 10, tag: "info", say: "Mode économie : l'arrosage est coupé, l'eau est réservée à la maison.", cam: "room:garden|pool", run: (sim) => { sim.gardenWater = false; sim.tankRate = -0.05; } },
      { at: 15, tag: "info", say: "KIZUNA prévient le propriétaire et propose un partage d'eau avec les voisins.", cam: "overview" },
      { at: 20, tag: "ok", say: "La consommation chute : la réserve tient plusieurs jours de plus.", cam: "tank" },
    ],
  },
  day: {
    label: "Crise combinée 24 h",
    duration: 60,
    setup: (sim) => {
      sim.hour = 6;
      sim.tank = 55;
      sim.battery = 40;
      sim.hourSpeed = 0.4;
      sim.lights = "auto";
      sim.autoSolar = true;
    },
    steps: [
      { at: 0, tag: "info", say: "06:00 — Lever du soleil. Une journée de crise en accéléré.", cam: "overview" },
      { at: 6, tag: "info", say: "Le soleil monte : les panneaux alimentent la maison et chargent la batterie.", cam: "solar", run: (sim) => { sim.batteryRate = 0.9; } },
      { at: 16, tag: "info", say: "Orage en début d'après-midi : la citerne récupère l'eau de pluie.", cam: "tank", run: (sim) => { sim.raining = true; sim.collecting = true; sim.tankRate = 1.4; } },
      { at: 22, tag: "info", say: "Fin de l'orage.", cam: "overview", run: (sim) => { sim.raining = false; sim.collecting = false; sim.tankRate = -0.2; } },
      { at: 28, tag: "alert", say: "Fuite détectée dans la salle de bain !", cam: "room:bathroom", run: (sim) => { sim.leak = true; sim.alert = "bathroom"; sim.tankRate = -1.5; } },
      { at: 32, tag: "ok", say: "Vanne fermée automatiquement par l'IA.", cam: "valve", run: (sim) => { sim.leak = false; sim.valveOpen = false; sim.alert = null; sim.tankRate = -0.1; } },
      { at: 38, tag: "alert", say: "La nuit tombe… et le réseau électrique tombe en panne.", cam: "grid", run: (sim) => { sim.grid = "down"; sim.batteryHome = true; sim.lights = "essential"; sim.batteryRate = -0.6; } },
      { at: 48, tag: "ok", say: "Le réseau revient. La batterie a tenu toute la soirée.", cam: "battery", run: (sim) => { sim.grid = "ok"; sim.batteryHome = false; sim.gridHome = true; sim.batteryRate = 0; sim.valveOpen = true; } },
      { at: 55, tag: "ok", say: "Bilan : eau préservée, aucune coupure ressentie. C'est la résilience KIZUNA.", cam: "overview" },
    ],
  },
};

Object.assign(DigitalTwin3D.prototype, {
  setupDemo() {
    if (!document.getElementById("twin3d-demo-css")) {
      const style = document.createElement("style");
      style.id = "twin3d-demo-css";
      style.textContent = DEMO_CSS;
      document.head.appendChild(style);
    }
    const panel = document.createElement("div");
    panel.className = "twin3d-demo";
    const title = document.createElement("div");
    title.className = "twin3d-demo-title";
    title.textContent = "Mode démo";
    panel.appendChild(title);
    this.demoButtons = {};
    const icons = { tour: "🎥", leak: "💧", storm: "🌧️", outage: "⚡", heatwave: "🔥", drought: "🌵", day: "⏱️" };
    Object.entries(SCENARIOS).forEach(([key, scenario]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = `${icons[key]}  ${scenario.label}`;
      button.addEventListener("click", () => this.startDemo(key));
      panel.appendChild(button);
      this.demoButtons[key] = button;
    });
    const stop = document.createElement("button");
    stop.type = "button";
    stop.className = "is-stop";
    stop.textContent = "■  Arrêter";
    stop.hidden = true;
    stop.addEventListener("click", () => this.stopDemo(true));
    panel.appendChild(stop);
    this.demoStop = stop;
    const full = document.createElement("button");
    full.type = "button";
    full.textContent = "⛶  Plein écran";
    full.addEventListener("click", () => {
      if (document.fullscreenElement) {
        document.exitFullscreen();
      } else if (this.stage.requestFullscreen) {
        this.stage.requestFullscreen();
      }
    });
    panel.appendChild(full);
    this.stage.appendChild(panel);

    const banner = document.createElement("div");
    banner.className = "twin3d-banner";
    banner.innerHTML = '<div class="twin3d-banner-box"><span class="twin3d-banner-tag">SIMULATION</span><span class="twin3d-banner-text"></span><div class="twin3d-banner-meta"></div><div class="twin3d-banner-bar"><i></i></div></div>';
    this.stage.appendChild(banner);
    this.banner = banner;
    this.demo = null;
    this.fly = null;
  },

  startDemo(key) {
    if (!this.eq) {
      return;
    }
    if (this.demo) {
      this.stopDemo(false);
    }
    const base = this.base || {};
    const scenario = SCENARIOS[key];
    const sim = {
      hour: 14,
      hourSpeed: 0,
      tank: Number(base.tank && base.tank.percent) || 60,
      tankRate: 0,
      battery: Number(base.battery && base.battery.percent) || 70,
      batteryRate: 0,
      valveOpen: true,
      leak: false,
      raining: false,
      collecting: false,
      grid: "ok",
      gridHome: false,
      batteryHome: false,
      lights: "auto",
      alert: null,
      autoSolar: true,
    };
    scenario.setup(sim);
    this.demo = { key, scenario, sim, t: 0, next: 0, push: 0 };
    this.controls.autoRotate = false;
    Object.entries(this.demoButtons).forEach(([k, b]) => b.classList.toggle("is-on", k === key));
    this.demoStop.hidden = false;
    this.banner.classList.add("is-on");
    this.ensureLeakFx();
    this.pushDemoState();
  },

  stopDemo(restore = true) {
    if (!this.demo) {
      return;
    }
    this.demo = null;
    Object.values(this.demoButtons).forEach((b) => b.classList.remove("is-on"));
    this.demoStop.hidden = true;
    this.banner.classList.remove("is-on");
    if (this.leakFx) {
      this.leakFx.spray.visible = false;
      this.leakFx.puddle.visible = false;
      this.leakFx.alarm.intensity = 0;
    }
    if (restore && this.base) {
      this.update(this.base);
      this.flyTo("overview");
    }
  },

  say(text, tag) {
    const box = this.banner;
    box.querySelector(".twin3d-banner-text").textContent = text;
    const t = box.querySelector(".twin3d-banner-tag");
    t.className = `twin3d-banner-tag${tag === "ok" ? " is-ok" : tag === "info" ? " is-info" : ""}`;
    t.textContent = tag === "alert" ? "ALERTE" : tag === "ok" ? "RÉSOLU" : "SIMULATION";
  },

  findRoom(kinds) {
    const list = kinds.split("|");
    for (const kind of list) {
      const hit = [...this.rects.values()].find((r) => r.room.kind === kind);
      if (hit) {
        return hit;
      }
    }
    return null;
  },

  shotFor(name) {
    const eq = this.eq;
    const c = this.center;
    if (name.startsWith("room:")) {
      const r = this.findRoom(name.slice(5));
      if (r) {
        return { target: new THREE.Vector3(r.cx, 0.4, r.cz), dist: Math.max(r.ws, r.ds) * 1.1 + 5, high: true };
      }
      return this.shotFor("overview");
    }
    const at = {
      tank: eq.tankPos,
      battery: eq.batteryPos,
      solar: eq.solarPos,
      grid: eq.gridPos,
      valve: new THREE.Vector3(eq.tankPos.x - 1.0, 0, eq.tankPos.z),
    }[name];
    if (at) {
      return { target: new THREE.Vector3(at.x, name === "grid" ? 2.5 : 1, at.z), dist: name === "grid" ? 11 : 7 };
    }
    return { target: new THREE.Vector3(c.x, 0.8, c.z), dist: this.span * 1.1 };
  },

  flyTo(name) {
    const shot = this.shotFor(name);
    const d = shot.dist;
    // Room shots look down into the room over the cut-away walls.
    const dir = shot.high ? new THREE.Vector3(0.3, 1.0, 0.55) : new THREE.Vector3(0.5, 0.62, 0.72);
    const to = shot.target.clone().add(dir.multiplyScalar(d));
    this.fly = {
      fromPos: this.camera.position.clone(),
      fromTarget: this.controls.target.clone(),
      toPos: to,
      toTarget: shot.target,
      t: 0,
      dur: 2.2,
    };
  },

  ensureLeakFx() {
    const bath = this.findRoom("bathroom|kitchen");
    if (this.leakFx) {
      this.world.remove(this.leakFx.group);
      disposeTree(this.leakFx.group);
    }
    const group = new THREE.Group();
    const origin = bath ? new THREE.Vector3(bath.cx + bath.ws * 0.1, FLOOR + 0.35, bath.cz + bath.ds * 0.1)
      : this.center.clone().setY(FLOOR + 0.35);
    const count = 700;
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i += 1) {
      pos.set([origin.x, origin.y - 60, origin.z], i * 3);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const sprayMat = new THREE.PointsMaterial({ color: "#7fd3ff", size: 0.14, transparent: true, opacity: 0.9, depthWrite: false });
    sprayMat.userData.own = true;
    const spray = new THREE.Points(geo, sprayMat);
    spray.frustumCulled = false;
    spray.visible = false;
    group.add(spray);
    const puddleMat = materials().water.clone();
    puddleMat.userData.own = true;
    puddleMat.opacity = 0.7;
    const puddle = new THREE.Mesh(new THREE.CircleGeometry(1, 40), puddleMat);
    puddle.rotation.x = -Math.PI / 2;
    puddle.position.set(origin.x, FLOOR + 0.006, origin.z);
    puddle.scale.setScalar(0.01);
    puddle.visible = false;
    group.add(puddle);
    const alarm = new THREE.PointLight("#ff2d20", 0, 7, 2);
    alarm.position.set(bath ? bath.cx : origin.x, FLOOR + 2.0, bath ? bath.cz : origin.z);
    group.add(alarm);
    this.world.add(group);
    const particles = [];
    for (let i = 0; i < count; i += 1) {
      particles.push({ p: new THREE.Vector3().copy(origin), v: new THREE.Vector3(), life: Math.random() });
    }
    this.leakFx = { group, spray, puddle, alarm, origin, particles, maxR: bath ? Math.min(bath.ws, bath.ds) * 0.3 : 1.2 };
  },

  simToState() {
    const sim = this.demo.sim;
    const base = this.base || {};
    const night = NIGHT(sim.hour);
    const rooms = (base.rooms || []).map((room) => {
      let on = false;
      if (sim.lights === "all") {
        on = true;
      } else if (sim.lights === "auto") {
        on = night;
      } else if (sim.lights === "essential") {
        on = room.kind === "living_room" || room.kind === "kitchen";
      }
      if (!INDOOR.has(room.kind)) {
        on = false;
      }
      return { ...room, lights_on: on };
    });
    const sun = daylight(sim.hour) * (sim.raining ? 0.35 : 1);
    const watts = Math.round(2400 * sun);
    const flows = [];
    const add = (id) => flows.push({ id, active: true });
    if (watts > 150) {
      add("solar_home");
      if (sim.battery < 99) {
        add("solar_battery");
      }
    }
    if (sim.leak && sim.valveOpen) {
      add("water_bathroom");
    }
    if (sim.raining) {
      add("rain_roof");
    }
    if (sim.gardenWater) {
      add("water_garden");
    }
    if (sim.collecting) {
      add("roof_tank");
    }
    if (sim.grid !== "down" && (sim.gridHome || (night && watts <= 150))) {
      add("grid_home");
    }
    if (sim.batteryHome) {
      add("battery_home");
    }
    const alertRooms = [];
    if (sim.alert) {
      const r = this.findRoom(sim.alert);
      if (r) {
        alertRooms.push(String(r.room.id));
      }
    }
    const cap = (base.tank && base.tank.capacity_liters) || 2000;
    const charging = sim.batteryRate > 0 || (watts > 150 && !sim.batteryHome);
    return {
      ...base,
      rooms,
      tank: { ...(base.tank || {}), percent: Math.round(sim.tank), liters: (sim.tank / 100) * cap, capacity_liters: cap },
      battery: { percent: Math.round(sim.battery), state: sim.batteryHome ? "discharging" : charging ? "charging" : "idle" },
      solar: { watts, allocation: "essential" },
      valve: { open: sim.valveOpen },
      pump: { running: Boolean(base.pump && base.pump.running) },
      weather: { raining: sim.raining, collecting: sim.collecting, heat: sim.heat, drought: sim.drought },
      flows,
      grid: sim.grid,
      alertRooms,
      clockHour: sim.hour,
    };
  },

  pushDemoState() {
    const state = this.simToState();
    this.update(state);
    const sim = this.demo.sim;
    const meta = this.banner.querySelector(".twin3d-banner-meta");
    meta.textContent = "";
    [
      `🕒 ${fmtHour(sim.hour)}`,
      `💧 Citerne ${Math.round(sim.tank)} %`,
      `🔋 Batterie ${Math.round(sim.battery)} %`,
      `☀️ ${state.solar.watts} W`,
      sim.valveOpen ? "Vanne ouverte" : "Vanne fermée",
    ].forEach((text) => {
      const span = document.createElement("span");
      span.textContent = text;
      meta.appendChild(span);
    });
    this.banner.querySelector(".twin3d-banner-bar > i").style.width = `${Math.min(100, (this.demo.t / this.demo.scenario.duration) * 100)}%`;
  },

  demoFrame(dt, time) {
    if (this.fly) {
      const f = this.fly;
      f.t = Math.min(1, f.t + dt / f.dur);
      const e = f.t < 0.5 ? 4 * f.t ** 3 : 1 - (-2 * f.t + 2) ** 3 / 2;
      this.camera.position.lerpVectors(f.fromPos, f.toPos, e);
      this.controls.target.lerpVectors(f.fromTarget, f.toTarget, e);
      if (f.t >= 1) {
        this.fly = null;
      }
    }
    const demo = this.demo;
    if (!demo) {
      return;
    }
    demo.t += dt;
    const sim = demo.sim;
    const steps = demo.scenario.steps;
    while (demo.next < steps.length && steps[demo.next].at <= demo.t) {
      const step = steps[demo.next];
      if (step.run) {
        step.run(sim);
      }
      if (step.say) {
        this.say(step.say, step.tag);
      }
      if (step.cam) {
        this.flyTo(step.cam);
      }
      demo.next += 1;
    }
    sim.hour += sim.hourSpeed * dt;
    sim.tank = THREE.MathUtils.clamp(sim.tank + sim.tankRate * dt, 2, 100);
    sim.battery = THREE.MathUtils.clamp(sim.battery + sim.batteryRate * dt, 3, 100);

    const fx = this.leakFx;
    if (fx) {
      const leaking = sim.leak && sim.valveOpen;
      fx.spray.visible = leaking || fx.particles.some((p) => p.p.y > FLOOR + 0.02 && p.active);
      if (sim.leak || sim.alert) {
        fx.puddle.visible = true;
      }
      if (leaking) {
        const s = Math.min(fx.maxR, fx.puddle.scale.x + dt * 0.4);
        fx.puddle.scale.setScalar(Math.max(0.05, s));
      }
      const attr = fx.spray.geometry.attributes.position;
      fx.particles.forEach((p, i) => {
        p.life -= dt;
        if (p.life <= 0 || p.p.y < FLOOR) {
          if (leaking) {
            p.p.copy(fx.origin);
            const a = Math.random() * Math.PI * 2;
            p.v.set(Math.cos(a) * (0.4 + Math.random() * 0.8), 1.6 + Math.random() * 1.6, Math.sin(a) * (0.4 + Math.random() * 0.8));
            p.life = 0.6 + Math.random() * 0.8;
            p.active = true;
          } else {
            p.active = false;
            p.p.set(0, -50, 0);
          }
        } else {
          p.v.y -= 9.8 * dt;
          p.p.addScaledVector(p.v, dt);
        }
        attr.setXYZ(i, p.p.x, p.p.y, p.p.z);
      });
      attr.needsUpdate = true;
      fx.alarm.intensity = sim.alert ? 6 + Math.sin(time * 8) * 5 : 0;
    }

    demo.push += dt;
    if (demo.push > 0.15) {
      demo.push = 0;
      this.pushDemoState();
    }
    if (demo.t >= demo.scenario.duration) {
      this.stopDemo(true);
    }
  },
});

// Shared with the 3D house builder (builder3d.js): same materials, walls and furniture.
export { H, T, FLOOR, materials, box, rbox, cyl, mesh, wallSegment, furnish, tree, bush, outdoor, skyTexture };
