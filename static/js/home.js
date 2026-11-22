function fillMeters() {
  document.querySelectorAll("[data-meter]").forEach((meter) => {
    const value = Number(meter.dataset.meter);
    const bar = meter.querySelector(".meter-bar");
    if (!bar || Number.isNaN(value)) {
      return;
    }
    const width = Math.max(0, Math.min(100, value));
    bar.style.width = `${width}%`;
  });
}

function setupApplianceForm(rules) {
  const form = document.querySelector("#appliance-form");
  if (!form) {
    return;
  }
  const kind = form.querySelector("#id_kind");
  const home = form.querySelector("#id_home");
  const room = form.querySelector("#id_room");
  const power = form.querySelector("#id_power_watts");
  const water = form.querySelector("#id_water_liters_per_hour");
  const waterWrap = water ? water.closest(".mb-3") : null;
  let lastDefault = null;

  function applyKind() {
    const preset = rules.defaults[kind.value] || { power: 0, water: 0 };
    const usesWater = rules.waterKinds.includes(kind.value);
    if (waterWrap) {
      waterWrap.hidden = !usesWater;
    }
    if (!usesWater && water) {
      water.value = "0";
    } else if (usesWater && water && (water.value === "" || water.value === "0" || water.value === "0.00")) {
      water.value = String(preset.water);
    }
    const powerIsUnset = power && (power.value === "" || (power.value === "0" && lastDefault === null));
    if (power && (powerIsUnset || power.value === String(lastDefault))) {
      power.value = String(preset.power);
    }
    lastDefault = preset.power;
  }

  function filterRooms() {
    if (!home || !room) {
      return;
    }
    const homeId = home.value;
    Array.from(room.options).forEach((option) => {
      if (!option.value) {
        option.hidden = false;
        return;
      }
      const matches = option.dataset.home === homeId;
      option.hidden = !matches;
      if (!matches && option.selected) {
        room.value = "";
      }
    });
  }

  if (kind) {
    kind.addEventListener("change", applyKind);
    applyKind();
  }
  if (home) {
    home.addEventListener("change", filterRooms);
    filterRooms();
  }
}

const homeSwitch = document.querySelector(".home-switch");
if (homeSwitch) {
  homeSwitch.addEventListener("change", () => {
    homeSwitch.form.submit();
  });
}

fillMeters();

const rulesNode = document.getElementById("appliance-rules");
if (rulesNode) {
  setupApplianceForm(JSON.parse(rulesNode.textContent));
}
