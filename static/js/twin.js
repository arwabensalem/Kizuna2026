/**
 * Floor plan for one KIZUNA home.
 *
 * Each room is a cell on the plan. Position is layout.
 * Tank, battery, solar, and the valve follow /api/twin/homes/<id>/.
 */

import { COLS, layout } from "./twin-layout.js";

const FILL = {
  bedroom: "#e7d7c4",
  bathroom: "#d5e6e6",
  kitchen: "#f0e0c4",
  living_room: "#f4efe6",
  garden: "#d7e6d4",
  pool: "#d4e6f0",
  garage: "#e4e2dc",
  other: "#efeae2",
};

const FLOW_LABELS = {
  solar_home: "Solaire → Maison",
  solar_battery: "Solaire → Batterie",
  battery_pump: "Batterie → Pompe",
  water_bathroom: "Eau → Salle de bain",
  water_garden: "Eau → Jardin",
  rain_roof: "Pluie → Toit",
  roof_tank: "Toit → Citerne",
};

const CELL_W = 180;
const CELL_H = 128;
const GAP = 0;
const ROOF = 52;
const PAD = 18;

export class DigitalTwin {
  constructor(stage) {
    this.stage = stage;
    this.svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    this.svg.setAttribute("class", "floor-plan");
    this.svg.setAttribute("role", "img");
    this.svg.setAttribute("aria-label", "Floor plan of this home");
    stage.replaceChildren(this.svg);
  }

  setState(state) {
    const plan = layout(state.rooms || []);
    const width = PAD * 2 + COLS * CELL_W + (COLS - 1) * GAP;
    const height = PAD * 2 + ROOF + plan.rows * CELL_H + Math.max(0, plan.rows - 1) * GAP + 8;
    this.svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    this.svg.replaceChildren();
    drawRoof(this.svg, state, width);
    const appliances = groupAppliances(state.appliances || []);
    plan.placed.forEach((room) => {
      drawRoom(this.svg, room, appliances.get(String(room.id)) || [], state);
    });
  }
}

function drawRoof(svg, state, width) {
  const raining = Boolean(state.weather && state.weather.raining);
  const solar = state.solar ? state.solar.watts : 0;
  const battery = state.battery ? state.battery.percent : 0;
  const tank = state.tank ? state.tank.percent : 0;
  const valve = state.valve && state.valve.open ? "Valve open" : "Valve closed";
  rect(svg, PAD, PAD, width - PAD * 2, ROOF - 8, raining ? "#d5e6e6" : "#16302a");
  const bits = [
    `Solar ${solar} W`,
    `Battery ${battery}%`,
    `Tank ${tank}%`,
    valve,
  ];
  if (raining) {
    bits.push("Rain");
  }
  text(svg, PAD + 16, PAD + 28, bits.join("   ·   "), raining ? "#16302a" : "#f4efe6", 15);
}

function drawRoom(svg, room, appliances, state) {
  const x = PAD + room.x * (CELL_W + GAP);
  const y = PAD + ROOF + room.y * (CELL_H + GAP);
  const w = room.w * CELL_W + (room.w - 1) * GAP;
  const h = room.h * CELL_H + (room.h - 1) * GAP;
  const wet = room.kind === "bathroom" || room.kind === "garden" || room.kind === "pool";
  const closed = wet && state.valve && state.valve.open === false;
  rect(svg, x, y, w, h, FILL[room.kind] || FILL.other, closed ? "#c23b2e" : "#16302a");
  text(svg, x + 14, y + 28, room.name, "#16302a", 18);
  const kind = labelFor(room.kind);
  if (kind.toLowerCase() !== String(room.name).toLowerCase()) {
    text(svg, x + 14, y + 48, kind, "#0f6e6e", 13);
  }
  if (room.lights_on) {
    text(svg, x + w - 64, y + 24, "Lights", "#1f8f6a", 12);
  }
  if (closed) {
    text(svg, x + 12, y + 58, "Water held", "#c23b2e", 12);
  }
  appliances.slice(0, 3).forEach((item, index) => {
    const mark = item.active ? "on" : "off";
    text(svg, x + 12, y + 74 + index * 16, `${item.name} · ${mark}`, "#16302a", 12);
  });
}

