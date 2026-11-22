/**
 * One poll of the shared clock.
 *
 * GET /api/simulation/state/ once a second while a live page is visible.
 * The response is the stored clock. Pages paint from it. Play posts to
 * /api/simulation/advance/ and does not keep a second clock.
 */
(function () {
  if (!document.querySelector("[data-live]")) {
    return;
  }

  const POLL_MS = 1000;
  let timer = null;
  let running = false;
  let stepping = false;
  let seen = "";
  let chart = null;

  function cookie(name) {
    const prefix = `${name}=`;
    for (const part of document.cookie.split(";")) {
      const item = part.trim();
      if (item.startsWith(prefix)) {
        return decodeURIComponent(item.slice(prefix.length));
      }
    }
    return "";
  }

  function cap(value) {
    const text = String(value ?? "");
    return text ? text.charAt(0).toUpperCase() + text.slice(1) : "";
  }

  function text(name, value) {
    document.querySelectorAll(`[data-live-text="${name}"]`).forEach((node) => {
      node.textContent = value;
    });
  }

  function paintReadings(state) {
    const write = (key, value) => {
      document.querySelectorAll(`[data-reading="${key}"]`).forEach((node) => {
        node.textContent = value;
      });
    };
    if (!state || !state.sensors) {
      return;
    }
    const hour = document.querySelector("[data-clock-hour]");
    const time = document.querySelector("[data-clock-time]");
    const crisis = document.querySelector("[data-crisis]");
    if (hour) {
      hour.textContent = state.hour;
    }
    if (time) {
      time.textContent = state.simulated_at;
    }
    if (crisis) {
      crisis.textContent = state.crisis_state;
    }
    Object.entries(state.sensors).forEach(([group, sensors]) => {
      Object.entries(sensors).forEach(([key, sensor]) => {
        const shown = sensor.unit ? `${sensor.value} ${sensor.unit}` : String(sensor.value);
        write(`${group}.${key}`, shown);
      });
    });
    write("tanks.home_percent", `${state.tanks.home_percent} %`);
    write("tanks.farm_percent", `${state.tanks.farm_percent} %`);
    write("batteries.home_percent", `${state.batteries.home_percent} %`);
    write("batteries.farm_percent", `${state.batteries.farm_percent} %`);
    write("solar.home_watts", `${state.solar.home_watts} W`);
    write("solar.farm_watts", `${state.solar.farm_watts} W`);
    write("pump.farm", state.pump.farm);
    write("valves.home", state.valves.home);
    write("valves.farm", state.valves.farm);
    write("soil", `${state.soil_moisture} %`);
    write(
      "consumption.home_water_liters_per_hour",
      `${state.consumption.home_water_liters_per_hour} L/h`,
    );
    write(
      "consumption.home_electricity_watts",
      `${state.consumption.home_electricity_watts} W`,
    );
  }

  function paintDashboard(state) {
    const root = document.querySelector('[data-live="dashboard"]');
    if (!root || !state.reading) {
      return;
    }
    const reading = state.reading;
    const fr = window.kzFr || ((v) => v);
    const frFlow = window.kzFrFlow || ((v) => v);
    const alerts = Number(root.dataset.alerts || 0);
    text("hour", state.hour);
    text("scenario", fr(state.scenario));
    text("status", fr(reading.status));
    text("status-detail", fr(reading.status_detail));
    text("grid", fr(reading.grid));
    text("home-tank", state.tanks.home_percent);
    text("farm-tank", state.tanks.farm_percent);
    text("home-battery", state.batteries.home_percent);
    text("farm-battery", state.batteries.farm_percent);
    text("home-solar", state.solar.home_watts);
    text("farm-solar", state.solar.farm_watts);
    text("resilience", reading.resilience);
    text("pump", fr(cap(state.pump.farm)));
    text("soil", state.soil_moisture);
    document.querySelectorAll("[data-live-meter]").forEach((bar) => {
      const key = bar.getAttribute("data-live-meter");
      const value = key === "home-battery"
        ? state.batteries.home_percent
        : state.tanks.home_percent;
      const width = Math.max(0, Math.min(100, Number(value) || 0));
      bar.style.width = `${width}%`;
    });
    const crisisValue = document.querySelector("[data-live-text='crisis']");
    const crisisDetail = document.querySelector("[data-live-text='crisis-detail']");
    if (crisisValue && crisisDetail) {
      if (state.crisis_state === "none" && alerts === 0) {
        crisisValue.textContent = "Tout est calme";
        crisisDetail.textContent = "Aucune crise en ce moment.";
      } else if (state.crisis_state === "none") {
        crisisValue.textContent = `${alerts} alerte${alerts === 1 ? "" : "s"}`;
        crisisDetail.textContent = `À voir sur vos maisons. Situation générale : ${fr(state.scenario)}.`;
      } else {
        crisisValue.textContent = fr(String(state.crisis_state).toUpperCase());
        crisisDetail.textContent = `${alerts} alerte${alerts === 1 ? "" : "s"} sur vos maisons. Situation : ${fr(state.scenario)}.`;
      }
    }
    const flows = document.querySelector("#dash-flows");
    if (flows) {
      flows.replaceChildren(...(reading.flows.length ? reading.flows.map((flow) => {
        const item = document.createElement("li");
        const name = document.createElement("span");
        name.textContent = frFlow(`${flow.source_label} → ${flow.destination_label}`);
        const amount = document.createElement("strong");
        amount.textContent = `${flow.quantity} ${flow.unit}`;
        item.append(name, amount);
        return item;
      }) : [emptyItem("Aucun échange pour cette heure.")]));
    }
    text("brain", fr(reading.status));
    text("brain-detail", fr(reading.brain_detail));
    const lines = document.querySelector("#dash-brain-lines");
    if (lines) {
      lines.replaceChildren(...reading.lines.map((line) => {
        const item = document.createElement("li");
        const name = document.createElement("span");
        name.textContent = fr(line.label);
        const value = document.createElement("strong");
        value.textContent = fr(line.value);
        item.append(name, value);
        return item;
      }));
    }
    paintChart(state.series || []);
  }

  function emptyItem(message) {
    const item = document.createElement("li");
    item.textContent = message;
    return item;
  }

  function paintChart(series) {
    const canvas = document.querySelector("#dash-chart");
    if (!canvas || typeof window.Chart !== "function") {
      return;
    }
    const labels = series.map((row) => row.hour);
    const tank = series.map((row) => row.home_tank);
    const battery = series.map((row) => row.home_battery);
    if (!chart) {
      chart = new window.Chart(canvas, {
        type: "line",
        data: {
          labels,
          datasets: [
            {
              label: "Réservoir maison %",
              data: tank,
              borderColor: "#0f6e6e",
              backgroundColor: "#0f6e6e",
              pointRadius: 0,
              tension: 0.15,
            },
            {
              label: "Batterie maison %",
              data: battery,
              borderColor: "#1d5e46",
              backgroundColor: "#1d5e46",
              pointRadius: 0,
              tension: 0.15,
            },
          ],
        },
        options: {
          animation: false,
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: "bottom" } },
          scales: {
            y: { min: 0, max: 100 },
          },
        },
      });
      return;
    }
    chart.data.labels = labels;
    chart.data.datasets[0].data = tank;
    chart.data.datasets[1].data = battery;
    chart.update();
  }

  async function paintBusiness(state) {
    const root = document.querySelector("[data-biz-url]");
    if (!root || root.dataset.seenHour === String(state.hour)) {
      return;
    }
    root.dataset.seenHour = String(state.hour);
    try {
      const response = await fetch(root.dataset.bizUrl, {
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        return;
      }
      const body = await response.json();
      const solar = document.querySelector("[data-biz='solar']");
      if (solar) {
        solar.textContent = body.solar_w == null ? "—" : `${body.solar_w} W`;
      }
      const sun = document.querySelector("[data-biz='sun']");
      if (sun && body.sun_factor != null) {
        sun.textContent = body.sun_factor;
      }
      const hour = document.querySelector("[data-biz='hour']");
      if (hour) {
        hour.textContent = body.hour;
      }
      const tbody = document.querySelector("#biz-flows");
      if (tbody && Array.isArray(body.flows)) {
        tbody.replaceChildren(...(body.flows.length ? body.flows.map((flow) => {
          const row = document.createElement("tr");
          if (flow.kind === "supplementary") {
            row.className = "biz-flow-extra";
          }
          [flow.resource, flow.source, flow.destination, `${flow.quantity} ${flow.unit}`, flow.note]
            .forEach((value) => {
              const cell = document.createElement("td");
              cell.textContent = value;
              row.appendChild(cell);
            });
          return row;
        }) : [(() => {
          const row = document.createElement("tr");
          const cell = document.createElement("td");
          cell.colSpan = 5;
          cell.textContent = "Aucun échange pour cette heure.";
          row.appendChild(cell);
          return row;
        })()]));
      }
    } catch (error) {
      root.dataset.seenHour = "";
    }
  }

  async function tick() {
    try {
      const response = await fetch("/api/simulation/state/", {
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        return;
      }
      const state = await response.json();
      const key = `${state.hour}|${state.scenario}|${state.crisis_state}|${state.simulated_at}`;
      paintReadings(state);
      paintDashboard(state);
      if (key !== seen) {
        seen = key;
        window.dispatchEvent(new CustomEvent("kizuna-state", { detail: state }));
        paintBusiness(state);
      }
    } catch (error) {
      /* The next second tries again. A missed poll does not change the clock. */
    }
  }

  function paintRunButtons() {
    document.querySelectorAll("[data-run-clock]").forEach((button) => {
      button.textContent = running ? "Pause" : "Faire avancer le temps";
      button.setAttribute("aria-pressed", running ? "true" : "false");
    });
    const advance = document.querySelector("#advance-simulation");
    const reset = document.querySelector("#reset-simulation");
    if (advance) {
      advance.disabled = running;
    }
    if (reset) {
      reset.disabled = running;
    }
  }

  async function step() {
    if (!running || stepping || document.hidden) {
      return;
    }
    stepping = true;
    try {
      const scenario = document.querySelector("#scenario");
      const body = { steps: 1 };
      if (scenario) {
        body.scenario = scenario.value;
      }
      const response = await fetch("/api/simulation/advance/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": cookie("csrftoken"),
        },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        running = false;
        paintRunButtons();
        return;
      }
      await tick();
    } catch (error) {
      running = false;
      paintRunButtons();
    } finally {
      stepping = false;
    }
  }

  document.querySelectorAll("[data-run-clock]").forEach((button) => {
    button.addEventListener("click", () => {
      running = !running;
      paintRunButtons();
      if (running) {
        step();
      }
    });
  });

  function start() {
    if (timer || document.hidden) {
      return;
    }
    tick();
    timer = window.setInterval(() => {
      if (running) {
        step();
      } else {
        tick();
      }
    }, POLL_MS);
  }

  function stop() {
    window.clearInterval(timer);
    timer = null;
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      stop();
    } else {
      start();
    }
  });

  function begin() {
    start();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", begin);
  } else {
    begin();
  }
})();
