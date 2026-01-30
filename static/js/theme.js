// 🌙 Theme toggle with localStorage memory
const toggleBtn = document.getElementById("theme-toggle");
const currentTheme = localStorage.getItem("theme");

if (currentTheme === "dark") enableDarkMode();

toggleBtn?.addEventListener("click", () => {
  if (document.body.classList.contains("dark")) {
    disableDarkMode();
  } else {
    enableDarkMode();
  }
});

function enableDarkMode() {
  document.body.classList.add("dark");
  document.querySelectorAll("nav, .navbar, .hero, .why, footer, .auth-container, .dashboard, table, .feature-card, input, button, select")
    .forEach(el => el.classList.add("dark"));
  toggleBtn.textContent = "☀️";
  localStorage.setItem("theme", "dark");
}

function disableDarkMode() {
  document.body.classList.remove("dark");
  document.querySelectorAll("nav, .navbar, .hero, .why, footer, .auth-container, .dashboard, table, .feature-card, input, button, select")
    .forEach(el => el.classList.remove("dark"));
  toggleBtn.textContent = "🌙";
  localStorage.setItem("theme", "light");
}
