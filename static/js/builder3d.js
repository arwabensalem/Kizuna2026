/**
 * Build your house in 3D, like a game.
 *
 * Pick a room in the palette, then click on the plot to place it. Rooms snap
 * to a grid and cannot overlap. The counters (surface, bedrooms, bathrooms)
 * and the spaces (kitchen, living room, garden, pool, garage) are computed
 * from what you build, and written into the existing form fields, so the
 * server keeps receiving the same form. The classic fields stay available
 * under "Remplir à la main".
 */

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { GTAOPass } from "three/addons/postprocessing/GTAOPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import * as T3 from "./twin3d.js?v=demo2";

const CELL = 2; // metres per grid cell
const COLS = 12;
const ROWS = 9;

const KINDS = {
  bedroom: { label: "Chambre", icon: "🛏️", w: 2, d: 2, floor: "#c79a6b", indoor: true },
  bathroom: { label: "Salle de bain", icon: "🛁", w: 2, d: 1, floor: "#d9e6ea", indoor: true },
  kitchen: { label: "Cuisine", icon: "🍳", w: 2, d: 2, floor: "#e3d6c3", indoor: true },
  living_room: { label: "Salon", icon: "🛋️", w: 3, d: 2, floor: "#b98a5e", indoor: true },
  garage: { label: "Garage", icon: "🚗", w: 3, d: 2, floor: "#a9a9a4", indoor: true },
  garden: { label: "Jardin", icon: "🌳", w: 3, d: 3, floor: "#6f9a46", indoor: false },
  pool: { label: "Piscine", icon: "🏊", w: 2, d: 3, floor: "#e8e4dc", indoor: false },
  solar: { label: "Panneaux solaires", icon: "☀️", w: 2, d: 1, floor: "#cfd3d6", indoor: false, bonus: true },
  tank: { label: "Citerne", icon: "💧", w: 1, d: 1, floor: "#cfd3d6", indoor: false, bonus: true },
};

const CSS = `
.hb-wrap{position:relative;margin:1rem 0 1.5rem;border-radius:18px;overflow:hidden;background:linear-gradient(#cfe6f5,#eef5ee);border:1px solid rgba(22,48,42,.15);box-shadow:0 8px 30px rgba(22,48,42,.08);user-select:none}
.hb-wrap canvas{display:block;width:100%;height:clamp(380px,56vw,560px);touch-action:none}
.hb-palette{position:absolute;top:12px;left:12px;display:grid;grid-template-columns:repeat(3,1fr);gap:6px;max-width:300px;z-index:2}
.hb-palette button,.hb-tools button{all:unset;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:2px;padding:8px 6px;border-radius:12px;background:rgba(255,255,255,.92);box-shadow:0 2px 8px rgba(0,0,0,.12);font:600 11px/1.15 system-ui,-apple-system,"Segoe UI",sans-serif;color:#16302a;text-align:center;transition:transform .12s,box-shadow .12s,background .12s}
.hb-palette button span{font-size:22px;line-height:1}
.hb-palette button:hover,.hb-tools button:hover{transform:translateY(-2px);box-shadow:0 6px 14px rgba(0,0,0,.16)}
.hb-palette button.is-on,.hb-tools button.is-on{background:#0f6e6e;color:#fff;outline:2px solid #9be3d3}
.hb-palette button.is-bonus{background:rgba(255,248,225,.95)}
.hb-tools{position:absolute;bottom:12px;left:12px;display:flex;gap:6px;z-index:2;flex-wrap:wrap}
.hb-tools button{flex-direction:row;padding:8px 12px;font-size:13px}
.hb-hud{position:absolute;top:12px;right:12px;z-index:2;background:rgba(22,48,42,.88);color:#f4efe6;border-radius:14px;padding:12px 14px;min-width:210px;font:500 13px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif;box-shadow:0 6px 20px rgba(0,0,0,.2)}
.hb-hud b{font-size:22px;color:#9be3d3}
.hb-hud .hb-row{display:flex;justify-content:space-between;gap:12px}
.hb-hud .hb-missions{margin:8px 0 0;padding:8px 0 0;border-top:1px solid rgba(255,255,255,.15);list-style:none}
.hb-hud .hb-missions li{opacity:.75}
.hb-hud .hb-missions li.is-done{opacity:1;color:#9be3d3}
.hb-stars{font-size:18px;letter-spacing:2px}
.hb-toast{position:absolute;left:50%;bottom:64px;transform:translate(-50%,20px);opacity:0;z-index:3;background:#fff;color:#16302a;border-radius:999px;padding:8px 16px;font:700 14px/1.2 system-ui,sans-serif;box-shadow:0 8px 24px rgba(0,0,0,.18);transition:opacity .25s,transform .25s;pointer-events:none;white-space:nowrap}
.hb-toast.is-on{opacity:1;transform:translate(-50%,0)}
.hb-help{position:absolute;bottom:12px;right:12px;z-index:2;background:rgba(255,255,255,.88);border-radius:10px;padding:6px 10px;font:500 12px/1.3 system-ui,sans-serif;color:#16302a;max-width:260px}
.hb-manual{margin-top:1rem;border:1px dashed rgba(22,48,42,.25);border-radius:14px;padding:.5rem 1rem}
.hb-manual>summary{cursor:pointer;font-weight:700;color:#0f6e6e;padding:.4rem 0}
@media (max-width:720px){.hb-palette{grid-template-columns:repeat(5,1fr);max-width:none;right:12px}.hb-hud{top:auto;bottom:60px;right:12px;min-width:0}.hb-help{display:none}}
`;

