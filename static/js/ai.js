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
  const node = document.querySelector("#ai-error");
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

function resultText(payload) {
  if (typeof payload.anomaly === "boolean") {
    const label = payload.anomaly ? "Anomaly" : "Not an anomaly";
    return `${label} · score ${payload.score}`;
  }
  const unit = payload.unit ? ` ${payload.unit}` : "";
  return `${payload.prediction}${unit}`;
}

document.querySelectorAll("[data-ai-form]").forEach((form) => {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    showError("");
    const body = {};
    for (const field of form.querySelectorAll("input, select")) {
      if (!field.name || field.name === "csrfmiddlewaretoken") {
        continue;
      }
      body[field.name] = field.type === "number" ? Number(field.value) : field.value;
    }
    const button = form.querySelector("button");
    button.disabled = true;
    try {
      const response = await fetch(form.getAttribute("data-endpoint"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": readCookie("csrftoken"),
        },
        body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Request failed.");
      }
      form.querySelector("[data-ai-result]").textContent = resultText(payload);
    } catch (error) {
      showError(error.message);
    } finally {
      button.disabled = false;
    }
  });
});
