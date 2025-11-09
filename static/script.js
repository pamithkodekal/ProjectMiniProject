document.addEventListener("DOMContentLoaded", () => {
  const alerts = document.querySelectorAll(".alert");
  alerts.forEach(alert => {
    setTimeout(() => {
      alert.classList.remove("show");
    }, 3000);
  });
});
