// Мягкая защита от нежелательного зума
(function () {
  const prevent = (e) => e.preventDefault();
  ["gesturestart", "gesturechange", "gestureend"].forEach(t => {
    document.addEventListener(t, prevent, { passive: false });
  });
  document.addEventListener("wheel", function (e) {
    if (e.ctrlKey) e.preventDefault();
  }, { passive: false });
})();
