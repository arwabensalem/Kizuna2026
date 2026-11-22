const path = window.location.pathname;

const NAV_PREFIXES = {
  dashboard: "/dashboard", simulation: "/simulation", ai: "/ai", autopilot: "/autopilot",
  weather: "/weather", twin: "/twin", brain: "/brain", "crisis-day": "/crisis/day",
  network: "/network", tunisia: "/tunisia", passport: "/passport", league: "/league",
  market: "/market", homes: "/homes", farms: "/farms", business: "/business",
  demo: "/demo", profile: "/accounts/profile", login: "/accounts/login",
  register: "/accounts/register",
};

document.querySelectorAll("[data-nav]").forEach((link) => {
  const key = link.getAttribute("data-nav");
  const active = (key === "home" && path === "/")
    || (key === "crisis" && path === "/crisis/")
    || (NAV_PREFIXES[key] && path.startsWith(NAV_PREFIXES[key]));
  if (active) {
    link.classList.add("active");
    link.setAttribute("aria-current", "page");
    // Si la page est dans le menu « Plus », on le signale sur le bouton.
    const more = link.closest(".dropdown")?.querySelector("[data-nav-more]");
    if (more) more.classList.add("active");
  }
});

// Confirmation avant toute suppression : chaque formulaire qui envoie vers
// une adresse de suppression demande d'abord « Êtes-vous sûr ? ».
(function () {
  const modalEl = document.getElementById("kz-confirm");
  if (!modalEl || !window.bootstrap) return;
  const modal = new bootstrap.Modal(modalEl);
  const text = document.getElementById("kz-confirm-text");
  const yes = document.getElementById("kz-confirm-yes");
  let pending = null;

  function isDelete(form) {
    if (form.hasAttribute("data-confirm")) return true;
    const action = form.getAttribute("action") || "";
    return form.method.toLowerCase() === "post" && /delete|supprim/i.test(action);
  }

  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.dataset.confirmed === "yes" || !isDelete(form)) return;
    event.preventDefault();
    pending = form;
    text.textContent = form.getAttribute("data-confirm")
      || "Voulez-vous vraiment supprimer cet élément ? Cette action est définitive.";
    modal.show();
  }, true);

  yes.addEventListener("click", () => {
    if (!pending) return;
    pending.dataset.confirmed = "yes";
    modal.hide();
    pending.requestSubmit ? pending.requestSubmit() : pending.submit();
  });
  modalEl.addEventListener("shown.bs.modal", () => modalEl.querySelector("[data-bs-dismiss]").focus());
})();

// Mots techniques de la simulation affichés en français (même liste que
// apps/dashboard/templatetags/kizuna_fr.py).
(function () {
  const build = (words) => {
    const keys = Object.keys(words).sort((a, b) => b.length - a.length)
      .map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    const re = new RegExp("(?<![\\p{L}\\p{N}_])(" + keys.join("|") + ")(?![\\p{L}\\p{N}_])", "gu");
    return (value) => (value == null ? value : String(value).replace(re, (m) => words[m]));
  };
  window.kzFr = build({"COMBINED_CRISIS": "Crise combinée", "POWER_OUTAGE": "Coupure de courant", "HEAVY_RAIN": "Fortes pluies", "REAL_WEATHER": "Météo réelle", "HEATWAVE": "Canicule", "DROUGHT": "Sécheresse", "NORMAL": "Normal", "WATCH": "Vigilance", "ALERT": "Alerte", "CRISIS": "Crise", "CONTAINED": "maîtrisée", "ACTIVE": "en cours", "AVAILABLE": "Disponible", "OUT": "Coupé", "HIGH": "Bon", "MEDIUM": "Moyen", "LOW": "Faible", "Up": "En service", "Down": "Coupé", "On": "En marche", "Off": "À l’arrêt", "Scenario": "Situation :", "Water availability": "Eau disponible", "Solar production": "Production solaire", "Soil moisture": "Humidité du sol", "Rain probability": "Risque de pluie", "Rainfall": "Pluie", "Temperature": "Température", "Grid": "Réseau électrique", "home tank": "réservoir de la maison", "power reserve available": "réserve d’énergie disponible", "no power reserve": "pas de réserve d’énergie", "crops watered or soil": "cultures arrosées ou sol", "and the pump is off": "et pompe à l’arrêt"});
  window.kzFrFlow = build({"Battery": "Batterie", "Home": "Maison", "Farm": "Ferme", "Business": "Atelier", "Workshop": "Atelier", "Tank": "Réservoir", "Solar": "Solaire", "Grid": "Réseau", "Neighbourhood": "Quartier", "Neighborhood": "Quartier"});
})();
