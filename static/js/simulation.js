function readCookie(name) {
  const prefix = `${name}=`;
  for (const part of document.cookie.split(";")) {
    const item = part.trim();
    if (item.startsWith(prefix)) {
      return decodeURIComponent(item.slice(prefix.length));
    }
  }
  return "";
}

function showError(message) {
  const node = document.querySelector("#simulation-error");
  if (!node) {
    return;
  }
  if (!message) {
    node.hidden = true;
    node.textContent = "";
    return;
  }
  node.hidden = false;
  node.textContent = message;
}

function textOf(sensor) {
  if (!sensor) {
    return "";
  }
  return sensor.unit ? `${sensor.value} ${sensor.unit}` : String(sensor.value);
}

function setReading(key, text) {
  const node = document.querySelector(`[data-reading="${key}"]`);
  if (node) {
    node.textContent = text;
  }
}

function paint(state) {
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
      setReading(`${group}.${key}`, textOf(sensor));
    });
  });
  setReading("tanks.home_percent", `${state.tanks.home_percent} %`);
  setReading("tanks.farm_percent", `${state.tanks.farm_percent} %`);
  setReading("batteries.home_percent", `${state.batteries.home_percent} %`);
  setReading("batteries.farm_percent", `${state.batteries.farm_percent} %`);
  setReading("solar.home_watts", `${state.solar.home_watts} W`);
  setReading("solar.farm_watts", `${state.solar.farm_watts} W`);
  setReading("pump.farm", state.pump.farm);
  setReading("valves.home", state.valves.home);
  setReading("valves.farm", state.valves.farm);
  setReading("soil", `${state.soil_moisture} %`);
  setReading(
    "consumption.home_water_liters_per_hour",
    `${state.consumption.home_water_liters_per_hour} L/h`,
  );
  setReading(
    "consumption.home_electricity_watts",
    `${state.consumption.home_electricity_watts} W`,
  );
  const scenario = document.querySelector("#scenario");
  if (scenario) {
    scenario.value = state.scenario;
  }
  const seed = document.querySelector("#seed");
  if (seed && document.activeElement !== seed) {
    seed.value = state.seed;
  }
}

async function postSimulation(path, body) {
  const response = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-CSRFToken": readCookie("csrftoken"),
    },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "The simulation request failed.");
  }
  return payload;
}

function bindControls() {
  const advance = document.querySelector("#advance-simulation");
  const reset = document.querySelector("#reset-simulation");
  if (!advance || !reset) {
    return;
  }
  const buttons = [advance, reset];

  function lock(disabled) {
    buttons.forEach((button) => {
      button.disabled = disabled;
    });
  }

  advance.addEventListener("click", async () => {
    showError("");
    lock(true);
    try {
      const scenario = document.querySelector("#scenario").value;
      paint(await postSimulation("/api/simulation/advance/", { steps: 1, scenario }));
    } catch (error) {
      showError(error.message);
    } finally {
      lock(false);
    }
  });

  reset.addEventListener("click", async () => {
    showError("");
    lock(true);
    try {
      const scenario = document.querySelector("#scenario").value;
      const seed = Number(document.querySelector("#seed").value);
      paint(await postSimulation("/api/simulation/reset/", { scenario, seed }));
    } catch (error) {
      showError(error.message);
    } finally {
      lock(false);
    }
  });
}

bindControls();
