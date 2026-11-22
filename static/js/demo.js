const data = JSON.parse(document.getElementById("kizuna-demo").textContent);
const steps = data.steps;
const atlas = data.atlas;
let index = 0;
let timer = null;
let chart = null;
let map = null;
let boundaries = null;

const stage = document.getElementById("demo-stage");
const finale = document.getElementById("demo-finale");
const count = document.getElementById("demo-count");
const time = document.getElementById("demo-time");
const title = document.getElementById("demo-title");
const narration = document.getElementById("demo-narration");
const source = document.getElementById("demo-source");
const rail = document.getElementById("demo-rail");
const events = document.getElementById("demo-events");
const prop = document.getElementById("demo-prop");
const dashboard = document.getElementById("demo-dashboard");
const twin = document.getElementById("demo-twin");
const brain = document.getElementById("demo-brain");
const flows = document.getElementById("demo-flows");
const mapPanel = document.getElementById("demo-map");
const mapTitle = document.getElementById("demo-map-title");
const places = document.getElementById("demo-places");
const leafletNode = document.getElementById("demo-leaflet");
const national = document.getElementById("demo-national");
const mapNote = document.getElementById("demo-map-note");

rail.innerHTML = steps.map((step, position) => (
  `<li data-step="${position}">${position + 1}. ${step.title}</li>`
)).join("");

function show(step) {
  finale.hidden = true;
  stage.hidden = false;
  count.textContent = `${index + 1} / ${steps.length}`;
  time.textContent = step.time;
  title.textContent = step.title;
  narration.textContent = step.narration;
  source.textContent = step.source;
  document.querySelectorAll(".demo-panel").forEach((panel) => {
    panel.classList.toggle("is-focus", panel.dataset.panel === step.focus);
  });
  rail.querySelectorAll("li").forEach((item) => {
    item.classList.toggle("is-current", Number(item.dataset.step) === index);
  });
  const current = rail.querySelector(".is-current");
  if (current) {
    current.scrollIntoView({ block: "nearest" });
  }
  const card = step.dashboard;
  dashboard.innerHTML = [
    row("Status", step.status),
    row("Water", card.water),
    row("Energy", card.energy),
    row("Crisis", card.crisis),
    row("Solar", card.solar),
    row("Resilience", card.resilience),
  ].join("");
  const house = step.twin;
  twin.innerHTML = [
    row("Temperature", `${house.temperature}°C`),
    row("Tank", `${house.tank}%`),
    row("Battery", `${house.battery}%`),
    row("Solar", `${house.solar} W`),
    row("Soil", `${house.soil}%`),
    row("Pump", house.pump),
    row("Valve", house.valve),
    row("Rain", `${house.rain} mm`),
  ].join("");
  paintHouse(house);
  brain.innerHTML = step.brain.map((line) => (
    `<li><span>${line.label}</span><strong>${line.value}</strong></li>`
  )).join("");
  flows.innerHTML = step.flows.length
    ? step.flows.map((flow) => (
      `<li class="day-flow"><span>${flow.source}</span><span class="day-dash"></span><span>${flow.destination}</span><strong>${flow.quantity} ${flow.unit}</strong></li>`
    )).join("")
    : "<li>No flow this chapter.</li>";
  events.innerHTML = step.events.length
    ? step.events.map((item) => `<li><span>${item.time}</span> ${item.text}</li>`).join("")
    : "<li>No logged action yet.</li>";
  prop.innerHTML = (step.propagation || []).map((item) => (
    `<li class="${item.on ? "on" : ""}"><span>${item.label}</span><strong>${item.value}</strong></li>`
  )).join("");
  drawChart();
  paintMap(step);
}

function row(label, value) {
  return `<div><dt>${label}</dt><dd>${value}</dd></div>`;
}

function paintHouse(house) {
  const tank = document.getElementById("demo-tank");
  const height = Math.max(0, Math.min(100, Number(house.tank))) / 100 * 100;
  tank.setAttribute("height", height.toFixed(1));
  tank.setAttribute("y", (140 - height).toFixed(1));
  const solar = document.getElementById("demo-solar");
  const share = Math.max(0, Math.min(1, Number(house.solar) / 3000));
  solar.setAttribute("opacity", (0.25 + share * 0.75).toFixed(2));
  document.getElementById("demo-valve").setAttribute("fill", house.valve === "open" ? "#1f8f6a" : "#c23b2e");
  const soilWidth = Math.max(0, Math.min(100, Number(house.soil))) / 100 * 150;
  document.getElementById("demo-soil").setAttribute("width", soilWidth.toFixed(1));
  document.getElementById("demo-pump").textContent = `Pump ${house.pump}`;
  document.getElementById("demo-rain").textContent = Number(house.rain) > 0 ? `${house.rain} mm` : "";
}

