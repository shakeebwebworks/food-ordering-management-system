(function () {
  "use strict";

  const tracker = document.getElementById("tracker");
  if (!tracker || tracker.dataset.final === "true") return; // nothing to update

  const url = tracker.dataset.statusUrl;
  const POLL_MS = 8000;

  const BADGE_CLASSES = {
    placed: "badge-placed",
    confirmed: "badge-placed",
    preparing: "badge-preparing",
    out_for_delivery: "badge-out",
    delivered: "badge-delivered",
    cancelled: "badge-cancelled",
  };

  const messageEl = tracker.querySelector("[data-track-message]");
  const badgeEl = tracker.querySelector("[data-track-badge]");
  const etaEl = tracker.querySelector("[data-track-eta]");
  const stepEls = tracker.querySelectorAll("[data-step]");

  let lastStatus = null;
  let timer = null;

  // Put the latest state from the server on the page
  function apply(data) {
    stepEls.forEach((element) => {
      const info = data.steps.find((step) => step.key === element.dataset.step);
      if (!info) return;

      element.classList.remove("is-done", "is-current", "is-pending");
      element.classList.add("is-" + info.state);
      if (info.state === "current") element.setAttribute("aria-current", "step");
      else element.removeAttribute("aria-current");

      const time = element.querySelector("[data-step-time]");
      if (time) time.textContent = info.time;
    });

    if (messageEl) messageEl.textContent = data.message;

    if (badgeEl) {
      Object.values(BADGE_CLASSES).forEach((name) => badgeEl.classList.remove(name));
      badgeEl.classList.add(BADGE_CLASSES[data.status] || "badge-placed");
      badgeEl.textContent = data.label;
    }

    if (data.final && etaEl) etaEl.remove();

    // Tell the customer when the status changes while they are watching
    if (lastStatus !== null && lastStatus !== data.status && window.Feastly) {
      Feastly.showToast(data.message, data.cancelled ? "error" : "success", 5000);
    }
    lastStatus = data.status;
  }

  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(poll, POLL_MS);
  }

  async function poll() {
    if (document.hidden) {
      schedule(); // the tab is in the background: wait
      return;
    }
    try {
      const response = await fetch(url, {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      });
      if (response.status === 401 || response.status === 404) return; // logged out or order gone: stop

      if (response.ok) {
        const data = await response.json();
        apply(data);
        if (data.final) {
          // Reload once so the page shows the finished (or cancelled) layout
          setTimeout(() => window.location.reload(), 2500);
          return;
        }
      }
    } catch (error) {
      /* connection problem: try again on the next round */
    }
    schedule();
  }

  // Coming back to the tab: refresh straight away
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) poll();
  });

  schedule();
})();