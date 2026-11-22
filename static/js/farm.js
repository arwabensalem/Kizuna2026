// Pages ferme : carte de la Tunisie, recherche de lieu, cultures multiples, animations.

const TUNISIA = [[30.2, 7.5], [37.6, 11.7]];

function fillMeters() {
  document.querySelectorAll("[data-meter]").forEach((meter) => {
    const value = Number(meter.dataset.meter);
    const bar = meter.querySelector(".meter-bar");
    if (!bar || Number.isNaN(value)) return;
    requestAnimationFrame(() => { bar.style.width = `${Math.max(0, Math.min(100, value))}%`; });
  });
}

function countUp() {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.querySelectorAll("[data-count]").forEach((node) => {
    const target = parseFloat(String(node.dataset.count).replace(",", "."));
    if (Number.isNaN(target) || reduce) return;
    const decimals = String(node.dataset.count).includes(".") ? 1 : 0;
    const start = performance.now();
    const duration = 900;
    const fmt = (v) => v.toLocaleString("fr-FR", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
    function step(now) {
      const t = Math.min(1, (now - start) / duration);
      node.textContent = fmt(target * (1 - Math.pow(1 - t, 3)));
      if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  });
}

function inTunisia(lat, lng) {
  return lat >= TUNISIA[0][0] && lat <= TUNISIA[1][0] && lng >= TUNISIA[0][1] && lng <= TUNISIA[1][1];
}

function baseLayers(map) {
  // Esri World_Street_Map : vérifié dans le navigateur sur 127.0.0.1, sans clé ni compte.
  const plan = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}", {
    maxZoom: 19,
    attribution: "Fond &copy; Esri",
  });
  const satellite = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
    maxZoom: 19,
    maxNativeZoom: 17,
    attribution: "Images &copy; Esri, Maxar",
  });
  plan.addTo(map);
  // Contour des gouvernorats servi par le site lui-même : la carte reste lisible même hors ligne.
  const overlays = {};
  if (typeof fetch === "function") {
    const govs = L.layerGroup().addTo(map);
    overlays["Gouvernorats"] = govs;
    fetch("/static/data/tunisia-governorates.geojson")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data) return;
        L.geoJSON(data, {
          interactive: false,
          style: { color: "#2f8fd8", weight: 1, opacity: 0.55, fillColor: "#5a9a3c", fillOpacity: 0.05 },
        }).addTo(govs);
      })
      .catch(() => {});
  }
  let failures = 0;
  plan.on("tileerror", () => {
    failures += 1;
    if (failures === 6) node(map).classList.add("kz-map-offline");
  });
  L.control.layers({ Plan: plan, Satellite: satellite }, overlays, { position: "topright" }).addTo(map);
}

function node(map) {
  return map.getContainer();
}

function tunisiaMap(node, options = {}) {
  const map = L.map(node, {
    maxBounds: L.latLngBounds(TUNISIA).pad(0.25),
    maxBoundsViscosity: 0.8,
    minZoom: 5,
    ...options,
  });
  baseLayers(map);
  map.fitBounds(TUNISIA);
  setTimeout(() => map.invalidateSize(), 200);
  return map;
}

function pin() {
  return L.divIcon({ className: "", html: '<div class="kz-map-pulse"></div>', iconSize: [18, 18], iconAnchor: [9, 9] });
}