function drawChart() {
  const canvas = document.getElementById("demo-chart");
  if (!canvas || typeof window.Chart === "undefined") {
    return;
  }
  const shown = steps.slice(0, index + 1);
  const payload = {
    labels: shown.map((step) => step.time),
    datasets: [
      {
        label: "Crop stress",
        data: shown.map((step) => step.chart.crop_stress),
        borderColor: "#c23b2e",
        backgroundColor: "transparent",
        tension: 0,
        pointRadius: 2,
      },
      {
        label: "Resilience",
        data: shown.map((step) => step.chart.resilience),
        borderColor: "#0f6e6e",
        backgroundColor: "transparent",
        tension: 0,
        pointRadius: 2,
      },
    ],
  };
  if (chart) {
    chart.data = payload;
    chart.update();
    return;
  }
  chart = new window.Chart(canvas, {
    type: "line",
    data: payload,
    options: {
      animation: false,
      responsive: true,
      scales: { y: { min: 0, max: 100 } },
      plugins: { legend: { position: "bottom" } },
    },
  });
}

function paintMap(step) {
  const zoomed = step.scope !== "home";
  mapPanel.hidden = !zoomed;
  if (!zoomed) {
    return;
  }
  places.hidden = step.scope !== "neighbourhood";
  leafletNode.hidden = step.scope === "neighbourhood";
  national.hidden = step.scope !== "score";
  mapNote.textContent = atlas.note;
  if (step.scope === "neighbourhood") {
    mapTitle.textContent = `${atlas.neighbourhood}, Tunis`;
    const sites = step.sites;
    places.innerHTML = [
      `<p>Neighbourhood index ${atlas.tunis.overall}</p>`,
      "<ul>",
      `<li><span>Home</span><strong>${sites.home}</strong></li>`,
      `<li><span>Farm</span><strong>${sites.farm}</strong></li>`,
      `<li><span>Workshop</span><strong>${sites.workshop}</strong></li>`,
      "</ul>",
      `<p>${sites.home_note}</p>`,
      `<p>${sites.farm_note}</p>`,
      `<p>${sites.workshop_note}</p>`,
    ].join("");
    return;
  }
  mapTitle.textContent = step.scope === "score" ? "Tunisia Resilience Score" : "Tunisia";
  national.textContent = step.scope === "score" ? String(atlas.national.overall) : "";
  ensureMap();
}

function ensureMap() {
  if (map || typeof window.L === "undefined") {
    if (map) {
      window.setTimeout(() => map.invalidateSize(), 50);
    }
    return;
  }
  map = window.L.map(leafletNode, { zoomControl: true, attributionControl: true });
  map.attributionControl.setPrefix("");
  map.attributionControl.addAttribution("geoBoundaries 2017, OpenStreetMap (ODbL). Colours are the simulated profile.");
  const byName = Object.fromEntries(atlas.governorates.map((row) => [row.name, row]));
  fetch(leafletNode.dataset.boundaries)
    .then((response) => response.json())
    .then((geojson) => {
      boundaries = window.L.geoJSON(geojson, {
        style: (feature) => ({
          color: "#16302a",
          weight: 1,
          fillColor: color(byName[feature.properties.shapeName].overall),
          fillOpacity: 0.85,
        }),
      }).addTo(map);
      map.fitBounds(boundaries.getBounds(), { padding: [12, 12] });
    });
}

function color(score) {
  const stops = [[194, 59, 46], [224, 165, 38], [31, 143, 106]];
  const scaled = Math.max(0, Math.min(100, score)) / 100 * (stops.length - 1);
  const slot = Math.min(stops.length - 2, Math.floor(scaled));
  const fraction = scaled - slot;
  const mix = stops[slot].map((channel, indexSlot) => (
    Math.round(channel + (stops[slot + 1][indexSlot] - channel) * fraction)
  ));
  return `rgb(${mix.join(",")})`;
}

function play() {
  if (timer) {
    return;
  }
  if (!finale.hidden) {
    index = 0;
    show(steps[0]);
  }
  timer = window.setInterval(() => {
    if (index >= steps.length - 1) {
      pause();
      finale.hidden = false;
      stage.hidden = true;
      return;
    }
    index += 1;
    show(steps[index]);
  }, 4000);
}

function pause() {
  window.clearInterval(timer);
  timer = null;
}

function reset() {
  pause();
  index = 0;
  show(steps[0]);
}

document.getElementById("demo-kizuna").addEventListener("click", play);
document.getElementById("demo-start").addEventListener("click", play);
document.getElementById("demo-pause").addEventListener("click", pause);
document.getElementById("demo-reset").addEventListener("click", reset);
show(steps[0]);
if (new URLSearchParams(window.location.search).get("play") === "1") {
  play();
}
