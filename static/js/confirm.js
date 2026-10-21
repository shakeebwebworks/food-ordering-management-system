(function () {
  "use strict";

  // A small "are you sure?" pop-up. Resolves to true (confirmed) or false (cancelled).
  function askConfirm(title, message, confirmLabel) {
    return new Promise((resolve) => {
      const modalEl = document.createElement("div");
      modalEl.className = "modal fade";
      modalEl.tabIndex = -1;
      modalEl.setAttribute("aria-hidden", "true");
      modalEl.innerHTML =
        '<div class="modal-dialog modal-dialog-centered">' +
        '<div class="modal-content border-0 rounded-4 p-2">' +
        '<div class="modal-body p-4">' +
        '<h2 class="h5 mb-2" data-title></h2>' +
        '<p class="text-muted-soft mb-4" data-message></p>' +
        '<div class="d-flex justify-content-end gap-2">' +
        '<button type="button" class="btn btn-outline-ink" data-bs-dismiss="modal">Cancel</button>' +
        '<button type="button" class="btn btn-accent" data-confirm></button>' +
        "</div></div></div></div>";

      modalEl.querySelector("[data-title]").textContent = title;
      modalEl.querySelector("[data-message]").textContent = message;
      modalEl.querySelector("[data-confirm]").textContent = confirmLabel;

      let answer = false;
      modalEl.querySelector("[data-confirm]").addEventListener("click", () => {
        answer = true;
        modal.hide();
      });
      modalEl.addEventListener("hidden.bs.modal", () => {
        modal.dispose();
        modalEl.remove();
        resolve(answer);
      });

      document.body.appendChild(modalEl);
      const modal = new bootstrap.Modal(modalEl);
      modal.show();
    });
  }

  // Other scripts can call Feastly.confirm(title, message, buttonLabel)
  window.Feastly = Object.assign(window.Feastly || {}, { confirm: askConfirm });

  // Any form with a data-confirm attribute asks first, then submits
  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!form.matches || !form.matches("form[data-confirm]")) return;

    event.preventDefault();
    const confirmed = await askConfirm(
      form.dataset.confirmTitle || "Are you sure?",
      form.dataset.confirm,
      form.dataset.confirmLabel || "Confirm"
    );
    if (confirmed) form.submit(); // form.submit() does not trigger this listener again
  });
})();