const FLOOR_OF = {
  bathroom: ["tile", 0.36],
  kitchen: ["kitchenTile", 0.5],
  garage: ["concrete", 0.3],
};

// Realistic room, built with the same pieces as the 3D twin:
// textured floor, thick plaster walls with glazed windows, a door, and furniture.
function roomMesh(kind, w, d) {
  const spec = KINDS[kind];
  const W = w * CELL;
  const D = d * CELL;
  const m = T3.materials();
  const g = new THREE.Group();
  const room = { id: `b-${kind}`, kind };
  if (spec.indoor) {
    const [matName, scale] = FLOOR_OF[kind] || ["wood", 0.3];
    g.add(T3.box(W, T3.FLOOR, D, m[matName], 0, 0, 0, scale));
    const glass = () => m.glass;
    const win = kind === "bathroom" ? "smallWindow" : kind === "garage" ? null : "window";
    const front = kind === "garage" ? "garage" : kind === "living_room" ? "entrance" : "door";
    const a = { x: -W / 2, z: -D / 2 };
    const b = { x: W / 2, z: -D / 2 };
    const c = { x: W / 2, z: D / 2 };
    const e = { x: -W / 2, z: D / 2 };
    g.add(T3.wallSegment(a, b, win, room, glass));
    g.add(T3.wallSegment(a, e, D >= 3.5 ? win : null, room, glass));
    g.add(T3.wallSegment(b, c, D >= 3.5 ? win : null, room, glass));
    g.add(T3.wallSegment(e, c, front, room, glass));
    [a, b, c, e].forEach((p) => g.add(T3.box(T3.T, T3.H, T3.T, m.wall, p.x, T3.FLOOR, p.z, 0.5)));
    const f = T3.furnish(room, W, D);
    f.position.y = T3.FLOOR;
    g.add(f);
  } else if (kind === "garden" || kind === "pool") {
    g.add(T3.outdoor(room, 0, 0, W, D));
  } else if (kind === "solar") {
    g.add(T3.box(W - 0.1, 0.06, D - 0.1, m.concrete, 0, 0, 0, 0.4));
    for (let i = 0; i < 2; i += 1) {
      const panel = new THREE.Group();
      panel.add(T3.box(1.6, 0.04, 1.0, m.solar, 0, 0, 0));
      panel.add(T3.box(1.64, 0.05, 0.03, m.alu, 0, -0.005, -0.5));
      panel.add(T3.box(1.64, 0.05, 0.03, m.alu, 0, -0.005, 0.5));
      panel.rotation.x = 0.45;
      panel.position.set(-0.95 + i * 1.9, 0.75, 0);
      g.add(panel);
      g.add(T3.cyl(0.03, 0.55, m.alu, -0.95 + i * 1.9, 0, 0.4, 10));
      g.add(T3.cyl(0.03, 1.0, m.alu, -0.95 + i * 1.9, 0, -0.4, 10));
    }
  } else if (kind === "tank") {
    g.add(T3.cyl(0.85, 0.12, m.concrete, 0, 0, 0));
    const shell = T3.mesh(new THREE.CylinderGeometry(0.78, 0.78, 1.9, 40, 1, true).translate(0, 1.07, 0), m.tankShell, false);
    g.add(shell);
    g.add(T3.cyl(0.8, 0.05, m.steel, 0, 2.02, 0, 40));
    g.add(T3.mesh(new THREE.CylinderGeometry(0.75, 0.75, 1.2, 40).translate(0, 0.74, 0), m.tankWater, false));
  }
  return g;
}

