(function () {
  if (location.pathname !== "/") return;

  const postJSON = (url, data) => fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
    credentials: "same-origin",
  });

  async function authFlow() {
    const statusEl = document.getElementById("auth-status");
    const wa = window.Telegram && window.Telegram.WebApp;
    if (!wa) { if (statusEl) statusEl.textContent = "Перезайдите через Telegram"; return; }
    wa.ready();

    const initData = wa.initData || "";
    try {
      const res = await postJSON("/auth/validate", { initData });
      const data = await res.json();
      if (data && data.ok && data.player) {
        sessionStorage.setItem("player", JSON.stringify(data.player));
        window.location.replace("/farm");
      } else if (data && data.error === "user_blocked") {
        // Пользователь заблокирован
        sessionStorage.setItem("blocked_reason", data.blocked_reason || "Аккаунт заблокирован");
        window.location.replace("/blocked");
      } else {
        if (statusEl) statusEl.textContent = "Перезайдите через Telegram";
      }
    } catch (_) {
      if (statusEl) statusEl.textContent = "Перезайдите через Telegram";
    }
  }

  window.addEventListener("DOMContentLoaded", authFlow);
})();
