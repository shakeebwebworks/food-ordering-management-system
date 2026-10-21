(function () {
  "use strict";

  // Tell the CSS that JavaScript is running (scroll-reveal and image-reveal need this)
  document.documentElement.classList.add("js");

  // 1. Navbar: add the "is-scrolled" class once the page is scrolled a little
  const header = document.getElementById("siteHeader");
  if (header) {
    const updateHeader = () => {
      header.classList.toggle("is-scrolled", window.scrollY > 10);
    };
    updateHeader();
    window.addEventListener("scroll", updateHeader, { passive: true });
  }

  // 2. Cart badge: change the number and play the small "pop" animation
  const cartCount = document.getElementById("cartCount");

  function setCartCount(count) {
    if (!cartCount) return;
    cartCount.textContent = count;
    cartCount.classList.remove("bump");
    void cartCount.offsetWidth; // restarts the animation if it is already playing
    cartCount.classList.add("bump");
  }

  // 3. Toast notifications: small messages in the corner
  const TOAST_ICONS = {
    success: "bi-check-lg",
    error: "bi-exclamation-lg",
    info: "bi-info-lg",
  };
  let toastStack = null;

  function showToast(message, type = "info", duration = 3500) {
    if (!toastStack) {
      toastStack = document.createElement("div");
      toastStack.className = "toast-stack";
      toastStack.setAttribute("aria-live", "polite");
      document.body.appendChild(toastStack);
    }

    const toast = document.createElement("div");
    toast.className = "app-toast toast-" + type;
    toast.setAttribute("role", type === "error" ? "alert" : "status");

    const icon = document.createElement("span");
    icon.className = "toast-icon";
    icon.innerHTML = '<i class="bi ' + (TOAST_ICONS[type] || TOAST_ICONS.info) + '"></i>';

    const text = document.createElement("span");
    text.className = "toast-message";
    text.textContent = message; // textContent keeps the message safe from injected HTML

    const close = document.createElement("button");
    close.type = "button";
    close.className = "toast-close";
    close.setAttribute("aria-label", "Dismiss");
    close.innerHTML = "&times;";

    toast.append(icon, text, close);
    toastStack.appendChild(toast);

    const dismiss = () => {
      if (toast.classList.contains("is-leaving")) return;
      toast.classList.add("is-leaving");
      toast.addEventListener("animationend", () => toast.remove(), { once: true });
    };
    close.addEventListener("click", dismiss);
    setTimeout(dismiss, duration);
  }

  // 4. Scroll reveal: elements with class "reveal" fade in when they come into view
  let revealObserver = null;
  if ("IntersectionObserver" in window) {
    revealObserver = new IntersectionObserver(
      (entries, observer) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12 }
    );
  }

  function observeReveals(root) {
    (root || document).querySelectorAll(".reveal:not(.is-visible)").forEach((el) => {
      if (revealObserver) revealObserver.observe(el);
      else el.classList.add("is-visible");
    });
  }

  // 5. Image reveal: photos fade in smoothly once they have loaded
  function markLoaded(img) {
    img.classList.add("is-loaded");
  }

  function observeImages(root) {
    (root || document).querySelectorAll(".img-reveal img:not(.is-loaded)").forEach((img) => {
      if (img.complete) markLoaded(img);
    });
  }

  ["load", "error"].forEach((eventName) => {
    document.addEventListener(
      eventName,
      (event) => {
        const img = event.target;
        if (img.tagName === "IMG" && img.closest(".img-reveal")) markLoaded(img);
      },
      true
    );
  });

  // 6. Wishlist hearts: saved in the database for logged-in users
  const urls = window.FEASTLY_URLS || {};
  const isLoggedIn = window.FEASTLY_USER === true;
  const savedIds = new Set();

  try {
    const data = document.getElementById("wishlist-data");
    if (data) JSON.parse(data.textContent).forEach((id) => savedIds.add(String(id)));
  } catch (error) {
    /* no saved foods to show */
  }

  function setHeart(button, active) {
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
    const icon = button.querySelector("i");
    if (icon) {
      icon.classList.toggle("bi-heart", !active);
      icon.classList.toggle("bi-heart-fill", active);
    }
  }

  // Updates every heart for the same food on the page (card and detail page)
  function syncHearts(foodId, active) {
    document.querySelectorAll('[data-wishlist][data-food-id="' + foodId + '"]').forEach((button) => {
      setHeart(button, active);
    });
  }

  function getCookie(name) {
    const row = document.cookie.split("; ").find((item) => item.startsWith(name + "="));
    return row ? decodeURIComponent(row.split("=")[1]) : "";
  }

  async function toggleWishlist(button) {
    const foodId = button.dataset.foodId;

    if (!isLoggedIn) {
      showToast("Please log in to save your favourites", "info");
      setTimeout(() => {
        window.location.href = (urls.login || "/login/") + "?next=" + encodeURIComponent(window.location.pathname);
      }, 1000);
      return;
    }

    button.disabled = true;
    try {
      const response = await fetch((urls.wishlistToggle || "").replace("/0/", "/" + foodId + "/"), {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRFToken": getCookie("csrftoken"), Accept: "application/json" },
      });
      if (!response.ok) throw new Error("bad status");

      const result = await response.json();
      syncHearts(foodId, result.saved);
      showToast(result.saved ? "Saved to wishlist" : "Removed from wishlist", result.saved ? "success" : "info");
    } catch (error) {
      showToast("Could not update your wishlist. Please try again.", "error");
    } finally {
      button.disabled = false;
    }
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-wishlist]");
    if (button) toggleWishlist(button);
  });

  // Show the foods you already saved as filled hearts
  document.querySelectorAll("[data-wishlist]").forEach((button) => {
    if (savedIds.has(button.dataset.foodId)) setHeart(button, true);
  });

    // 7. Connection status: tell people when the internet drops or comes back
  window.addEventListener("offline", () => showToast("You are offline. Some things may not work.", "error", 6000));
  window.addEventListener("online", () => showToast("You are back online.", "success"));
  // Run once when the page loads
  observeReveals();
  observeImages();

  // Other files can call these, for example Feastly.showToast("Added to cart", "success")
  window.Feastly = { setCartCount, showToast, observeReveals, observeImages };
})();