class HouseBuilder {
  constructor(form) {
    this.form = form;
    this.rooms = [];
    this.tool = "bedroom";
    this.rot = false;
    this.history = [];
    this.makeDom();
    this.makeScene();
    this.loadFromForm();
    this.sync(false);
    this.renderer.setAnimationLoop(() => this.frame());
  }

  field(name) {
    return this.form.querySelector(`[name="${name}"]`);
  }

  makeDom() {
    const style = document.createElement("style");
    style.textContent = CSS;
    document.head.appendChild(style);
    const wrap = document.createElement("section");
    wrap.className = "hb-wrap";
    wrap.setAttribute("aria-label", "Construire ma maison en 3D");
    this.wrap = wrap;

    const palette = document.createElement("div");
    palette.className = "hb-palette";
    this.buttons = {};
    Object.entries(KINDS).forEach(([kind, spec]) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = spec.bonus ? "is-bonus" : "";
      b.innerHTML = `<span>${spec.icon}</span>${spec.label}`;
      b.title = spec.bonus ? "Décoration bonus" : `Ajouter : ${spec.label}`;
      b.addEventListener("click", () => this.setTool(kind));
      palette.appendChild(b);
      this.buttons[kind] = b;
    });
    wrap.appendChild(palette);

    const tools = document.createElement("div");
    tools.className = "hb-tools";
    const mk = (label, fn, key) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = label;
      b.addEventListener("click", fn);
      tools.appendChild(b);
      if (key) {
        this.buttons[key] = b;
      }
      return b;
    };
    mk("🔄 Tourner", () => this.rotate());
    mk("🧽 Gomme", () => this.setTool("erase"), "erase");
    mk("↩️ Annuler", () => this.undo());
    mk("🗑️ Tout effacer", () => this.clear());
    wrap.appendChild(tools);

    this.hud = document.createElement("div");
    this.hud.className = "hb-hud";
    wrap.appendChild(this.hud);

    this.toastEl = document.createElement("div");
    this.toastEl.className = "hb-toast";
    wrap.appendChild(this.toastEl);

    const help = document.createElement("div");
    help.className = "hb-help";
    help.textContent = "Choisissez une pièce, puis cliquez sur le terrain pour la poser. Clic droit pour tourner la vue, molette pour zoomer.";
    wrap.appendChild(help);

    // Classic fields stay, folded away under "Remplir à la main".
    const manual = document.createElement("details");
    manual.className = "hb-manual";
    manual.innerHTML = "<summary>Remplir à la main (facultatif)</summary>";
    ["area_m2", "bedrooms", "bathrooms"].forEach((name) => {
      const input = this.field(name);
      const col = input && input.closest("[class*='col-']");
      if (col) {
        manual.appendChild(col);
      }
    });
    const spaces = this.form.querySelector("fieldset");
    if (spaces) {
      manual.appendChild(spaces);
    }
    const anchor = this.form.querySelector(".row.g-3");
    anchor.after(wrap);
    wrap.after(manual);
  }

  makeScene() {
    const canvas = document.createElement("canvas");
    this.wrap.prepend(canvas);
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.9;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer = renderer;

    const scene = new THREE.Scene();
    scene.background = T3.skyTexture("#5d9bd6", "#e9f0ee");
    scene.fog = new THREE.Fog("#e9f0ee", 70, 160);
    scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environmentIntensity = 0.5;
    this.scene = scene;

    const sun = new THREE.DirectionalLight("#fff4e2", 2.5);
    sun.position.set(-14, 24, 16);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    Object.assign(sun.shadow.camera, { left: -20, right: 20, top: 20, bottom: -20, near: 1, far: 80 });
    sun.shadow.camera.updateProjectionMatrix();
    sun.shadow.bias = -0.0003;
    sun.shadow.normalBias = 0.03;
    sun.shadow.radius = 4;
    scene.add(sun, new THREE.HemisphereLight("#dff1ff", "#6b7a4a", 0.5));

    const m = T3.materials();
    scene.add(T3.box(240, 0.1, 240, m.grass, 0, -0.12, 0, 0.25));
    const plot = T3.box(COLS * CELL + 0.6, 0.04, ROWS * CELL + 0.6, m.paving, 0, -0.04, 0, 0.45);
    plot.castShadow = false;
    scene.add(plot);
    this.plot = plot;
    const grid = new THREE.GridHelper(Math.max(COLS, ROWS) * CELL, Math.max(COLS, ROWS), "#8f8676", "#a39a89");
    grid.material.transparent = true;
    grid.material.opacity = 0.35;
    grid.scale.set(COLS / Math.max(COLS, ROWS), 1, ROWS / Math.max(COLS, ROWS));
    grid.position.y = 0.005;
    scene.add(grid);

    this.camera = new THREE.PerspectiveCamera(38, 16 / 9, 0.1, 300);
    this.camera.position.set(5, 26, 17);
    const controls = new OrbitControls(this.camera, canvas);
    controls.target.set(0, 0, 0);
    controls.enableDamping = true;
    controls.maxPolarAngle = 1.25;
    controls.minDistance = 8;
    controls.maxDistance = 60;
    controls.mouseButtons = { LEFT: null, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.ROTATE };
    controls.touches = { ONE: null, TWO: THREE.TOUCH.DOLLY_ROTATE };
    this.controls = controls;

    this.ghost = new THREE.Mesh(
      new THREE.BoxGeometry(1, 0.3, 1),
      new THREE.MeshBasicMaterial({ color: "#2fbf71", transparent: true, opacity: 0.45, depthWrite: false }),
    );
    this.ghost.visible = false;
    scene.add(this.ghost);

    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    canvas.addEventListener("pointermove", (e) => this.onMove(e));
    canvas.addEventListener("pointerleave", () => {
      this.ghost.visible = false;
    });
    canvas.addEventListener("pointerdown", (e) => {
      if (e.button === 0) {
        this.down = { x: e.clientX, y: e.clientY };
      }
    });
    canvas.addEventListener("pointerup", (e) => {
      if (e.button === 0 && this.down && Math.hypot(e.clientX - this.down.x, e.clientY - this.down.y) < 6) {
        this.onMove(e);
        this.onClick();
      }
      this.down = null;
    });
    canvas.addEventListener("contextmenu", (e) => e.preventDefault());
    window.addEventListener("keydown", (e) => {
      if (e.target.closest && e.target.closest("input,textarea,select")) {
        return;
      }
      if (e.key === "r" || e.key === "R") {
        this.rotate();
      }
    });
    const size = { w: canvas.clientWidth || 800, h: canvas.clientHeight || 480 };
    const rt = new THREE.WebGLRenderTarget(size.w, size.h, { type: THREE.HalfFloatType, samples: 4 });
    this.composer = new EffectComposer(renderer, rt);
    this.composer.addPass(new RenderPass(scene, this.camera));
    const gtao = new GTAOPass(scene, this.camera, size.w, size.h);
    gtao.updateGtaoMaterial({ radius: 0.5, distanceExponent: 1.5, thickness: 1, scale: 1.2, samples: 16 });
    gtao.blendIntensity = 0.9;
    this.composer.addPass(gtao);
    this.composer.addPass(new OutputPass());
    this.clock = new THREE.Clock();
    new ResizeObserver(() => this.resize()).observe(canvas);
    this.resize();
    this.setTool("bedroom");
  }

  resize() {
    const c = this.renderer.domElement;
    const w = c.clientWidth || 800;
    const h = c.clientHeight || 480;
    this.renderer.setSize(w, h, false);
    if (this.composer) {
      this.composer.setSize(w, h);
      this.composer.setPixelRatio(this.renderer.getPixelRatio());
    }
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  setTool(kind) {
    this.tool = kind;
    Object.entries(this.buttons).forEach(([k, b]) => b.classList.toggle("is-on", k === kind));
    this.updateGhost();
  }

  rotate() {
    this.rot = !this.rot;
    this.updateGhost();
  }

  size(kind, rot) {
    const s = KINDS[kind];
    return rot ? { w: s.d, d: s.w } : { w: s.w, d: s.d };
  }

  cellAt(e) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.pointer.set(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1);
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const hit = this.raycaster.intersectObject(this.plot)[0];
    if (!hit) {
      return null;
    }
    return {
      x: Math.floor(hit.point.x / CELL + COLS / 2),
      z: Math.floor(hit.point.z / CELL + ROWS / 2),
    };
  }

  onMove(e) {
    this.hover = this.cellAt(e);
    this.updateGhost();
  }

  roomAt(x, z) {
    return this.rooms.find((r) => x >= r.x && x < r.x + r.w && z >= r.z && z < r.z + r.d);
  }

  fits(x, z, w, d) {
    if (x < 0 || z < 0 || x + w > COLS || z + d > ROWS) {
      return false;
    }
    for (let i = 0; i < w; i += 1) {
      for (let j = 0; j < d; j += 1) {
        if (this.roomAt(x + i, z + j)) {
          return false;
        }
      }
    }
    return true;
  }

  anchor(w, d) {
    // Centre the footprint on the cell under the pointer.
    return { x: this.hover.x - Math.floor((w - 1) / 2), z: this.hover.z - Math.floor((d - 1) / 2) };
  }

  updateGhost() {
    const g = this.ghost;
    if (!this.hover) {
      g.visible = false;
      return;
    }
    if (this.tool === "erase") {
      const r = this.roomAt(this.hover.x, this.hover.z);
      g.visible = Boolean(r);
      if (r) {
        g.scale.set(r.w * CELL, 1, r.d * CELL);
        g.position.set((r.x + r.w / 2 - COLS / 2) * CELL, 0.2, (r.z + r.d / 2 - ROWS / 2) * CELL);
        g.material.color.set("#e5483b");
      }
      return;
    }
    const { w, d } = this.size(this.tool, this.rot);
    const { x, z } = this.anchor(w, d);
    g.visible = true;
    g.scale.set(w * CELL, 1, d * CELL);
    g.position.set((x + w / 2 - COLS / 2) * CELL, 0.2, (z + d / 2 - ROWS / 2) * CELL);
    g.material.color.set(this.fits(x, z, w, d) ? "#2fbf71" : "#e5483b");
  }

  onClick() {
    if (!this.hover) {
      return;
    }
    if (this.tool === "erase") {
      const r = this.roomAt(this.hover.x, this.hover.z);
      if (r) {
        this.remove(r, true);
        this.toast(`${KINDS[r.kind].icon} ${KINDS[r.kind].label} retirée`);
      }
      return;
    }
    const { w, d } = this.size(this.tool, this.rot);
    const { x, z } = this.anchor(w, d);
    if (!this.fits(x, z, w, d)) {
      this.toast("Pas assez de place ici : essayez ailleurs ou tournez la pièce 🔄");
      return;
    }
    this.add(this.tool, x, z, this.rot, true);
  }

  add(kind, x, z, rot, play) {
    const { w, d } = this.size(kind, rot);
    const mesh = roomMesh(kind, w, d);
    mesh.position.set((x + w / 2 - COLS / 2) * CELL, 0, (z + d / 2 - ROWS / 2) * CELL);
    const room = { kind, x, z, w, d, rot, mesh, born: play ? this.clock.elapsedTime : -10 };
    this.scene.add(mesh);
    this.rooms.push(room);
    if (play) {
      this.history.push({ type: "add", room });
      this.celebrate(kind);
      this.sync(true);
    }
    this.updateGhost();
    return room;
  }

  remove(room, record) {
    this.scene.remove(room.mesh);
    this.rooms = this.rooms.filter((r) => r !== room);
    if (record) {
      this.history.push({ type: "remove", room });
      this.sync(true);
    }
    this.updateGhost();
  }

  undo() {
    const last = this.history.pop();
    if (!last) {
      this.toast("Rien à annuler");
      return;
    }
    if (last.type === "add") {
      this.remove(last.room, false);
    } else if (last.type === "remove") {
      this.scene.add(last.room.mesh);
      this.rooms.push(last.room);
    } else if (last.type === "clear") {
      last.rooms.forEach((r) => {
        this.scene.add(r.mesh);
        this.rooms.push(r);
      });
    }
    this.sync(true);
  }

  clear() {
    if (!this.rooms.length) {
      return;
    }
    const all = this.rooms.slice();
    all.forEach((r) => this.scene.remove(r.mesh));
    this.rooms = [];
    this.history.push({ type: "clear", rooms: all });
    this.sync(true);
    this.toast("Terrain vide : à vous de construire !");
  }

  count(kind) {
    return this.rooms.filter((r) => r.kind === kind).length;
  }

  celebrate(kind) {
    const n = this.count(kind);
    const spec = KINDS[kind];
    const msgs = {
      bedroom: n === 1 ? "Première chambre posée ! 🎉" : `${n} chambres, la famille s'agrandit !`,
      bathroom: n === 1 ? "Salle de bain installée 🚿" : `${n} salles de bain, le grand luxe !`,
      kitchen: "Cuisine prête, à table ! 🍽️",
      living_room: "Salon installé, place à la détente 🛋️",
      garage: "Garage construit, la voiture est rangée 🚗",
      garden: "Un jardin ! Les plantes vous disent merci 🌱",
      pool: "Piscine ! Attention à la consommation d'eau 💧",
      solar: "Panneaux solaires : énergie gratuite ☀️",
      tank: "Citerne posée : vous récupérerez l'eau de pluie 💧",
    };
    this.toast(msgs[kind] || `${spec.icon} ${spec.label} ajoutée`);
  }

  toast(text) {
    this.toastEl.textContent = text;
    this.toastEl.classList.add("is-on");
    clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => this.toastEl.classList.remove("is-on"), 2200);
  }

  loadFromForm() {
    const num = (name) => parseInt((this.field(name) || {}).value, 10) || 0;
    const on = (name) => Boolean(this.field(name) && this.field(name).checked);
    const wanted = [];
    if (on("has_living_room")) wanted.push("living_room");
    if (on("has_kitchen")) wanted.push("kitchen");
    for (let i = 0; i < num("bedrooms"); i += 1) wanted.push("bedroom");
    for (let i = 0; i < num("bathrooms"); i += 1) wanted.push("bathroom");
    if (on("has_garage")) wanted.push("garage");
    if (on("has_garden")) wanted.push("garden");
    if (on("has_pool")) wanted.push("pool");
    // Place each room at the first free spot, scanning row by row from the back.
    wanted.forEach((kind) => {
      for (const rot of [false, true]) {
        const { w, d } = this.size(kind, rot);
        for (let z = 1; z <= ROWS - d; z += 1) {
          for (let x = 1; x <= COLS - w; x += 1) {
            if (this.fits(x, z, w, d)) {
              this.add(kind, x, z, rot, false);
              return;
            }
          }
        }
      }
    });
  }

  sync(write) {
    const indoor = this.rooms.filter((r) => KINDS[r.kind].indoor);
    const area = indoor.reduce((sum, r) => sum + r.w * r.d * CELL * CELL, 0);
    const bedrooms = this.count("bedroom");
    const bathrooms = this.count("bathroom");
    const has = (k) => this.count(k) > 0;
    if (write) {
      const set = (name, value) => {
        const input = this.field(name);
        if (!input) {
          return;
        }
        if (input.type === "checkbox") {
          input.checked = value;
        } else {
          input.value = value;
        }
        input.dispatchEvent(new Event("change", { bubbles: true }));
      };
      if (area > 0) {
        set("area_m2", area);
      }
      set("bedrooms", bedrooms);
      set("bathrooms", bathrooms);
      set("has_kitchen", has("kitchen"));
      set("has_living_room", has("living_room"));
      set("has_garden", has("garden"));
      set("has_pool", has("pool"));
      set("has_garage", has("garage"));
    }
    const missions = [
      ["Poser une chambre", bedrooms > 0],
      ["Ajouter une salle de bain", bathrooms > 0],
      ["Installer une cuisine", has("kitchen")],
      ["Créer un salon", has("living_room")],
      ["Bonus : panneaux solaires ou citerne", has("solar") || has("tank")],
    ];
    const done = missions.filter((m) => m[1]).length;
    const stars = "★".repeat(done) + "☆".repeat(missions.length - done);
    this.hud.innerHTML = `
      <div class="hb-row"><span>Surface</span><span><b>${area}</b> m²</span></div>
      <div class="hb-row"><span>Chambres</span><span><b>${bedrooms}</b></span></div>
      <div class="hb-row"><span>Salles de bain</span><span><b>${bathrooms}</b></span></div>
      <div class="hb-row"><span>Niveau</span><span class="hb-stars">${stars}</span></div>
      <ul class="hb-missions">${missions.map(([t, ok]) => `<li class="${ok ? "is-done" : ""}">${ok ? "✅" : "⬜"} ${t}</li>`).join("")}</ul>`;
  }

  frame() {
    const t = this.clock.getElapsedTime();
    this.rooms.forEach((r) => {
      const k = Math.min(1, (t - r.born) / 0.45);
      // Ease-out-back pop when a room lands.
      const s = k >= 1 ? 1 : 1 + 2.2 * (k - 1) ** 3 + 1.2 * (k - 1) ** 2;
      r.mesh.scale.setScalar(Math.max(0.01, s));
    });
    this.ghost.material.opacity = 0.35 + Math.sin(t * 5) * 0.1;
    this.controls.update();
    this.composer.render();
  }
}

function boot() {
  const form = document.querySelector("form.home-form");
  if (!form || !form.querySelector("[name='bedrooms']")) {
    return;
  }
  if (!document.createElement("canvas").getContext("webgl2")) {
    return;
  }
  try {
    new HouseBuilder(form);
  } catch (error) {
    console.warn("KIZUNA: le constructeur 3D n'a pas pu démarrer.", error);
  }
}

boot();
