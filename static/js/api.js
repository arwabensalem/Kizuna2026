function getCookie(name) {
  const prefix = `${name}=`;
  for (const part of document.cookie.split(";")) {
    const item = part.trim();
    if (item.startsWith(prefix)) {
      return decodeURIComponent(item.slice(prefix.length));
    }
  }
  return "";
}

export async function api(path, { method = "GET", body } = {}) {
  const headers = { Accept: "application/json" };
  const options = { method, headers, credentials: "same-origin" };

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    const csrf = getCookie("csrftoken");
    if (csrf) {
      headers["X-CSRFToken"] = csrf;
    }
    options.body = JSON.stringify(body);
  }

  const response = await fetch(path, options);
  const text = await response.text();
  if (!response.ok) {
    throw new Error(text || response.statusText);
  }
  if (!text) {
    return null;
  }
  return JSON.parse(text);
}
