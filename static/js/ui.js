// KIZUNA · habillage commun de toutes les pages.
// 1. Transforme le titre de chaque page (sur-titre, titre, chapeau) en bandeau.
// 2. Fait apparaître les cartes en douceur et anime les chiffres.
// 3. Ombre du menu au défilement.
// Sans JavaScript, la page garde sa mise en page simple : rien ne se perd.

(function () {
  const main = document.getElementById("contenu");
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function isHeaderBlock(el) {
    if (!el || el.nodeType !== 1) return false;
    if (el.matches(".kicker, h1, .lead, .kz-help, img.kz-hero-logo")) return true;
    // Bloc d'en-tête « titre + boutons » : un div qui contient le h1 de la page.
    return el.tagName === "DIV" && !!el.querySelector(":scope > h1, :scope > div > h1, :scope > div > p.kicker");
  }

  function buildHero() {
    if (!main || !main.classList.contains("container")) return;
    if (document.querySelector(".kz-page-hero, .kz-hero")) return;
    const children = [...main.children];
    const alerts = [];
    let index = 0;
    while (index < children.length && (children[index].matches(".alert[role=status], style, script, link") )) {
      if (children[index].matches(".alert")) alerts.push(children[index]);
      index += 1;
    }
    const picked = [];
    let sawTitle = false;
    // Tableau de bord : <div><header>titre + actions</header>…</div>
    const wrapper = children[index];
    const innerHeader = wrapper && wrapper.querySelector(":scope > header");
    if (wrapper && innerHeader && wrapper.firstElementChild === innerHeader && innerHeader.querySelector("h1")) {
      picked.push(innerHeader);
      sawTitle = true;
      index = children.length;
    }
    for (; index < children.length; index += 1) {
      const el = children[index];
      if (el.matches("style, script, template")) continue;
      if (isHeaderBlock(el)) {
        picked.push(el);
        if (el.matches("h1") || el.querySelector("h1")) sawTitle = true;
        continue;
      }
      // Un court paragraphe juste après le titre sert de chapeau.
      if (sawTitle && el.tagName === "P" && picked.length < 5 && el.textContent.length < 420 && !el.querySelector("form, table")) {
        el.classList.add("lead");
        picked.push(el);
        continue;
      }
      break;
    }
    if (!sawTitle) return;

    const hero = document.createElement("header");
    hero.className = "kz-page-hero kz-auto-hero";
    const inner = document.createElement("div");
    inner.className = "container kz-page-hero-inner";
    hero.appendChild(inner);
    picked.forEach((el) => {
      inner.appendChild(el);
      if (el.matches(".kicker")) el.classList.add("kz-eyebrow");
      el.querySelectorAll(":scope p.kicker").forEach((k) => k.classList.add("kz-eyebrow"));
      if (el.matches("h1")) el.classList.add("kz-page-title");
      el.querySelectorAll("h1").forEach((h) => h.classList.add("kz-page-title"));
    });
    main.parentNode.insertBefore(hero, main);
    alerts.reverse().forEach((alert) => main.prepend(alert));
    main.classList.add("kz-after-hero");
    document.body.classList.add("has-hero");
  }

  function reveal() {
    const items = document.querySelectorAll(
      "#contenu .placeholder-card, #contenu .kz-tile, #contenu .card, #contenu .list-group, #contenu .table-responsive, #contenu .kz-card, #contenu .kz-bill, #contenu .kz-tip"
    );
    if (reduce || !("IntersectionObserver" in window)) return;
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("kz-in");
        observer.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -40px 0px" });
    items.forEach((el, i) => {
      el.classList.add("kz-reveal");
      el.style.transitionDelay = `${Math.min(i % 6, 5) * 60}ms`;
      observer.observe(el);
    });
  }

  function countUp() {
    if (reduce) return;
    document.querySelectorAll(".metric-value, .dash-value, .kz-bill-amount").forEach((node) => {
      const textNode = [...node.childNodes].find((n) => n.nodeType === 3 && n.textContent.trim());
      if (!textNode) return;
      const original = textNode.textContent;
      const raw = original.trim();
      const match = raw.match(/^(≈\s*)?(-?\d+(?:[.,]\d+)?)(.*)$/);
      if (!match) return;
      const target = parseFloat(match[2].replace(",", "."));
      if (!Number.isFinite(target) || target === 0) return;
      const decimals = (match[2].split(/[.,]/)[1] || "").length;
      const prefix = match[1] || "";
      const suffix = match[3] || "";
      const start = performance.now();
      function step(now) {
        const t = Math.min(1, (now - start) / 900);
        const v = target * (1 - Math.pow(1 - t, 3));
        textNode.textContent = `${prefix}${v.toFixed(decimals).replace(".", ",")}${suffix} `;
        if (t < 1) requestAnimationFrame(step);
        else textNode.textContent = original;
      }
      requestAnimationFrame(step);
    });
  }

  function navShadow() {
    const nav = document.querySelector(".kz-nav");
    if (!nav) return;
    const update = () => nav.classList.toggle("is-scrolled", window.scrollY > 8);
    window.addEventListener("scroll", update, { passive: true });
    update();
  }

  // Vagues animées et pictos eau, énergie, agriculture au bas de chaque bandeau.
  function decorateHeroes() {
    document.querySelectorAll(".kz-page-hero").forEach((hero) => {
      if (hero.querySelector(".kz-hero-waves")) return;
      const deco = document.createElement("div");
      deco.className = "kz-hero-deco";
      deco.setAttribute("aria-hidden", "true");
      const icons = hero.querySelector(".btn, form, button") ? "" :
        '<span class="kz-float-ico kz-ico-water"><svg viewBox="0 0 24 24"><path d="M12 2.5C8 8 5.5 11.4 5.5 14.6a6.5 6.5 0 0 0 13 0C18.5 11.4 16 8 12 2.5z"/></svg></span>' +
        '<span class="kz-float-ico kz-ico-energy"><svg viewBox="0 0 24 24"><path d="M13.5 2 5 13.5h6L9.5 22 19 9.8h-6.2z"/></svg></span>' +
        '<span class="kz-float-ico kz-ico-agri"><svg viewBox="0 0 24 24"><path d="M12 22v-8.5C12 8 15.5 4 21 3.5c-.3 5.6-3.6 9.3-9 10M12 16C12 11.5 9 8.4 3.5 8c.2 4.6 3.4 7.6 8.5 8"/></svg></span>';
      deco.innerHTML = icons +
        '<svg class="kz-hero-waves" viewBox="0 0 1440 90" preserveAspectRatio="none">' +
        '<path class="kz-hw kz-hw-1" d="M0 50 C180 20 360 80 540 50 S900 20 1080 50 S1440 80 1620 50 S1980 20 2160 50 V90 H0 Z"/>' +
        '<path class="kz-hw kz-hw-2" d="M0 62 C200 40 400 84 600 62 S1000 40 1200 62 S1600 84 1800 62 S2200 40 2400 62 V90 H0 Z"/>' +
        "</svg>";
      hero.appendChild(deco);
      hero.classList.add("kz-hero-decorated");
    });
  }

  // Jeton de sécurité toujours à jour : quand on change de compte dans un autre
  // onglet, le jeton d'une page déjà ouverte devient périmé (erreur 403).
  // Juste avant l'envoi, on reprend la valeur actuelle du cookie.
  function freshCsrf() {
    document.addEventListener("submit", (event) => {
      const form = event.target;
      if (!(form instanceof HTMLFormElement) || (form.method || "").toLowerCase() !== "post") return;
      const field = form.querySelector("input[name=csrfmiddlewaretoken]");
      const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
      if (field && match) field.value = decodeURIComponent(match[1]);
    }, true);
    // Page revenue du cache du navigateur (bouton Retour) : on la recharge.
    window.addEventListener("pageshow", (event) => {
      if (event.persisted && document.querySelector("form[method=post] input[name=csrfmiddlewaretoken]")) window.location.reload();
    });
  }

  try {
    freshCsrf();
    buildHero();
    decorateHeroes();
    reveal();
    countUp();
    navShadow();
  } finally {
    document.documentElement.classList.add("kz-ready");
  }
})();
