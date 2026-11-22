(() => {
  const form = document.querySelector("#lab-form");
  if (!form) {
    return;
  }
  const presets = JSON.parse(document.querySelector("#lab-presets").textContent);
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const step = reduced ? 0 : 650;
  const fields = ["temperature", "rainfall", "grid", "solar", "water", "soil", "duration"];
  const button = document.querySelector("#lab-simulate");
  const errorNode = document.querySelector("#lab-error");
  const charts = {};
  let last = null;
  let runId = 0;

  const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined) {
      node.textContent = text;
    }
    return node;
  };

  const readCookie = (name) => {
    const prefix = `${name}=`;
    for (const part of document.cookie.split(";")) {
      const item = part.trim();
      if (item.startsWith(prefix)) {
        return decodeURIComponent(item.slice(prefix.length));
      }
    }
    return "";
  };

  const showError = (message) => {
    errorNode.hidden = !message;
    errorNode.textContent = message || "";
  };

  const syncOutputs = () => {
    fields.forEach((name) => {
      const input = form.elements[name];
      const output = form.querySelector(`output[data-for="${name}"]`);
      if (input && output) {
        output.textContent = input.value;
      }
    });
  };

  form.querySelectorAll("[data-scenario]").forEach((choice) => {
    choice.addEventListener("click", () => {
      const name = choice.getAttribute("data-scenario");
      form.elements.scenario.value = name;
      form.querySelectorAll("[data-scenario]").forEach((other) => {
        const on = other === choice;
        other.classList.toggle("active", on);
        other.setAttribute("aria-checked", on ? "true" : "false");
      });
      fields.forEach((field) => {
        form.elements[field].value = presets[name][field];
      });
      syncOutputs();
    });
  });

  fields.forEach((name) => form.elements[name].addEventListener("input", syncOutputs));

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    showError("");
    const payload = { scenario: form.elements.scenario.value };
    fields.forEach((name) => {
      payload[name] = Number(form.elements[name].value);
    });
    button.disabled = true;
    button.textContent = "SIMULATING…";
    try {
      const response = await fetch("/api/crisis/simulate/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": readCookie("csrftoken") },
        body: JSON.stringify(payload),
      });
      const body = await response.json();
      if (!response.ok) {
        showError(body.detail || "The simulation did not run.");
        return;
      }
      last = body;
      play(body);
    } catch (error) {
      showError("The simulation did not run.");
    } finally {
      button.disabled = false;
      button.textContent = "SIMULATE";
    }
  });

  document.querySelector("#lab-replay").addEventListener("click", () => {
    if (last) {
      play(last);
    }
  });

  async function play(result) {
    const id = ++runId;
    const alive = () => id === runId;
    document.querySelector("#lab-idle").hidden = true;
    document.querySelector("#lab-run").hidden = false;
    const propagation = document.querySelector("#lab-propagation");
    const response = document.querySelector("#lab-response");
    const side = document.querySelector("#lab-side");
    const final = document.querySelector("#lab-final");
    const activated = document.querySelector("#lab-activated");
    propagation.replaceChildren();
    response.replaceChildren();
    side.replaceChildren();
    final.replaceChildren();
    final.className = "lab-final";
    activated.classList.remove("show");
    document.querySelector("#lab-ai").textContent = result.ai.note;

    const steps = result.propagation.steps;
    for (let index = 0; index < steps.length; index += 1) {
      if (!alive()) {
        return;
      }
      const item = steps[index];
      const node = el("li", "lab-node lab-node-bad");
      node.append(el("span", "lab-node-label", item.label), el("span", "lab-node-value", item.value));
      propagation.append(node);
      if (index < steps.length - 1) {
        propagation.append(el("li", "lab-link lab-link-bad", "↓"));
      }
      await reveal(node);
    }
    if (!result.propagation.cascade) {
      propagation.append(el("li", "lab-quiet", "No cascade in this run."));
    }

    await sleep(step);
    if (!alive()) {
      return;
    }
    activated.classList.add("show");
    await sleep(step * 1.4);

    for (const chain of result.response.chains) {
      const lane = el("ol", "lab-chain lab-chain-good");
      response.append(lane);
      for (let index = 0; index < chain.length; index += 1) {
        if (!alive()) {
          return;
        }
        const item = chain[index];
        const node = el("li", "lab-node lab-node-good");
        node.append(el("span", "lab-node-label", item.label));
        if (item.value) {
          node.append(el("span", "lab-node-value", item.value));
        }
        lane.append(node);
        if (index < chain.length - 1) {
          lane.append(el("li", "lab-link lab-link-good", "↓"));
        }
        await reveal(node);
      }
    }
    if (!result.response.chains.length) {
      response.append(el("p", "lab-quiet", "No energy or water flow was needed."));
    }
    result.response.side.forEach((text) => side.append(el("li", "", text)));

    await sleep(step);
    if (!alive()) {
      return;
    }
    final.textContent = result.response.status;
    final.classList.add(`lab-final-${result.response.level}`, "show");
    renderResults(result);
  }

  async function reveal(node) {
    await sleep(30);
    node.classList.add("show");
    await sleep(step);
  }

  function renderResults(result) {
    const panel = document.querySelector("#lab-results");
    panel.hidden = false;
    const comparison = result.comparison;
    const base = result.without.metrics;
    const smart = result.with.metrics;

    setHeadline("water", `${Math.round(comparison.water_saved_l).toLocaleString()} L`,
      `${Math.round(comparison.water_saved_parts.rain_recovered_l)} L rain · ${Math.round(comparison.water_saved_parts.evaporation_avoided_l)} L less evaporation`);
    setHeadline("energy", `${(comparison.energy_recovered_wh / 1000).toFixed(1)} kWh`,
      `${(base.solar_curtailed_wh / 1000).toFixed(1)} kWh solar wasted without KIZUNA`);
    setHeadline("crop", `${smart.crop_protection}%`, `of hours below crop-stress 55 · ${base.crop_protection}% without`);
    setHeadline("recovery", recovery(comparison.recovery.with, comparison.recovery.with_ongoing, smart.duration),
      `without KIZUNA: ${recovery(comparison.recovery.without, comparison.recovery.without_ongoing, base.duration)}`);

    const bars = document.querySelector("#lab-bars");
    bars.replaceChildren();
    comparison.rows.forEach((row) => {
      const max = row.unit === "%" || row.unit === "/100" ? 100 : Math.max(row.without, row.with, 1);
      const wrap = el("div", "lab-bar-row");
      const better = row.lower_is_better ? row.with < row.without : row.with > row.without;
      const head = el("div", "lab-bar-head");
      head.append(el("span", "", row.label));
      head.append(el("span", better ? "lab-better" : "", `${fmt(row.without)} → ${fmt(row.with)} ${row.unit}`));
      wrap.append(head);
      ["without", "with"].forEach((side) => {
        const track = el("div", "lab-track");
        const fill = el("div", `lab-fill lab-fill-${side}`);
        track.append(fill);
        wrap.append(track);
        window.requestAnimationFrame(() => {
          fill.style.width = `${Math.max(1.5, (row[side] / max) * 100)}%`;
        });
      });
      bars.append(wrap);
    });

    drawMap("#lab-map-without", result.nodes, base.affected);
    drawMap("#lab-map-with", result.nodes, smart.affected);
    drawCharts(result);

    const events = document.querySelector("#lab-events");
    events.replaceChildren();
    if (!result.with.events.length) {
      const row = el("tr");
      const cell = el("td", "", "No state change was needed.");
      cell.colSpan = 3;
      row.append(cell);
      events.append(row);
    }
    result.with.events.forEach((item) => {
      const row = el("tr");
      row.append(el("td", "", item.hour), el("td", "", item.action.replaceAll("_", " ")), el("td", "", item.reason));
      events.append(row);
    });

    const rules = document.querySelector("#lab-rules");
    rules.replaceChildren(
      el("li", "", `Water saved: ${comparison.water_saved_rule}`),
      el("li", "", `Energy recovered: ${comparison.energy_recovered_rule}`),
      el("li", "", `Status: ${result.response.rule}`),
      el("li", "", `Pump outage counts hours when irrigation was wanted, water was in the tank, and no power source could run the pump. Empty-tank hours: ${base.tank_empty_hours} without, ${smart.tank_empty_hours} with KIZUNA.`),
      el("li", "", result.label),
    );
  }

  function setHeadline(key, value, note) {
    document.querySelector(`[data-headline="${key}"]`).textContent = value;
    document.querySelector(`[data-headline-note="${key}"]`).textContent = note;
  }

  function recovery(hours, ongoing, duration) {
    if (ongoing) {
      return `not recovered in ${duration} h`;
    }
    if (hours === 0) {
      return "no crisis";
    }
    return `${hours} h`;
  }

  function fmt(value) {
    return Number.isInteger(value) ? value : value.toFixed(1);
  }

  function drawMap(selector, nodes, affected) {
    const layout = {
      grid: [50, 35],
      home_power: [175, 35],
      home_water: [300, 35],
      battery: [50, 115],
      pump: [175, 115],
      irrigation: [300, 115],
      crops: [400, 75],
    };
    const edges = [
      ["grid", "home_power"], ["grid", "pump"], ["battery", "home_power"], ["battery", "pump"],
      ["home_power", "home_water"], ["pump", "irrigation"], ["irrigation", "crops"],
    ];
    const lines = edges.map(([from, to]) => {
      const [x1, y1] = layout[from];
      const [x2, y2] = layout[to];
      const bad = affected[from] && affected[from].affected && affected[to] && affected[to].affected;
      return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" class="lab-edge${bad ? " lab-edge-bad" : ""}"/>`;
    }).join("");
    const circles = nodes.map((node) => {
      const [x, y] = layout[node.key];
      const state = affected[node.key];
      const bad = state && state.affected;
      const title = bad ? `${node.label}: affected from hour ${state.first_hour}` : `${node.label}: held`;
      return `<g class="lab-map-node${bad ? " bad" : ""}"><title>${title}</title><circle cx="${x}" cy="${y}" r="17"/><text x="${x}" y="${y + 32}">${node.label}</text></g>`;
    }).join("");
    document.querySelector(selector).innerHTML = `<svg viewBox="0 0 450 160" role="img" aria-label="Affected nodes">${lines}${circles}</svg>`;
  }

  function drawCharts(result) {
    if (!window.Chart) {
      return;
    }
    const labels = result.without.hours.map((item) => item.hour);
    const series = (run, key) => result[run].hours.map((item) => item[key]);
    const make = (id, datasets, max) => {
      if (charts[id]) {
        charts[id].destroy();
      }
      charts[id] = new window.Chart(document.getElementById(id), {
        type: "line",
        data: { labels, datasets },
        options: {
          animation: reduced ? false : { duration: 900 },
          interaction: { mode: "index", intersect: false },
          scales: {
            x: { title: { display: true, text: "Simulated hour" } },
            y: { min: 0, max },
          },
          plugins: { legend: { labels: { boxWidth: 12 } } },
        },
      });
    };
    const red = "#c0392b";
    const green = "#2f8f6b";
    make("lab-chart-crop", [
      { label: "Crop stress · without", data: series("without", "crop_stress"), borderColor: red, pointRadius: 0, tension: 0.25 },
      { label: "Crop stress · with", data: series("with", "crop_stress"), borderColor: green, pointRadius: 0, tension: 0.25 },
      { label: "Soil · without", data: series("without", "soil"), borderColor: red, borderDash: [5, 4], pointRadius: 0, tension: 0.25 },
      { label: "Soil · with", data: series("with", "soil"), borderColor: green, borderDash: [5, 4], pointRadius: 0, tension: 0.25 },
    ], 100);
    make("lab-chart-stock", [
      { label: "Battery · without", data: series("without", "home_battery_percent"), borderColor: red, pointRadius: 0, tension: 0.25 },
      { label: "Battery · with", data: series("with", "home_battery_percent"), borderColor: green, pointRadius: 0, tension: 0.25 },
      { label: "Tank · without", data: series("without", "home_tank_percent"), borderColor: red, borderDash: [5, 4], pointRadius: 0, tension: 0.25 },
      { label: "Tank · with", data: series("with", "home_tank_percent"), borderColor: green, borderDash: [5, 4], pointRadius: 0, tension: 0.25 },
    ], 100);
  }

  syncOutputs();
})();