function normalize(text) {
  return (text || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim();
}

function setupFarmPicker() {
  const node = document.querySelector("#farm-map");
  const latitude = document.querySelector("#id_latitude");
  const longitude = document.querySelector("#id_longitude");
  const location = document.querySelector("#id_location");
  const status = document.querySelector("[data-geo-status]");
  if (!node || !latitude || !longitude || typeof L === "undefined") return;
  const dataNode = document.querySelector("#kz-places-data");
  const places = dataNode ? JSON.parse(dataNode.textContent) : [];
  const map = tunisiaMap(node);
  let marker = null;

  function say(text, kind) {
    if (!status) return;
    status.textContent = text;
    status.className = `kz-geo-status small mb-2 ${kind || ""}`;
  }

  function place(lat, lng, zoom, fill = true) {
    if (!inTunisia(lat, lng)) {
      say("Ce point est en dehors de la Tunisie. Choisissez un lieu en Tunisie.", "warn");
      return;
    }
    if (fill) {
      latitude.value = lat.toFixed(6);
      longitude.value = lng.toFixed(6);
    }
    if (!marker) {
      marker = L.marker([lat, lng], { icon: pin(), draggable: true }).addTo(map);
      marker.on("dragend", () => {
        const p = marker.getLatLng();
        place(p.lat, p.lng, null);
        say("Position ajustée à la main.", "ok");
      });
    } else {
      marker.setLatLng([lat, lng]);
    }
    if (zoom) map.flyTo([lat, lng], zoom, { duration: 1.4 });
  }

  const lat0 = parseFloat(latitude.value);
  const lng0 = parseFloat(longitude.value);
  if (!Number.isNaN(lat0) && !Number.isNaN(lng0) && inTunisia(lat0, lng0)) {
    place(lat0, lng0, 14, false);
  } else if (!Number.isNaN(lat0)) {
    latitude.value = "";
    longitude.value = "";
    say("L’ancienne position était hors de Tunisie : tapez votre ville ou cliquez sur la carte.", "warn");
  }

  function localMatch(text) {
    const key = normalize(text);
    if (!key) return null;
    const exact = places.find((p) => normalize(p.name) === key);
    if (exact) return exact;
    return places
      .filter((p) => ` ${key} `.includes(` ${normalize(p.name)} `))
      .sort((a, b) => b.name.length - a.name.length)[0] || null;
  }

  let timer = null;
  let lastQuery = "";
  async function search() {
    const text = location.value.trim();
    if (text.length < 3 || text === lastQuery) return;
    lastQuery = text;
    const local = localMatch(text);
    if (local) {
      place(local.lat, local.lng, 12);
      say(`📍 ${local.name} trouvé. Cliquez sur la carte pour placer votre parcelle exacte.`, "ok");
      return;
    }
    say("Recherche du lieu…");
    try {
      const url = `https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=tn&q=${encodeURIComponent(text)}`;
      const response = await fetch(url, { headers: { "Accept-Language": "fr" } });
      const found = (await response.json())[0];
      if (found) {
        place(parseFloat(found.lat), parseFloat(found.lon), 13);
        say(`📍 ${found.display_name.split(",").slice(0, 2).join(",")} trouvé. Ajustez en cliquant sur la carte.`, "ok");
      } else {
        say("Lieu introuvable. Essayez le nom de la ville ou de la délégation, ou cliquez sur la carte.", "warn");
      }
    } catch (error) {
      say("Recherche impossible hors ligne. Cliquez directement sur la carte.", "warn");
    }
  }
  if (location) {
    location.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(search, 600); });
    location.addEventListener("change", search);
  }

  map.on("click", (event) => {
    place(event.latlng.lat, event.latlng.lng, map.getZoom() < 13 ? 14 : null);
    if (inTunisia(event.latlng.lat, event.latlng.lng)) say("Parcelle placée. Vous pouvez déplacer le repère.", "ok");
  });

  const me = document.querySelector("[data-geo-me]");
  if (me && navigator.geolocation) {
    me.addEventListener("click", () => {
      say("Localisation en cours…");
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          place(pos.coords.latitude, pos.coords.longitude, 15);
          if (inTunisia(pos.coords.latitude, pos.coords.longitude)) say("Position du téléphone utilisée.", "ok");
        },
        (error) => {
          if (error.code === 1) {
            say("La localisation est désactivée sur cet ordinateur (Paramètres Windows › Confidentialité › Emplacement, ou l’icône à droite de l’adresse). Tapez plutôt votre ville ou cliquez sur la carte.", "warn");
          } else {
            say("Position introuvable pour le moment. Tapez votre ville ou cliquez sur la carte.", "warn");
          }
        },
        { enableHighAccuracy: true, timeout: 10000 },
      );
    });
  } else if (me) {
    me.hidden = true;
  }
}

