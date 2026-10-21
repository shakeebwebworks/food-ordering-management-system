(function () {
  "use strict";

  const configurator = document.getElementById("foodConfigurator");
  const form = document.getElementById("foodForm");
  if (!configurator || !form) return;

  const MIN_QTY = 1;
  const MAX_QTY = 20;

  const qtyInput = document.getElementById("detailQty");
  const minusBtn = form.querySelector("[data-qty-minus]");
  const plusBtn = form.querySelector("[data-qty-plus]");
  const priceLabels = document.querySelectorAll("[data-total-price]");

  // Work in paise (whole numbers) so prices never show errors like 299.9999
  const toPaise = (value) => Math.round((parseFloat(value) || 0) * 100);

  function formatPrice(paise) {
    const rupees = paise / 100;
    return "\u20B9" + (Number.isInteger(rupees) ? rupees : rupees.toFixed(2));
  }

  function currentQty() {
    const value = parseInt(qtyInput.value, 10);
    if (Number.isNaN(value)) return MIN_QTY;
    return Math.min(MAX_QTY, Math.max(MIN_QTY, value));
  }

  // ---------- Live price: (base + size + extras) x quantity ----------
  function unitPaise() {
    let total = toPaise(configurator.dataset.basePrice);

    const size = form.querySelector('input[name="size"]:checked');
    if (size) total += toPaise(size.dataset.delta);

    form.querySelectorAll('input[name="extras"]:checked').forEach((extra) => {
      total += toPaise(extra.dataset.price);
    });
    return total;
  }

  function updatePrice() {
    const text = formatPrice(unitPaise() * currentQty());

    priceLabels.forEach((label) => {
      if (label.textContent === text) return;
      label.textContent = text;
      label.classList.remove("price-bump");
      void label.offsetWidth; // restarts the little pop animation
      label.classList.add("price-bump");
    });
  }

  // ---------- Quantity buttons ----------
  function setQty(value) {
    qtyInput.value = Math.min(MAX_QTY, Math.max(MIN_QTY, value));
    minusBtn.disabled = currentQty() <= MIN_QTY;
    plusBtn.disabled = currentQty() >= MAX_QTY;
    updatePrice();
  }

  minusBtn.addEventListener("click", () => setQty(currentQty() - 1));
  plusBtn.addEventListener("click", () => setQty(currentQty() + 1));
  qtyInput.addEventListener("change", () => setQty(currentQty())); // fixes typed values like 0 or 99
  qtyInput.addEventListener("input", updatePrice);

  // Picking a size or an extra updates the price
  form.addEventListener("change", (event) => {
    if (event.target.matches('input[name="size"], input[name="extras"]')) updatePrice();
  });

  // ---------- Photo thumbnails ----------
  const mainImage = document.getElementById("detailMainImage");
  const thumbs = document.querySelectorAll(".detail-thumb");

  thumbs.forEach((thumb) => {
    thumb.addEventListener("click", () => {
      if (!mainImage || thumb.classList.contains("is-active")) return;

      thumbs.forEach((other) => other.classList.toggle("is-active", other === thumb));

      mainImage.style.opacity = "0";
      mainImage.addEventListener(
        "load",
        () => { mainImage.style.opacity = ""; },
        { once: true }
      );
      mainImage.src = thumb.dataset.full;
      mainImage.alt = thumb.dataset.alt || "";
    });
  });

  // Adding to the cart is handled by cart-add.js, which reads this form.

  setQty(currentQty());
})();