function groupAppliances(appliances) {
  const grouped = new Map();
  appliances.forEach((item) => {
    const key = String(item.room_id);
    const list = grouped.get(key) || [];
    list.push(item);
    grouped.set(key, list);
  });
  return grouped;
}

function labelFor(kind) {
  return String(kind || "room").replaceAll("_", " ");
}

function rect(svg, x, y, w, h, fill, stroke) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  node.setAttribute("x", x);
  node.setAttribute("y", y);
  node.setAttribute("width", w);
  node.setAttribute("height", h);
  node.setAttribute("rx", 0);
  node.setAttribute("fill", fill);
  node.setAttribute("stroke", stroke || "#16302a");
  node.setAttribute("stroke-width", 1.5);
  svg.appendChild(node);
}

function text(svg, x, y, value, fill, size) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", "text");
  node.setAttribute("x", x);
  node.setAttribute("y", y);
  node.setAttribute("fill", fill);
  node.setAttribute("font-size", size);
  node.setAttribute("font-family", "Georgia, serif");
  node.textContent = value;
  svg.appendChild(node);
}

function writeReadout(state) {
  const set = (field, value) => {
    const node = document.querySelector(`[data-field="${field}"]`);
    if (node) {
      node.textContent = value;
    }
  };
  const lit = state.rooms.filter((room) => room.lights_on).map((room) => room.name);
  const moving = state.flows.filter((flow) => flow.active).map((flow) => FLOW_LABELS[flow.id] || flow.id);
  const battery = { charging: "en charge", discharging: "en décharge", idle: "au repos" };
  set("clock", state.sharedClock || "Cette maison");
  set("valve", state.valve.open ? "ouverte" : "fermée");
  set("pump", state.pump.running ? "en marche" : "arrêtée");
  set("tank", `${state.tank.percent} % · ${state.tank.liters} / ${state.tank.capacity_liters} L`);
  set("battery", `${state.battery.percent} % · ${battery[state.battery.state] || state.battery.state}`);
  set("solar", `${state.solar.watts} W · ${state.solar.allocation}`);
  set("lights", lit.length ? lit.join(", ") : "éteintes");
  set("flows", moving.length ? moving.join(" · ") : "aucun");
}

function applyClock(home, clock) {
  return {
    ...home,
    sharedClock: `Heure ${clock.hour} · ${window.kzFr ? window.kzFr(clock.scenario) : clock.scenario}`,
    clockHour: Number(clock.hour),
  };
}

async function createTwin(stage) {
  // Realistic 3D first. The 2D plan stays as the fallback when WebGL2
  // or the Three.js modules are not available.
  try {
    const { DigitalTwin3D } = await import("./twin3d.js?v=demo2");
    return new DigitalTwin3D(stage);
  } catch (error) {
    console.warn("KIZUNA twin: 3D view unavailable, showing the floor plan.", error);
    stage.classList.remove("is-3d");
    return new DigitalTwin(stage);
  }
}

async function boot() {
  const root = document.querySelector("[data-twin-root]");
  const stage = document.querySelector("#twin-stage");
  if (!root || !stage) {
    return;
  }
  const twin = await createTwin(stage);
  const url = root.getAttribute("data-state-url");
  let homeState = null;
  let clockState = null;

  function publish() {
    if (!homeState) {
      return;
    }
    const state = clockState ? applyClock(homeState, clockState) : homeState;
    twin.setState(state);
    writeReadout(state);
    root.dataset.ready = "1";
  }

  const loadHome = async () => {
    try {
      const response = await fetch(url, {
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      if (!response.ok) {
        return;
      }
      homeState = await response.json();
      publish();
    } catch (error) {
      const node = document.querySelector('[data-field="flows"]');
      if (node) {
        node.textContent = "Le jumeau n'a pas pu lire l'état de la maison.";
      }
    }
  };

  window.addEventListener("kizuna-state", (event) => {
    clockState = event.detail;
    publish();
  });
  loadHome();
}

boot();
