(function () {
  "use strict";

  // Replays a small fade-in on a card, each one a little after the one before
  function animateIn(element, delay) {
    element.classList.add("is-visible");
    element.style.animation = "none";
    void element.offsetWidth; // restarts the animation
    element.style.animation = "page-in 400ms var(--ease) both " + delay + "ms";
  }

  // ---------- 1. Category cards filter the popular foods ----------
  function initCategoryFilter() {
    const buttons = document.querySelectorAll("[data-category-filter]");
    const grid = document.getElementById("foodGrid");
    const emptyMessage = document.getElementById("filterEmpty");
    if (!buttons.length || !grid) return;

    const cards = grid.querySelectorAll("[data-category]");
    if (!cards.length) return; // no food in the database yet

    function filterFoods(category) {
      let shown = 0;
      cards.forEach((card) => {
        const match = category === "all" || card.dataset.category === category;
        card.hidden = !match;
        if (match) {
          animateIn(card, shown * 50);
          shown += 1;
        }
      });
      if (emptyMessage) emptyMessage.hidden = shown !== 0;
    }

    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        buttons.forEach((other) => {
          const active = other === button;
          other.classList.toggle("is-active", active);
          other.setAttribute("aria-pressed", String(active));
        });
        filterFoods(button.dataset.categoryFilter);
      });
    });
  }

  // ---------- 2. Dropdown filters for the restaurants ----------
  function initRestaurantFilters() {
    const grid = document.getElementById("restaurantGrid");
    const selects = document.querySelectorAll("[data-restaurant-filter]");
    if (!grid || !selects.length) return;

    const cards = grid.querySelectorAll("[data-restaurant]");
    const emptyMessage = document.getElementById("restaurantEmpty");
    const countLabel = document.getElementById("restaurantCount");
    const resetButtons = document.querySelectorAll("[data-filter-reset]");

    // Does one restaurant card pass every chosen filter?
    function matches(card, filters) {
      const data = card.dataset;
      if (filters.cuisine && !data.cuisines.split(" ").includes(filters.cuisine)) return false;
      if (filters.rating && parseFloat(data.rating) < parseFloat(filters.rating)) return false;
      if (filters.time && parseInt(data.time, 10) > parseInt(filters.time, 10)) return false;
      if (filters.price && data.price !== filters.price) return false;
      if (filters.diet === "veg" && data.vegOnly !== "true") return false;
      if (filters.diet === "nonveg" && data.vegOnly === "true") return false;
      return true;
    }

    function applyFilters() {
      const filters = {};
      selects.forEach((select) => {
        filters[select.dataset.restaurantFilter] = select.value;
        select.classList.toggle("is-filtered", select.value !== "");
      });

      let shown = 0;
      cards.forEach((card) => {
        const column = card.closest(".restaurant-col");
        const match = matches(card, filters);
        column.hidden = !match;
        if (match) {
          animateIn(column, shown * 50);
          shown += 1;
        }
      });

      if (emptyMessage) emptyMessage.hidden = shown !== 0;
      if (countLabel) countLabel.textContent = shown + " restaurant" + (shown === 1 ? "" : "s");
    }

    selects.forEach((select) => select.addEventListener("change", applyFilters));

    resetButtons.forEach((button) => {
      button.addEventListener("click", () => {
        selects.forEach((select) => { select.value = ""; });
        applyFilters();
      });
    });
  }

  initCategoryFilter();
  initRestaurantFilters();
})();