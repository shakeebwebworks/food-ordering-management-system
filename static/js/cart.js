(function () {
  "use strict";

  const linesEl = document.getElementById("cartLines");
  if (!linesEl) return; // not the cart page

  const MIN_QTY = 1;
  const MAX_QTY = 20;

  function formatPrice(value) {
    const number = parseFloat(value) || 0;
    return "\u20B9" + (Number.isInteger(number) ? number : number.toFixed(2));
  }

  function getCookie(name) {
    const row = document.cookie.split("; ").find((item) => item.startsWith(name + "="));
    return row ? decodeURIComponent(row.split("=")[1]) : "";
  }

  function toast(message, type) {
    if (window.Feastly) Feastly.showToast(message, type);
  }

  // Sends one action to the server and returns its answer (or null after showing an error)
  async function post(url, fields) {
    try {
      const response = await fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRFToken": getCookie("csrftoken"), Accept: "application/json" },
        body: new URLSearchParams(fields || {}),
      });
      if (response.status === 401) {
        window.location.href = (window.FEASTLY_URLS || {}).login || "/login/";
        return null;
      }
      const data = await response.json();
      if (!response.ok || !data.ok) {
        toast(data.message || "Something went wrong. Please try again.", "error");
        return null;
      }
      return data;
    } catch (error) {
      toast("Could not reach the server. Check your connection.", "error");
      return null;
    }
  }

  // ---------- Put the new numbers on the page ----------
  function setText(element, text) {
    if (!element || element.textContent === text) return;
    element.textContent = text;
    element.classList.remove("is-changing");
    void element.offsetWidth; // restarts the small pop animation
    element.classList.add("is-changing");
  }

  function updateButtons(line) {
    const qty = parseInt(line.querySelector("[data-cart-qty]").textContent, 10);
    line.querySelector("[data-cart-minus]").disabled = qty <= MIN_QTY;
    line.querySelector("[data-cart-plus]").disabled = qty >= MAX_QTY;
  }

  function showEmptyCart() {
    ["cartContent", "cartMobileBar"].forEach((id) => {
      const element = document.getElementById(id);
      if (element) element.hidden = true;
    });
    document.getElementById("cartEmpty").hidden = false;
  }

  function applyPayload(data) {
    if (window.Feastly) Feastly.setCartCount(data.count);
    if (!data.count) {
      showEmptyCart();
      return;
    }

    // Lines: new quantity and line total (lines the server no longer has are removed)
    linesEl.querySelectorAll("[data-cart-line]").forEach((line) => {
      const info = data.lines[line.dataset.cartLine];
      if (!info) {
        line.remove();
        return;
      }
      setText(line.querySelector("[data-cart-qty]"), String(info.quantity));
      setText(line.querySelector("[data-line-total]"), formatPrice(info.line_total));
      updateButtons(line);
    });

    // Summary numbers (the total also appears in the phone bar)
    const sum = data.summary;
    document.querySelectorAll("[data-sum]").forEach((element) => {
      const key = element.dataset.sum;
      let text = formatPrice(sum[key]);
      if (key === "delivery_fee" && parseFloat(sum[key]) === 0) text = "Free";
      if (key === "discount") text = "-" + text;
      setText(element, text);
    });

    const discountRow = document.querySelector("[data-discount-row]");
    if (discountRow) discountRow.hidden = parseFloat(sum.discount) === 0;

    // Minimum order message and the checkout buttons
    const note = document.getElementById("minNote");
    if (note) {
      note.hidden = data.meets_minimum;
      note.lastChild.textContent = " Minimum order is " + formatPrice(data.min_order_amount) + ".";
    }
    document.querySelectorAll("#checkoutBtn, [data-checkout-link]").forEach((link) => {
      link.classList.toggle("is-disabled", !data.meets_minimum);
      if (data.meets_minimum) link.removeAttribute("aria-disabled");
      else link.setAttribute("aria-disabled", "true");
    });
  }

  // ---------- Buttons on each line ----------
  async function changeQuantity(line, newQty) {
    if (newQty < MIN_QTY || newQty > MAX_QTY) return;
    line.classList.add("is-busy");
    const data = await post(line.dataset.updateUrl, { quantity: newQty });
    line.classList.remove("is-busy");
    if (data) applyPayload(data);
  }

  async function removeLine(line) {
    line.classList.add("is-busy");
    const data = await post(line.dataset.removeUrl);
    line.classList.remove("is-busy");
    if (!data) return;

    line.classList.add("is-removing");
    toast("Item removed", "info");
    setTimeout(() => {
      line.remove();
      applyPayload(data);
    }, 280);
  }

  linesEl.addEventListener("click", (event) => {
    const line = event.target.closest("[data-cart-line]");
    if (!line) return;

    const qty = parseInt(line.querySelector("[data-cart-qty]").textContent, 10);
    if (event.target.closest("[data-cart-plus]")) changeQuantity(line, qty + 1);
    else if (event.target.closest("[data-cart-minus]")) changeQuantity(line, qty - 1);
    else if (event.target.closest("[data-cart-remove]")) removeLine(line);
  });

  linesEl.querySelectorAll("[data-cart-line]").forEach(updateButtons);
})();