(() => {
  const mapNode = document.querySelector("#tn-map");
  if (!mapNode || typeof window.L === "undefined") {
    return;
  }
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const PILLARS = [
    ["water", "Water resilience"],
    ["energy", "Energy resilience"],
    ["agriculture", "Agricultural resilience"],
    ["climate", "Climate resilience"],
  ];
  const KIND = { home: "Hm", farm: "Fm", business: "Bz" };
  const state = { data: null, selected: null, path: [], token: 0 };
  let map;
  let polygons;
  const layers = {};

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

  const color = (score) => {
    const stops = [[194, 59, 46], [224, 165, 38], [31, 143, 106]];
    const scaled = Math.max(0, Math.min(100, score)) / 100 * (stops.length - 1);
    const index = Math.min(stops.length - 2, Math.floor(scaled));
    const fraction = scaled - index;
    const mix = stops[index].map((channel, slot) => Math.round(channel + (stops[index + 1][slot] - channel) * fraction));
    return `rgb(${mix.join(",")})`;
  };

  const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

  async function load() {
    const panel = document.querySelector("#tn-panel");
    try {
      const [atlas, boundaries] = await Promise.all([
        fetch("/api/tunisia/", { cache: "no-store" }).then((response) => response.json().then((body) => ({ ok: response.ok, body }))),
        fetch(mapNode.dataset.boundaries).then((response) => response.json()),
      ]);
      if (!atlas.ok) {
        panel.textContent = atlas.body.detail || "The map could not be loaded.";
        return;
      }
      state.data = atlas.body;
      draw(boundaries);
    } catch (error) {
      panel.textContent = "The map could not be loaded.";
    }
  }

  function draw(boundaries) {
    const data = state.data;
    map = window.L.map(mapNode, { zoomControl: true, minZoom: 6, maxZoom: 18 });
    map.setView([data.country.lat, data.country.lng], data.country.zoom, { animate: false });
    window.L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}", {
      attribution: "Tiles &copy; Esri",
      maxZoom: 18,
      maxNativeZoom: 16,
    }).addTo(map);
    const byName = Object.fromEntries(data.governorates.map((item) => [item.name, item]));
    polygons = window.L.geoJSON(boundaries, {
      style: (feature) => polygonStyle(byName[feature.properties.shapeName], false),
      onEachFeature: (feature, layer) => {
        const place = byName[feature.properties.shapeName];
        if (!place) {
          return;
        }
        layer.bindTooltip(`${place.name} · ${place.scores.overall}`, {
          sticky: true,
          className: "tunisia-score-tip",
        });
        layer.on("mouseover", () => layer.setStyle(polygonStyle(place, true)));
        layer.on("mouseout", () => layer.setStyle(polygonStyle(place, state.selected && state.selected.id === place.id)));
        layer.on("click", () => stopAndChoose(place, [data.country, place]));
      },
    }).addTo(map);

    layers.cities = window.L.layerGroup();
    layers.neighbourhoods = window.L.layerGroup();
    layers.nodes = window.L.layerGroup();
    data.governorates.forEach((governorate) => {
      const city = governorate.city;
      const neighbourhood = city.neighbourhood;
      marker(layers.cities, city, [data.country, governorate, city], 8, governorate.scores.overall);
      marker(layers.neighbourhoods, neighbourhood, [data.country, governorate, city, neighbourhood], neighbourhood.live ? 11 : 8, governorate.scores.overall);
      neighbourhood.nodes.forEach((node) => {
        nodeMarker(node, [data.country, governorate, city, neighbourhood, node]);
      });
    });
    data.registered.placed.forEach((site) => {
      const icon = window.L.divIcon({
        className: "tunisia-pin tunisia-pin-registered",
        html: `<span>${KIND[site.kind] || "•"}</span>`,
        iconSize: [36, 36],
        iconAnchor: [18, 18],
      });
      window.L.marker([site.lat, site.lng], { icon })
        .bindTooltip(`${site.name} · registered`, { direction: "top", offset: [0, -12] })
        .on("click", () => stopAndChoose(site, [data.country, site]))
        .addTo(layers.nodes);
    });
    map.on("zoomend", syncLayers);
    document.querySelector("#tn-scenario").textContent = `${data.scenario.replaceAll("_", " ")} · hour ${data.hour} · simulated`;
    document.querySelector("#tn-credit").textContent = data.boundary_note;
    choose(data.country, [data.country]);
    syncLayers();
  }

  function polygonStyle(place, strong) {
    const score = place ? place.scores.overall : 50;
    const zoom = map ? map.getZoom() : 6.6;
    const base = zoom >= 13 ? 0.2 : zoom >= 9 ? 0.4 : 0.62;
    return {
      color: strong ? "#f4efe6" : "rgba(244, 239, 230, 0.7)",
      weight: strong ? 2.5 : 1,
      fillColor: color(score),
      fillOpacity: strong ? Math.min(0.78, base + 0.12) : base,
    };
  }

  function marker(group, place, path, radius, score) {
    window.L.circleMarker([place.lat, place.lng], {
      radius,
      color: "#f4efe6",
      weight: 2,
      fillColor: color(score),
      fillOpacity: 0.95,
    }).bindTooltip(place.name, { direction: "top", offset: [0, -4] })
      .on("click", () => stopAndChoose(place, path))
      .addTo(group);
  }

  function nodeMarker(node, path) {
    const icon = window.L.divIcon({
      className: `tunisia-pin${node.live ? " tunisia-pin-live" : ""}`,
      html: `<span>${KIND[node.kind] || "•"}</span><small>${Math.round(node.scores.overall)}</small>`,
      iconSize: [46, 46],
      iconAnchor: [23, 23],
    });
    window.L.marker([node.lat, node.lng], { icon, zIndexOffset: node.live ? 500 : 0 })
      .bindTooltip(`${node.name} · ${node.scores.overall}`, { direction: "top", offset: [0, -16] })
      .on("click", () => stopAndChoose(node, path))
      .addTo(layers.nodes);
  }

  function syncLayers() {
    if (!map) {
      return;
    }
    const zoom = map.getZoom();
    toggle(layers.cities, zoom >= 8 && zoom < 12.4);
    toggle(layers.neighbourhoods, zoom >= 12 && zoom < 15.2);
    toggle(layers.nodes, zoom >= 14.6);
    if (polygons && state.data) {
      polygons.eachLayer((layer) => {
        const governorate = state.data.governorates.find((item) => item.name === layer.feature.properties.shapeName);
        const on = state.path.some((item) => governorate && item.id === governorate.id);
        layer.setStyle(polygonStyle(governorate, on));
      });
    }
  }

  function toggle(layer, on) {
    const present = map.hasLayer(layer);
    if (on && !present) {
      layer.addTo(map);
    }
    if (!on && present) {
      map.removeLayer(layer);
    }
  }

  function stopAndChoose(place, path) {
    state.token += 1;
    choose(place, path);
  }

  function choose(place, path) {
    state.selected = place;
    state.path = path;
    if (map && place.lat !== undefined) {
      map.flyTo([place.lat, place.lng], place.zoom, { duration: reduced ? 0 : 0.85 });
    }
    if (polygons) {
      polygons.eachLayer((layer) => {
        const name = layer.feature.properties.shapeName;
        const governorate = state.data.governorates.find((item) => item.name === name);
        const on = path.some((item) => item.id === governorate.id);
        layer.setStyle(polygonStyle(governorate, on));
      });
    }
    renderPanel(place, path);
  }

  function renderPanel(place, path) {
    const panel = document.querySelector("#tn-panel");
    const country = place.level === "country";
    panel.replaceChildren();
    const crumbs = el("nav", "tunisia-crumbs");
    path.forEach((item, index) => {
      if (index) {
        crumbs.append(el("span", "", "›"));
      }
      const button = el("button", "", item.name);
      button.type = "button";
      button.addEventListener("click", () => stopAndChoose(item, path.slice(0, index + 1)));
      crumbs.append(button);
    });
    panel.append(crumbs);
    panel.append(el("p", "tunisia-panel-kicker", country ? "KIZUNA Resilience Index" : place.level));
    panel.append(el("h2", "", place.name));
    if (place.scores) {
      const score = el("p", "tunisia-index");
      score.append(el("strong", "", place.scores.overall.toFixed(1)), el("span", "", "/ 100"));
      panel.append(score);
      panel.append(el("p", "tunisia-index-caption", country ? "National score, simulated" : "Overall resilience, simulated"));
      PILLARS.forEach(([key, label]) => {
        if (place.scores[key] === undefined) {
          return;
        }
        const row = el("div", "tunisia-pillar");
        const head = el("div", "tunisia-pillar-head");
        head.append(el("span", "", label), el("span", "", place.scores[key].toFixed(1)));
        const track = el("div", "tunisia-track");
        const fill = el("div", "tunisia-fill");
        fill.style.width = `${place.scores[key]}%`;
        fill.style.background = color(place.scores[key]);
        track.append(fill);
        row.append(head, track);
        panel.append(row);
      });
    }
    if (place.note) {
      panel.append(el("p", "tunisia-note", place.note));
    }
    if (place.level === "node") {
      panel.append(el("p", "tunisia-note", `${place.kind}. ${place.live ? "Live simulation clock." : "Demo node."}`));
    }
    if (country) {
      const registered = state.data.registered;
      if (registered.unplaced.length || registered.placed.length) {
        panel.append(el("p", "tunisia-panel-kicker", "Your sites"));
      }
      registered.placed.forEach((site) => {
        const button = el("button", "tunisia-site", `${site.name} · on the map`);
        button.type = "button";
        button.addEventListener("click", () => stopAndChoose(site, [state.data.country, site]));
        panel.append(button);
      });
      registered.unplaced.forEach((site) => panel.append(el("p", "tunisia-note", `${site.name}: ${site.note}`)));
      const rules = el("ul", "tunisia-rules");
      state.data.rules.forEach((text) => rules.append(el("li", "", text)));
      panel.append(rules);
    }
  }

  document.querySelector("#tn-country").addEventListener("click", () => {
    if (state.data) {
      stopAndChoose(state.data.country, [state.data.country]);
    }
  });

  document.querySelector("#tn-descend").addEventListener("click", async () => {
    if (!state.data) {
      return;
    }
    const button = document.querySelector("#tn-descend");
    const token = ++state.token;
    button.disabled = true;
    const governorate = state.data.governorates.find((item) => item.id === state.data.focus.governorate);
    const city = governorate.city;
    const neighbourhood = city.neighbourhood;
    const node = neighbourhood.nodes.find((item) => item.id === state.data.focus.node);
    const steps = [
      [state.data.country, [state.data.country]],
      [governorate, [state.data.country, governorate]],
      [city, [state.data.country, governorate, city]],
      [neighbourhood, [state.data.country, governorate, city, neighbourhood]],
      [node, [state.data.country, governorate, city, neighbourhood, node]],
    ];
    for (const [place, path] of steps) {
      if (token !== state.token) {
        break;
      }
      choose(place, path);
      await sleep(reduced ? 0 : 1050);
    }
    button.disabled = false;
  });

  load();
})();
