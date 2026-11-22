(() => {
  const panels = document.querySelector("#brain-panels");
  if (!panels) {
    return;
  }
  const url = panels.getAttribute("data-panels-url");
  const errorNode = document.querySelector("#brain-error");
  const advance = document.querySelector("#brain-advance");

  const showError = (message) => {
    if (!errorNode) {
      return;
    }
    errorNode.hidden = !message;
    errorNode.textContent = message || "";
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

  const refresh = async () => {
    try {
      const response = await fetch(url, { cache: "no-store", headers: { Accept: "text/html" } });
      if (!response.ok) {
        showError("The Brain could not read the system state.");
        return;
      }
      panels.innerHTML = await response.text();
      showError("");
    } catch (error) {
      showError("The Brain could not read the system state.");
    }
  };

  if (advance) {
    advance.addEventListener("click", async () => {
      advance.disabled = true;
      try {
        const response = await fetch("/api/simulation/advance/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": readCookie("csrftoken"),
          },
          body: JSON.stringify({ steps: 1 }),
        });
        if (!response.ok) {
          showError("The simulation did not advance.");
          return;
        }
        await refresh();
      } finally {
        advance.disabled = false;
      }
    });
  }

  window.addEventListener("kizuna-state", (event) => {
    const detail = event.detail || {};
    const mark = `${detail.hour}|${detail.scenario}|${detail.crisis_state}`;
    if (panels.dataset.seen === mark) {
      return;
    }
    panels.dataset.seen = mark;
    refresh();
  });
})();
