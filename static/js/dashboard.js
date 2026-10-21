(function () {
  "use strict";

  const root = document.getElementById("dashCharts");
  if (!root || typeof Chart === "undefined") return;

  const apiUrl = root.dataset.api;
  const errorBox = document.getElementById("dashError");
  const rangeButtons = document.querySelectorAll(".range-btn");

  // Colours come from the site's own CSS variables
  const css = getComputedStyle(document.documentElement);
  const color = (name, fallback) => css.getPropertyValue(name).trim() || fallback;
  const ACCENT = color("--color-accent", "#d83c13");
  const INK = color("--color-ink", "#16161a");
  const MUTED = color("--color-muted", "#6b6b76");
  const BORDER = color("--color-border", "#e8e6e1");
  const PALETTE = [ACCENT, INK, "#f5a524", "#1f9d55", "#1d4fb8", "#9a9aa6"];
  const STATUS_COLORS = {
    placed: "#9a9aa6",
    confirmed: "#1d4fb8",
    preparing: "#f5a524",
    out_for_delivery: "#6f42c1",
    delivered: "#1f9d55",
    cancelled: "#b3261e",
  };

  Chart.defaults.font.family = color("--font-sans", "system-ui, sans-serif");
  Chart.defaults.color = MUTED;
  Chart.defaults.maintainAspectRatio = false;
  if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    Chart.defaults.animation = false;
  }

  const charts = {};

  const number = (value) => Number(value) || 0;
  const rupees = (value) => "\u20B9" + number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 });
  const shortDate = (iso) =>
    new Date(iso + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });

  // ---------- Key numbers ----------
  function showTotals(totals) {
    document.querySelectorAll("[data-stat]").forEach((element) => {
      const value = number(totals[element.dataset.stat]);
      element.textContent = element.dataset.kind === "money" ? rupees(value) : value.toLocaleString("en-IN");
    });
  }

  function showStatsFailed() {
    document.querySelectorAll("[data-stat]").forEach((element) => {
      element.textContent = "\u2014";
    });
  }

  // ---------- Charts ----------
  function draw(id, hasData, config) {
    const canvas = document.getElementById(id);
    const empty = canvas.parentElement.querySelector(".chart-empty");

    if (charts[id]) {
      charts[id].destroy();
      delete charts[id];
    }
    canvas.hidden = !hasData;
    if (empty) empty.hidden = hasData;
    if (hasData) charts[id] = new Chart(canvas, config);
  }

  const gridOptions = { color: BORDER, drawTicks: false };

  function lineConfig(labels, values, label, money) {
    return {
      type: "line",
      data: {
        labels: labels.map(shortDate),
        datasets: [{
          label,
          data: values.map(number),
          borderColor: ACCENT,
          backgroundColor: "rgba(216, 60, 19, 0.12)",
          fill: true,
          tension: 0.35,
          pointRadius: 0,
          pointHoverRadius: 5,
          borderWidth: 2.5,
        }],
      },
      options: {
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (item) => (money ? rupees(item.parsed.y) : item.parsed.y) } },
        },
        scales: {
          x: { grid: { display: false }, ticks: { maxTicksLimit: 7 } },
          y: {
            beginAtZero: true,
            grid: gridOptions,
            border: { display: false },
            ticks: { precision: 0, callback: (value) => (money ? rupees(value) : value) },
          },
        },
      },
    };
  }

  function barConfig(labels, values, label, horizontal) {
    return {
      type: "bar",
      data: {
        labels,
        datasets: [{ label, data: values.map(number), backgroundColor: ACCENT, borderRadius: 6, maxBarThickness: 28 }],
      },
      options: {
        indexAxis: horizontal ? "y" : "x",
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: horizontal ? gridOptions : { display: false }, border: { display: false }, ticks: { precision: 0, maxTicksLimit: horizontal ? 6 : 7 } },
          y: { beginAtZero: true, grid: horizontal ? { display: false } : gridOptions, border: { display: false }, ticks: { precision: 0 } },
        },
      },
    };
  }

  function doughnutConfig(labels, values, colors) {
    return {
      type: "doughnut",
      data: { labels, datasets: [{ data: values.map(number), backgroundColor: colors, borderWidth: 2, borderColor: "#fff" }] },
      options: {
        cutout: "62%",
        plugins: { legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8, padding: 14 } } },
      },
    };
  }

  function showCharts(data) {
    const charts = data.charts;
    const hasRevenue = charts.revenue.some((value) => number(value) > 0);
    const hasOrders = charts.orders.some((value) => number(value) > 0);

    draw("chartRevenue", hasRevenue, lineConfig(charts.labels, charts.revenue, "Revenue", true));
    draw("chartOrders", hasOrders, barConfig(charts.labels.map(shortDate), charts.orders, "Orders", false));

    const popular = charts.popular_foods;
    draw("chartPopular", popular.length > 0, barConfig(popular.map((row) => row.name), popular.map((row) => row.sold), "Sold", true));

    const byCategory = charts.orders_by_category;
    draw("chartCategory", byCategory.length > 0,
      doughnutConfig(byCategory.map((row) => row.category), byCategory.map((row) => row.sold), PALETTE));

    draw("chartGrowth", number(charts.customer_growth[charts.customer_growth.length - 1]) > 0,
      lineConfig(charts.labels, charts.customer_growth, "Customers", false));

    const statuses = charts.status_distribution.filter((row) => row.count > 0);
    draw("chartStatus", statuses.length > 0,
      doughnutConfig(statuses.map((row) => row.label), statuses.map((row) => row.count),
        statuses.map((row) => STATUS_COLORS[row.status] || MUTED)));
  }

  // ---------- Loading ----------
  async function load(days) {
    errorBox.hidden = true;
    try {
      const response = await fetch(apiUrl + "?days=" + days, {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) throw new Error("bad status " + response.status);
      const data = await response.json();
      showTotals(data.totals);
      showCharts(data);
    } catch (error) {
      errorBox.hidden = false;
      showStatsFailed();
    }
  }

  rangeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      rangeButtons.forEach((other) => {
        const active = other === button;
        other.classList.toggle("is-active", active);
        other.setAttribute("aria-pressed", String(active));
      });
      load(button.dataset.days);
    });
  });

  load(30);
})();