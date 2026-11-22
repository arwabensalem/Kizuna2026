const data = JSON.parse(document.getElementById("crisis-day-data").textContent);
const beats = data.beats;
let index = 0;
let timer = null;

const time = document.getElementById("day-time");
const title = document.getElementById("day-title");
const twin = document.getElementById("day-twin");
const flows = document.getElementById("day-flows");
const prop = document.getElementById("day-prop");
const brain = document.getElementById("day-brain");
const actions = document.getElementById("day-actions");
const chart = document.getElementById("day-chart");
const tunis = document.getElementById("day-tunis");
const tunisNote = document.getElementById("day-tunis-note");
const end = document.getElementById("day-end");
const endTitle = document.getElementById("day-end-title");
const endMetrics = document.getElementById("day-end-metrics");

function show(beat) {
  time.textContent = beat.time;
  title.textContent = beat.title;
  const note = document.getElementById("day-note");
  note.textContent = beat.note || "";
  note.hidden = !beat.note;
  const home = beat.twin;
  twin.innerHTML = [
    row("Temperature", `${home.temperature}°C`),
    row("Home tank", `${home.home_tank_percent}%`),
    row("Farm tank", `${home.farm_tank_percent}%`),
    row("Home battery", `${home.home_battery_percent}%`),
    row("Farm battery", `${home.farm_battery_percent}%`),
    row("Home solar", `${home.solar_w} W`),
    row("Pump", home.pump),
    row("Soil", `${home.soil}%`),
  ].join("");
  flows.innerHTML = beat.flows.length
    ? beat.flows.map((flow) => (
      `<li class="day-flow"><span>${flow.source}</span><span class="day-dash"></span><span>${flow.destination}</span><strong>${flow.quantity} ${flow.unit}</strong></li>`
    )).join("")
    : "<li>No flow this beat.</li>";
  prop.innerHTML = beat.propagation.map((step) => (
    `<li class="${step.on ? "on" : ""}"><span>${step.label}</span><strong>${step.value}</strong></li>`
  )).join("");
  brain.innerHTML = beat.brain.map((line) => `<li><span>${line.label}</span><strong>${line.value}</strong></li>`).join("");
  actions.innerHTML = beat.actions.length
    ? beat.actions.map((item) => `<li><span>${item.time}</span> ${item.text}</li>`).join("")
    : "<li>No autonomous action yet.</li>";
  drawChart(index);
  const score = beat.tunisia;
  tunis.textContent = `${score.overall}`;
  tunisNote.textContent = `${score.place} · water ${score.water} · energy ${score.energy} · agriculture ${score.agriculture} · climate ${score.climate}. ${score.note}`;
  if (beat.summary) {
    const summary = beat.summary;
    end.hidden = false;
    endTitle.textContent = summary.headline;
    endMetrics.innerHTML = [
      metric("Water saved", `${summary.water_saved_l} L`, summary.rules.water_saved_l),
      metric("Energy recovered", `${summary.energy_recovered_wh} Wh`, summary.rules.energy_recovered_wh),
      metric("Crops protected", `${summary.crops_protected} of ${summary.crops_hours} hours`, summary.rules.crops_protected),
      metric("Homes stabilized", String(summary.homes_stabilized), summary.rules.homes_stabilized),
      metric("Water recovered", `${summary.water_recovered_l} L`, summary.rules.water_recovered_l),
    ].join("");
  } else {
    end.hidden = true;
  }
}

function row(label, value) {
  return `<div><dt>${label}</dt><dd>${value}</dd></div>`;
}

function metric(label, value, rule) {
  return `<div><dt>${label}</dt><dd>${value}</dd><p>${rule}</p></div>`;
}

function drawChart(upto) {
  const series = [
    { key: "crop_stress", color: "#9a3412" },
    { key: "water_stress", color: "#0f6e6e" },
    { key: "energy_stress", color: "#1d5e46" },
  ];
  const width = 320;
  const height = 120;
  const points = [];
  beats.slice(0, upto + 1).forEach((beat) => {
    const previous = points[points.length - 1];
    const same = previous
      && previous.chart.crop_stress === beat.chart.crop_stress
      && previous.chart.water_stress === beat.chart.water_stress
      && previous.chart.energy_stress === beat.chart.energy_stress;
    if (!same) {
      points.push(beat);
    }
  });
  const step = points.length > 1 ? (width - 16) / (points.length - 1) : 0;
  const lines = series.map((seriesItem) => {
    const path = points.map((beat, position) => {
      const y = 8 + (100 - beat.chart[seriesItem.key]) / 100 * (height - 16);
      return `${position === 0 ? "M" : "L"}${8 + position * step},${y.toFixed(1)}`;
    }).join(" ");
    return `<path d="${path}" fill="none" stroke="${seriesItem.color}" stroke-width="2"/>`;
  }).join("");
  chart.innerHTML = lines;
}

function play() {
  if (timer) {
    return;
  }
  if (index >= beats.length - 1) {
    index = 0;
  }
  timer = window.setInterval(() => {
    index += 1;
    show(beats[index]);
    if (index >= beats.length - 1) {
      pause();
    }
  }, 1600);
}

function pause() {
  window.clearInterval(timer);
  timer = null;
}

function reset() {
  pause();
  index = 0;
  show(beats[0]);
}

document.getElementById("day-start-crisis").addEventListener("click", play);
document.getElementById("day-start").addEventListener("click", play);
document.getElementById("day-pause").addEventListener("click", pause);
document.getElementById("day-reset").addEventListener("click", reset);
show(beats[0]);
