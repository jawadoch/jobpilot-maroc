/* JobPilot Maroc — JavaScript minimal (aucune dépendance hors Bootstrap / Chart.js). */
(function () {
  "use strict";

  // --- Confirmation des actions destructives : <form data-confirm="..."> ---------------
  var modalEl = document.getElementById("confirmModal");
  var pendingForm = null;
  if (modalEl && window.bootstrap) {
    var modal = new bootstrap.Modal(modalEl);
    document.addEventListener("submit", function (event) {
      var form = event.target;
      if (!form.dataset || !form.dataset.confirm || form.dataset.confirmed === "1") return;
      event.preventDefault();
      pendingForm = form;
      document.getElementById("confirmModalBody").textContent = form.dataset.confirm;
      modal.show();
    }, true);
    document.getElementById("confirmModalOk").addEventListener("click", function () {
      if (!pendingForm) return;
      pendingForm.dataset.confirmed = "1";
      modal.hide();
      if (pendingForm.requestSubmit) pendingForm.requestSubmit(); else pendingForm.submit();
    });
    modalEl.addEventListener("hidden.bs.modal", function () {
      if (pendingForm) pendingForm.dataset.confirmed = "";
      pendingForm = null;
    });
  }

  // --- Formulaire candidature : sections propres au secteur ------------------------------
  var sectorSelect = document.querySelector("[data-sector-select]");
  if (sectorSelect) {
    var categorySelect = document.getElementById("category");
    var applySector = function () {
      var sector = sectorSelect.value;
      document.querySelectorAll("[data-sector-section]").forEach(function (section) {
        section.hidden = section.dataset.sectorSection !== sector;
      });
    };
    sectorSelect.addEventListener("change", function () {
      if (categorySelect) {
        if (sectorSelect.value === "public" && categorySelect.value !== "concours") categorySelect.value = "concours";
        if (sectorSelect.value === "private" && categorySelect.value === "concours") categorySelect.value = "cdi";
      }
      applySector();
    });
    applySector();
  }

  // --- Envoi automatique des filtres (sélecteurs marqués data-autosubmit) -----------------
  document.querySelectorAll("[data-autosubmit]").forEach(function (el) {
    el.addEventListener("change", function () { el.form.submit(); });
  });

  // --- Onglets : conserver l'onglet actif dans l'URL -----------------------------------
  document.querySelectorAll('[data-bs-toggle="tab"][data-tab-name]').forEach(function (tab) {
    tab.addEventListener("shown.bs.tab", function () {
      var url = new URL(window.location.href);
      url.searchParams.set("onglet", tab.dataset.tabName);
      window.history.replaceState(null, "", url.toString());
    });
  });

  // --- Graphiques (Chart.js), données lues depuis <script type="application/json"> --------
  var dataEl = document.getElementById("chart-data");
  if (!dataEl || !window.Chart) return;
  var data = JSON.parse(dataEl.textContent);

  var PUBLIC = "#2a78d6", PRIVATE = "#eb6834", SINGLE = "#2a78d6";
  var INK = "#52514e", MUTED = "#898781", GRID = "#e1e0d9";
  Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", sans-serif';
  Chart.defaults.font.size = 12;
  Chart.defaults.color = INK;
  Chart.defaults.plugins.tooltip.backgroundColor = "#16202e";
  Chart.defaults.plugins.tooltip.padding = 8;
  Chart.defaults.maintainAspectRatio = false;
  Chart.defaults.animation = false;

  var fmt = new Intl.NumberFormat("fr-FR");
  var baseBar = { borderRadius: 4, borderSkipped: "start", maxBarThickness: 28, borderColor: "#ffffff", borderWidth: 0 };
  var axis = function (extra) {
    return Object.assign({ grid: { color: GRID, drawTicks: false }, border: { display: false },
      ticks: { color: MUTED, padding: 6 } }, extra || {});
  };
  var noGrid = { grid: { display: false }, border: { color: "#c3c2b7" }, ticks: { color: INK } };

  function render(id, config, hasData) {
    var canvas = document.getElementById(id);
    if (!canvas) return;
    var box = canvas.closest("[data-chart-box]");
    var total = (config.data.datasets || []).reduce(function (sum, ds) {
      return sum + ds.data.reduce(function (a, b) { return a + (b || 0); }, 0);
    }, 0);
    if (hasData === undefined ? !total : !hasData) {
      if (box) box.innerHTML = '<div class="empty-state small"><i class="bi bi-bar-chart" aria-hidden="true"></i>Pas encore de données à afficher.</div>';
      return;
    }
    new Chart(canvas, config);
  }

  // Candidatures par secteur (barres horizontales, couleur = secteur)
  if (data.sector) {
    render("chart-sector", {
      type: "bar",
      data: { labels: data.sector.labels, datasets: [Object.assign({ label: "Candidatures", data: data.sector.values,
        backgroundColor: [PUBLIC, PRIVATE] }, baseBar)] },
      options: { indexAxis: "y", plugins: { legend: { display: false } },
        scales: { x: axis({ beginAtZero: true, ticks: { precision: 0, color: MUTED } }), y: noGrid } },
    });
  }

  // Candidatures par statut (une seule série → une seule teinte, pas de légende)
  if (data.status) {
    render("chart-status", {
      type: "bar",
      data: { labels: data.status.labels, datasets: [Object.assign({ label: "Candidatures", data: data.status.values,
        backgroundColor: SINGLE }, baseBar)] },
      options: { indexAxis: "y", plugins: { legend: { display: false } },
        scales: { x: axis({ beginAtZero: true, ticks: { precision: 0, color: MUTED } }), y: noGrid } },
    });
  }

  // Envois mensuels, empilés par secteur (légende + couleurs fixes)
  if (data.monthly) {
    render("chart-monthly", {
      type: "bar",
      data: { labels: data.monthly.labels, datasets: [
        Object.assign({ label: "Public", data: data.monthly.public, backgroundColor: PUBLIC }, baseBar, { borderWidth: { top: 2 } }),
        Object.assign({ label: "Privé", data: data.monthly.private, backgroundColor: PRIVATE }, baseBar, { borderWidth: { top: 2 } }),
      ] },
      options: {
        plugins: { legend: { position: "top", align: "end", labels: { boxWidth: 10, boxHeight: 10, useBorderRadius: true, borderRadius: 2 } },
          tooltip: { mode: "index", intersect: false } },
        scales: { x: Object.assign({ stacked: true }, noGrid, { ticks: { color: MUTED, maxRotation: 0, autoSkip: true } }),
          y: axis({ stacked: true, beginAtZero: true, ticks: { precision: 0, color: MUTED } }) },
      },
    });
  }

  // Taux de réponse public vs privé (%), dénominateur dans l'infobulle
  if (data.response) {
    var r = data.response;
    render("chart-response", {
      type: "bar",
      data: { labels: r.labels, datasets: [Object.assign({ label: "Taux de réponse", data: r.rates.map(function (v) { return v === null ? 0 : v; }),
        backgroundColor: [PUBLIC, PRIVATE] }, baseBar)] },
      options: {
        indexAxis: "y",
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: function (ctx) {
          var i = ctx.dataIndex;
          if (!r.submitted[i]) return "Aucune candidature envoyée";
          return fmt.format(r.rates[i]) + " % — " + r.responded[i] + " réponse(s) sur " + r.submitted[i] + " envoyée(s)";
        } } } },
        scales: { x: axis({ beginAtZero: true, max: 100, ticks: { color: MUTED, callback: function (v) { return v + " %"; } } }), y: noGrid },
      },
    }, r.submitted[0] + r.submitted[1] > 0);
  }
})();
