(function () {
  "use strict";

  const urls = window.FEASTLY_URLS || {};
  if (!urls.cartAdd) return;

  function getCookie(name) {
    const row = document.cookie.split("; ").find((item) => item.startsWith(name + "="));
    return row ? decodeURIComponent(row.split("=")[1]) : "";
  }

  function toast(message, type) {
    if (window.Feastly) Feastly.showToast(message, type);
  }

  async function send(params) {
    const response = await fetch(urls.cartAdd, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRFToken": getCookie("csrftoken"), Accept: "application/json" },
      body: params,
    });
    const data = await response.json().catch(() => ({}));
    return { response, data };
  }

  // Adds food to the cart. Returns true when it worked.
  async function addToCart(params) {
    if (!window.FEASTLY_USER) {
      toast("Please log in to add food to your cart", "info");
      setTimeout(() => {
        window.location.href = (urls.login || "/login/") + "?next=" + encodeURIComponent(window.location.pathname);
      }, 1000);
      return false;
    }

    try {
      let { response, data } = await send(params);

      // The cart holds food from another restaurant: ask before replacing it
      if (response.status === 409 && data.code === "different_restaurant") {
        const confirmed = await Feastly.confirm(
          "Start a new cart?",
          "Your cart already has food from another restaurant. Starting a new cart removes those items.",
          "Start new cart"
        );
        if (!confirmed) return false;
        params.set("replace", "1");
        ({ response, data } = await send(params));
      }

      if (!response.ok || !data.ok) {
        toast(data.message || "Could not add to cart. Please try again.", "error");
        return false;
      }

      if (window.Feastly) Feastly.setCartCount(data.count);
      toast(data.message, "success");
      return true;
    } catch (error) {
      toast("Could not reach the server. Check your connection.", "error");
      return false;
    }
  }

  // ---------- "Add" buttons on food cards: one item, default size, no extras ----------
  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-add-to-cart]");
    if (!button || button.disabled) return;

    const original = button.innerHTML;
    button.disabled = true;

    const added = await addToCart(new URLSearchParams({ food_id: button.dataset.foodId, quantity: "1" }));

    if (added) {
      button.innerHTML = '<i class="bi bi-check-lg me-1"></i>Added';
      setTimeout(() => {
        button.innerHTML = original;
        button.disabled = false;
      }, 1200);
    } else {
      button.disabled = false;
    }
  });

  // ---------- The food details page: size, extras and quantity from the form ----------
  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (form.id !== "foodForm") return;
    event.preventDefault();

    const idHolder = form.querySelector("[data-food-id]"); // the heart button carries the food id
    if (!idHolder) return;

    const params = new URLSearchParams(new FormData(form));
    params.set("food_id", idHolder.dataset.foodId);

    const submitter = event.submitter;
    if (submitter) submitter.disabled = true;
    await addToCart(params);
    if (submitter) submitter.disabled = false;
  });
})();