(function () {
  "use strict";

  const modalEl = document.getElementById("searchModal");
  const input = document.getElementById("searchInput");
  const endpoint = (window.FEASTLY_URLS || {}).searchSuggestions;
  if (!modalEl || !input || !endpoint) return;

  const idleEl = document.getElementById("searchIdle");
  const loadingEl = document.getElementById("searchLoading");
  const resultsEl = document.getElementById("searchResults");
  const emptyEl = document.getElementById("searchEmpty");
  const emptyQuery = document.getElementById("searchEmptyQuery");
  const statusEl = document.getElementById("searchStatus");
  const recentBlock = document.getElementById("recentBlock");
  const recentList = document.getElementById("recentList");
  const popularList = document.getElementById("popularList");
  const popularBlock = popularList.closest(".search-block");

  const STORAGE_KEY = "feastly.recentSearches";
  const MAX_RECENT = 6;
  let controller = null;
  let timer = null;
  let popularLoaded = false;

  // ---------- Small helpers ----------
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function makeChip(text, iconClass, extra) {
    const chip = el("button", "chip");
    chip.type = "button";
    const icon = el("i", "bi " + iconClass);
    icon.setAttribute("aria-hidden", "true");
    chip.append(icon, document.createTextNode(text));
    if (extra) Object.assign(chip.dataset, extra);
    return chip;
  }

  // Wraps the letters you typed in an orange highlight (built safely, no raw HTML)
  function highlight(text, query) {
    const fragment = document.createDocumentFragment();
    const start = text.toLowerCase().indexOf(query.toLowerCase());
    if (start === -1) {
      fragment.append(text);
      return fragment;
    }
    const end = start + query.length;
    fragment.append(text.slice(0, start));
    fragment.append(el("mark", "search-hit", text.slice(start, end)));
    fragment.append(text.slice(end));
    return fragment;
  }

  // Show only one of the four areas: idle, loading, results or empty
  function show(state) {
    idleEl.hidden = state !== "idle";
    loadingEl.hidden = state !== "loading";
    resultsEl.hidden = state !== "results";
    emptyEl.hidden = state !== "empty";
  }

  // ---------- Recent searches (saved in this browser only) ----------
  function loadRecent() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
      return Array.isArray(saved) ? saved.filter((t) => typeof t === "string").slice(0, MAX_RECENT) : [];
    } catch (error) {
      return [];
    }
  }

  function saveRecent(term) {
    term = (term || "").trim();
    if (term.length < 2) return;
    const list = loadRecent().filter((item) => item.toLowerCase() !== term.toLowerCase());
    list.unshift(term);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(list.slice(0, MAX_RECENT)));
    } catch (error) {
      /* private mode or storage full: recent searches just won't be kept */
    }
  }

  function renderRecent() {
    const items = loadRecent();
    recentList.replaceChildren(...items.map((term) => makeChip(term, "bi-clock-history")));
    recentBlock.hidden = items.length === 0;
  }

  document.getElementById("clearRecent").addEventListener("click", () => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (error) {
      /* ignore */
    }
    renderRecent();
  });

  // ---------- Popular searches (loaded once) ----------
  async function loadPopular() {
    if (popularLoaded) return;
    try {
      const response = await fetch(endpoint + "?q=", { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error("bad status");
      const data = await response.json();
      const names = data.popular || [];
      popularList.replaceChildren(...names.map((name) => makeChip(name, "bi-fire")));
      popularBlock.hidden = names.length === 0;
      popularLoaded = true;
    } catch (error) {
      popularList.replaceChildren();
      popularBlock.hidden = true;
    }
  }

  // ---------- Search ----------
  function resultRow(type, label, value, iconClass, subText, meta, query) {
    const item = el("li");
    const button = el("button", "result-item");
    button.type = "button";
    Object.assign(button.dataset, { go: type, label: label, value: value });

    const icon = el("span", "result-icon");
    icon.innerHTML = '<i class="bi ' + iconClass + '" aria-hidden="true"></i>';

    const text = el("span", "result-text");
    const title = el("span", "result-title");
    title.append(highlight(label, query));
    text.append(title, el("span", "result-sub", subText));

    button.append(icon, text);
    if (meta) button.append(el("span", "result-meta", meta));
    item.append(button);
    return item;
  }

  function fillBlock(blockId, nodes) {
    const block = document.getElementById(blockId);
    block.querySelector("[data-list]").replaceChildren(...nodes);
    block.hidden = nodes.length === 0;
  }

  function renderResults(data, query) {
    const foods = data.foods || [];
    const restaurants = data.restaurants || [];
    const categories = data.categories || [];
    const total = foods.length + restaurants.length + categories.length;

    if (total === 0) {
      emptyQuery.textContent = query;
      statusEl.textContent = "No results found";
      show("empty");
      return;
    }

    fillBlock(
      "resultFoods",
      foods.map((food) =>
        resultRow("food", food.name, food.name, "bi-egg-fried", food.restaurant, "\u20B9" + food.price, query)
      )
    );
    fillBlock(
      "resultRestaurants",
      restaurants.map((restaurant) =>
        resultRow(
          "restaurant",
          restaurant.name,
          restaurant.name,
          "bi-shop",
          restaurant.location + (restaurant.is_open ? "" : " \u00B7 Closed"),
          "",
          query
        )
      )
    );
    fillBlock(
      "resultCategories",
      categories.map((category) =>
        makeChip(category.name, "bi-grid", { go: "category", label: category.name, value: category.slug })
      )
    );

    statusEl.textContent = total + (total === 1 ? " result" : " results") + " found";
    show("results");
  }

  async function runSearch(query) {
    if (controller) controller.abort(); // cancel the previous request
    controller = new AbortController();
    show("loading");
    try {
      const response = await fetch(endpoint + "?q=" + encodeURIComponent(query), {
        signal: controller.signal,
        headers: { Accept: "application/json" },
      });
      if (!response.ok) throw new Error("bad status");
      renderResults(await response.json(), query);
    } catch (error) {
      if (error.name === "AbortError") return;
      show("idle");
      if (window.Feastly) Feastly.showToast("Search is unavailable right now. Check your connection.", "error");
    }
  }

  input.addEventListener("input", () => {
    clearTimeout(timer);
    const query = input.value.trim();
    if (query.length < 2) {
      if (controller) controller.abort();
      statusEl.textContent = "";
      show("idle");
      return;
    }
    show("loading");
    timer = setTimeout(() => runSearch(query), 250); // wait until you pause typing
  });

  input.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    const query = input.value.trim();
    if (query.length < 2) return;
    const first = resultsEl.hidden ? null : resultsEl.querySelector("[data-go]");
    if (first) first.click();
    else saveRecent(query);
  });

  // ---------- Clicking things ----------
  // Recent and popular searches: fill the box and search
  idleEl.addEventListener("click", (event) => {
    const chip = event.target.closest(".chip");
    if (!chip) return;
    input.value = chip.textContent.trim();
    input.focus();
    input.dispatchEvent(new Event("input"));
  });

  function afterClose(action) {
    modalEl.addEventListener("hidden.bs.modal", action, { once: true });
    const instance = window.bootstrap && bootstrap.Modal.getInstance(modalEl);
    if (instance) instance.hide();
  }

  function scrollToSection(id) {
    const target = document.getElementById(id);
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    else window.location.href = "/#" + id; // not on the home page: go there first
  }

  // Result rows (food detail and restaurant pages come in a later phase,
  // so for now a result takes you to the matching section of the home page)
  resultsEl.addEventListener("click", (event) => {
    const item = event.target.closest("[data-go]");
    if (!item) return;
    saveRecent(item.dataset.label);

    const { go, value } = item.dataset;
    afterClose(() => {
      if (go === "restaurant") {
        scrollToSection("restaurants");
        return;
      }
      const filter = go === "category" ? value : "all";
      const button = document.querySelector('[data-category-filter="' + CSS.escape(filter) + '"]');
      if (button) button.click();
      scrollToSection("popular");
    });
  });

  // ---------- Opening and closing ----------
  modalEl.addEventListener("show.bs.modal", () => {
    renderRecent();
    loadPopular();
  });
  modalEl.addEventListener("shown.bs.modal", () => input.focus());
  modalEl.addEventListener("hidden.bs.modal", () => {
    if (controller) controller.abort();
    input.value = "";
    statusEl.textContent = "";
    show("idle");
  });
})();