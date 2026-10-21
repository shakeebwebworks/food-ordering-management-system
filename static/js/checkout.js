(function () {
  "use strict";

  const form = document.getElementById("checkoutForm");
  if (!form) return;

  // ---------- Saved address chosen: hide the new-address fields. "New address": show them ----------
  const newAddressBlocks = document.querySelectorAll("[data-new-address]");
  const choices = form.querySelectorAll("[data-address-choice]");

  function updateAddressFields() {
    const picked = form.querySelector("[data-address-choice]:checked");
    const useNew = !picked || picked.value === "";
    newAddressBlocks.forEach((block) => {
      block.hidden = !useNew;
    });
  }

  choices.forEach((choice) => choice.addEventListener("change", updateAddressFields));
  updateAddressFields();

  // ---------- Place order: show a spinner and block double clicks ----------
  const button = document.getElementById("placeOrderBtn");
  const mobileButton = document.querySelector('button[form="checkoutForm"]');
  let submitted = false;

  form.addEventListener("submit", (event) => {
    if (submitted) {
      event.preventDefault(); // already sending: ignore the second click
      return;
    }
    submitted = true;
    if (button) button.classList.add("is-loading");
    if (mobileButton) setTimeout(() => { mobileButton.disabled = true; }, 0);
  });

  // Coming back with the browser's Back button: make the buttons usable again
  window.addEventListener("pageshow", (event) => {
    if (!event.persisted) return;
    submitted = false;
    if (button) button.classList.remove("is-loading");
    if (mobileButton) mobileButton.disabled = false;
  });
})();