function setupFarmViews() {
  if (typeof L === "undefined") return;
  document.querySelectorAll(".farm-map-view").forEach((node) => {
    const lat = parseFloat(node.dataset.lat);
    const lng = parseFloat(node.dataset.lng);
    if (Number.isNaN(lat) || Number.isNaN(lng)) return;
    const map = tunisiaMap(node, { scrollWheelZoom: false });
    L.marker([lat, lng], { icon: pin() }).addTo(map);
    const zoom = node.dataset.exact === "1" ? 14 : 11;
    setTimeout(() => map.flyTo([lat, lng], zoom, { duration: 2 }), 600);
  });
}

function setupCrops() {
  const rows = document.querySelector("[data-crop-rows]");
  if (!rows) return;
  const template = document.querySelector("[data-crop-template]");
  const total = document.querySelector("#id_crops-TOTAL_FORMS");
  const farmArea = document.querySelector("#id_area_m2");
  const gauge = document.querySelector("[data-area-gauge]");
  const bar = document.querySelector("[data-area-bar]");
  const text = document.querySelector("[data-area-text]");
  const totalText = document.querySelector("[data-area-total]");

  function paint(row) {
    const kind = row.querySelector("select[name$='-kind']");
    const dot = row.querySelector("[data-crop-dot]");
    if (kind && dot) dot.className = `kz-crop-dot kz-crop-${kind.value}`;
  }

  function update() {
    let sum = 0;
    rows.querySelectorAll("[data-crop-row]:not(.is-removed)").forEach((row) => {
      const area = parseFloat((row.querySelector("input[name$='-area_m2']") || {}).value);
      if (!Number.isNaN(area)) sum += area;
      paint(row);
    });
    const max = parseFloat(farmArea && farmArea.value);
    const fmt = (v) => Math.round(v).toLocaleString("fr-FR");
    if (text) text.textContent = `${fmt(sum)} m² cultivés`;
    if (!Number.isNaN(max) && max > 0) {
      const share = (100 * sum) / max;
      if (bar) bar.style.width = `${Math.min(100, share)}%`;
      if (totalText) totalText.textContent = sum > max ? `Dépasse la ferme de ${fmt(sum - max)} m²` : `${Math.round(share)} % de ${fmt(max)} m²`;
      if (gauge) gauge.classList.toggle("over", sum > max);
    } else if (totalText) {
      totalText.textContent = "Indiquez la surface de la ferme";
    }
  }

  function wire(row) {
    row.addEventListener("input", update);
    row.addEventListener("change", update);
    const remove = row.querySelector("[data-crop-remove]");
    if (remove) {
      remove.addEventListener("click", () => {
        const del = row.querySelector("input[name$='-DELETE']");
        const id = row.querySelector("input[name$='-id']");
        if (del && id && id.value) {
          del.checked = true;
          row.classList.add("is-removed");
        } else {
          row.remove();
          renumber();
        }
        update();
      });
    }
  }

  function renumber() {
    const all = rows.querySelectorAll("[data-crop-row]");
    all.forEach((row, index) => {
      row.querySelectorAll("[name], [id], label[for]").forEach((el) => {
        ["name", "id", "for"].forEach((attr) => {
          const value = el.getAttribute(attr);
          if (value) el.setAttribute(attr, value.replace(/crops-(\d+|__prefix__)-/, `crops-${index}-`));
        });
      });
    });
    total.value = all.length;
  }

  function add() {
    const index = parseInt(total.value, 10);
    const html = template.innerHTML.replace(/__prefix__/g, index);
    const wrap = document.createElement("div");
    wrap.innerHTML = html.trim();
    const row = wrap.firstElementChild;
    rows.appendChild(row);
    total.value = index + 1;
    wire(row);
    update();
    const area = row.querySelector("input[name$='-area_m2']");
    if (area) area.focus();
  }

  rows.querySelectorAll("[data-crop-row]").forEach(wire);
  document.querySelector("[data-crop-add]").addEventListener("click", add);
  if (farmArea) farmArea.addEventListener("input", update);
  if (!rows.querySelector("[data-crop-row]")) add();
  update();
}

const farmSwitch = document.querySelector(".farm-switch");
if (farmSwitch) farmSwitch.addEventListener("change", () => farmSwitch.form.submit());

fillMeters();
countUp();
setupFarmPicker();
setupFarmViews();
setupCrops();
