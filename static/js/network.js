(() => {
  const svg = document.querySelector("#net-graph");
  if (!svg) {
    return;
  }
  const NS = "http://www.w3.org/2000/svg";
  const RADIUS = 26;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const layers = {
    edges: svg.querySelector("#net-edges"),
    particles: svg.querySelector("#net-particles"),
    labels: svg.querySelector("#net-flow-labels"),
    nodes: svg.querySelector("#net-nodes"),
  };
  const errorNode = document.querySelector("#net-error");
  const SYMBOLS = {
    rain: "Rn", roof: "Rf", tank: "Tk", garden: "Gd", solar: "So", home: "Hm",
    battery: "Bt", mains: "Wt", grid: "Gr", pump: "Pm", farm: "Fm", business: "Bz",
  };
  const state = { data: null, live: true, hour: null, resource: "all", exchangeOnly: false, selected: null };
  let particles = [];
  let frame = null;

  const make = (tag, attrs = {}, text) => {
    const node = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    if (text !== undefined) {
      node.textContent = text;
    }
    return node;
  };

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

  const formatTime = (iso) => {
    const date = new Date(iso);
    return date.toLocaleString([], { weekday: "short", hour: "2-digit", minute: "2-digit" });
  };

  const quantity = (flow) => (flow.unit === "Wh" && flow.quantity >= 1000
    ? `${(flow.quantity / 1000).toFixed(1)} kWh`
    : `${flow.quantity.toLocaleString()} ${flow.unit}`);

  const edgeKey = (source, destination, resource) => `${source}>${destination}>${resource}`;

  const visible = (flow) => (state.resource === "all" || flow.resource === state.resource)
    && (!state.exchangeOnly || flow.kind === "exchange");

  async function load() {
    const query = state.live || state.hour === null ? "" : `?hour=${state.hour}`;
    try {
      const response = await fetch(`/api/network/${query}`, { cache: "no-store" });
      const body = await response.json();
      if (!response.ok) {
        showError(body.detail || "The network could not be loaded.");
        return;
      }
      showError("");
      state.data = body;
      state.hour = body.hour;
      render();
    } catch (error) {
      showError("The network could not be loaded.");
    }
  }

  function geometry(nodes, edge) {
    const a = nodes[edge.source];
    const b = nodes[edge.destination];
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const length = Math.hypot(dx, dy) || 1;
    const ux = dx / length;
    const uy = dy / length;
    const bend = edge.exchange ? 46 : 14;
    const cx = (a.x + b.x) / 2 - uy * bend;
    const cy = (a.y + b.y) / 2 + ux * bend;
    const start = { x: a.x + ux * RADIUS, y: a.y + uy * RADIUS };
    const end = { x: b.x - ux * (RADIUS + 4), y: b.y - uy * (RADIUS + 4) };
    return { d: `M${start.x},${start.y} Q${cx},${cy} ${end.x},${end.y}`, mid: { x: (start.x + 2 * cx + end.x) / 4, y: (start.y + 2 * cy + end.y) / 4 } };
  }

  function render() {
    const data = state.data;
    const nodes = Object.fromEntries(data.nodes.map((node) => [node.key, node]));
    const flows = new Map(data.flows.map((flow) => [edgeKey(flow.source, flow.destination, flow.resource), flow]));
    const max = { water: 1, energy: 1 };
    data.flows.forEach((flow) => {
      max[flow.resource] = Math.max(max[flow.resource], flow.quantity);
    });

    document.querySelector("#net-hour").textContent = `Hour ${data.hour}`;
    document.querySelector("#net-time").textContent = `${formatTime(data.timestamp)} · ${data.scenario.replaceAll("_", " ")} · simulated`;
    document.querySelector("#net-prev").disabled = data.hour <= data.hours[0];
    document.querySelector("#net-next").disabled = data.hour >= data.latest_hour;
    const live = document.querySelector("#net-live");
    live.classList.toggle("active", state.live);
    live.setAttribute("aria-pressed", state.live ? "true" : "false");

    layers.edges.replaceChildren();
    layers.labels.replaceChildren();
    particles = [];
    layers.particles.replaceChildren();
    const placed = [];

    data.edges.forEach((edge) => {
      const flow = flows.get(edgeKey(edge.source, edge.destination, edge.resource));
      const shape = geometry(nodes, edge);
      const active = flow && visible(flow);
      const share = active ? flow.quantity / max[flow.resource] : 0;
      const path = make("path", {
        d: shape.d,
        class: `net-edge net-edge-${edge.resource}${edge.exchange ? " net-edge-exchange" : ""}${active ? " active" : ""}`,
        "stroke-width": active ? (2 + share * 4).toFixed(1) : 1.5,
      });
      if (active) {
        const title = make("title", {}, `${flow.source_label} → ${flow.destination_label}: ${quantity(flow)} ${flow.resource}`);
        path.append(title);
      }
      layers.edges.append(path);
      if (!active) {
        return;
      }
      const spot = clearSpot(placed, nodes, shape.mid.x, shape.mid.y - 6);
      const label = make("text", { x: spot.x, y: spot.y, class: `net-flow-label net-flow-label-${flow.resource}` }, quantity(flow));
      layers.labels.append(label);
      if (reduced) {
        return;
      }
      const length = path.getTotalLength();
      const count = Math.max(2, Math.min(9, Math.round(2 + share * 7)));
      for (let index = 0; index < count; index += 1) {
        const dot = make("circle", {
          r: flow.kind === "exchange" ? 5 : 4,
          class: `net-particle net-particle-${flow.resource}${flow.kind === "exchange" ? " net-particle-exchange" : ""}`,
        });
        layers.particles.append(dot);
        particles.push({ dot, path, length, offset: index / count, speed: 0.12 + share * 0.18 });
      }
    });

    layers.nodes.replaceChildren();
    data.nodes.forEach((node) => {
      const group = make("g", {
        class: `net-node net-node-${node.level}${state.selected === node.key ? " selected" : ""}`,
        transform: `translate(${node.x},${node.y})`,
        tabindex: "0",
        role: "button",
        "aria-label": `${node.label}: ${node.value}`,
      });
      group.append(
        make("circle", { r: RADIUS, class: `net-node-body net-node-${node.type}` }),
        make("text", { class: "net-node-symbol", y: 6 }, SYMBOLS[node.type] || "•"),
        make("text", { class: "net-node-label", y: RADIUS + 15 }, node.label),
        make("text", { class: "net-node-value", y: RADIUS + 28 }, node.value),
      );
      const choose = () => {
        state.selected = node.key;
        render();
      };
      group.addEventListener("click", choose);
      group.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          choose();
        }
      });
      layers.nodes.append(group);
    });

    renderNode(nodes);
    renderTotals(data.totals);
    renderTables(data);
    if (!frame && particles.length) {
      frame = window.requestAnimationFrame(animate);
    }
  }

  function clearSpot(placed, nodes, x, y) {
    const blocked = (px, py) => placed.some((item) => Math.hypot(item.x - px, item.y - py) < 36)
      || Object.values(nodes).some((node) => Math.hypot(node.x - px, node.y - py) < 34);
    const tries = [
      { x, y },
      { x, y: y - 18 },
      { x, y: y + 18 },
      { x: x + 30, y },
      { x: x - 30, y },
      { x, y: y - 34 },
    ];
    const spot = tries.find((item) => !blocked(item.x, item.y)) || tries[0];
    placed.push(spot);
    return spot;
  }

  function animate(time) {
    const seconds = time / 1000;
    particles.forEach((item) => {
      const t = (item.offset + seconds * item.speed) % 1;
      const point = item.path.getPointAtLength(t * item.length);
      item.dot.setAttribute("cx", point.x);
      item.dot.setAttribute("cy", point.y);
    });
    frame = particles.length ? window.requestAnimationFrame(animate) : null;
  }

  function renderNode(nodes) {
    const panel = document.querySelector("#net-node");
    const node = nodes[state.selected];
    if (!node) {
      return;
    }
    const flows = state.data.flows;
    const incoming = flows.filter((flow) => flow.destination === node.key);
    const outgoing = flows.filter((flow) => flow.source === node.key);
    panel.replaceChildren(el("h2", "", "Node status"));
    const head = el("div", "network-node-head");
    head.append(el("strong", "", node.label), el("span", `network-level network-level-${node.level}`, node.level.toUpperCase()));
    panel.append(head);
    panel.append(el("p", "network-node-value", node.value));
    panel.append(el("p", "text-muted", `${node.site} · ${node.type}. ${node.detail}`));
    const list = (title, items, pick) => {
      panel.append(el("p", "network-node-sub", title));
      if (!items.length) {
        panel.append(el("p", "text-muted small", "None this hour."));
        return;
      }
      const ul = el("ul", "network-node-flows");
      items.forEach((flow) => ul.append(el("li", `network-flow-${flow.resource}`, `${pick(flow)} · ${quantity(flow)} ${flow.resource}${flow.kind === "exchange" ? " · Exchange" : ""}`)));
      panel.append(ul);
    };
    list("Incoming", incoming, (flow) => `from ${flow.source_label}`);
    list("Outgoing", outgoing, (flow) => `to ${flow.destination_label}`);
  }

  function renderTotals(totals) {
    const rows = [
      ["Local energy", `${(totals.energy_local_wh / 1000).toFixed(2)} kWh`],
      ["Exchange energy", `${(totals.energy_exchanged_wh / 1000).toFixed(2)} kWh`],
      ["From the grid", `${(totals.energy_grid_wh / 1000).toFixed(2)} kWh`],
      ["Solar still curtailed", `${(totals.curtailed_wh / 1000).toFixed(2)} kWh`],
      ["Unserved load", `${(totals.unmet_wh / 1000).toFixed(2)} kWh`],
      ["Water moved", `${totals.water_moved_l} L`],
      ["Exchange water", `${totals.water_exchanged_l} L`],
      ["Rain captured (estimate)", `${totals.rain_captured_l} L`],
    ];
    const list = document.querySelector("#net-totals");
    list.replaceChildren();
    rows.forEach(([term, value]) => list.append(el("dt", "", term), el("dd", "", value)));
  }

  function renderTables(data) {
    const body = document.querySelector("#net-flows");
    body.replaceChildren();
    const shown = data.flows.filter(visible);
    if (!shown.length) {
      const row = el("tr");
      const cell = el("td", "text-muted", "No flow matches the filter this hour.");
      cell.colSpan = 7;
      row.append(cell);
      body.append(row);
    }
    shown.forEach((flow) => {
      const row = el("tr", flow.kind === "exchange" ? "network-row-exchange" : "");
      row.append(
        el("td", `network-flow-${flow.resource}`, flow.resource),
        el("td", "", flow.source_label),
        el("td", "", flow.destination_label),
        el("td", "text-end", quantity(flow)),
        el("td", "", flow.kind === "exchange" ? "KIZUNA Exchange" : flow.kind),
        el("td", "", formatTime(flow.timestamp)),
        el("td", "small", flow.note),
      );
      body.append(row);
    });

    const history = document.querySelector("#net-history");
    history.replaceChildren();
    const exchanges = data.history.filter((flow) => flow.kind === "exchange");
    if (!exchanges.length) {
      const row = el("tr");
      const cell = el("td", "text-muted", "No exchange in the last 12 simulated hours. Exchange starts when a battery is full or the farm tank runs low.");
      cell.colSpan = 5;
      row.append(cell);
      history.append(row);
    }
    exchanges.forEach((flow) => {
      const row = el("tr");
      row.append(
        el("td", "", `Hour ${flow.hour} · ${formatTime(flow.timestamp)}`),
        el("td", `network-flow-${flow.resource}`, flow.resource),
        el("td", "", flow.source_label),
        el("td", "", flow.destination_label),
        el("td", "text-end", quantity(flow)),
      );
      history.append(row);
    });

    const assumptions = document.querySelector("#net-assumptions");
    if (!assumptions.children.length) {
      data.assumptions.forEach((text) => assumptions.append(el("li", "", text)));
    }
  }

  document.querySelectorAll("[data-resource]").forEach((button) => {
    button.addEventListener("click", () => {
      state.resource = button.getAttribute("data-resource");
      document.querySelectorAll("[data-resource]").forEach((other) => other.classList.toggle("active", other === button));
      if (state.data) {
        render();
      }
    });
  });

  document.querySelector("#net-exchange").addEventListener("change", (event) => {
    state.exchangeOnly = event.target.checked;
    if (state.data) {
      render();
    }
  });

  document.querySelector("#net-prev").addEventListener("click", () => {
    state.live = false;
    state.hour = Math.max(0, state.hour - 1);
    load();
  });

  document.querySelector("#net-next").addEventListener("click", () => {
    state.hour += 1;
    state.live = state.data && state.hour >= state.data.latest_hour;
    load();
  });

  document.querySelector("#net-live").addEventListener("click", () => {
    state.live = true;
    load();
  });

  document.querySelector("#net-advance").addEventListener("click", async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      const response = await fetch("/api/simulation/advance/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": readCookie("csrftoken") },
        body: JSON.stringify({ steps: 1 }),
      });
      if (!response.ok) {
        showError("The simulation did not advance.");
        return;
      }
      state.live = true;
      await load();
    } finally {
      button.disabled = false;
    }
  });

  window.addEventListener("kizuna-state", () => {
    if (state.live) {
      load();
    }
  });

  load();
})();
