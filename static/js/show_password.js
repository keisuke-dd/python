const toggleVisibility = (inputId, buttonId) => {
  const input = document.getElementById(inputId);
  const button = document.getElementById(buttonId);
  const icon = button.querySelector("i");

  if (!input || !button) return;

  button.addEventListener("click", () => {
    const isHidden = input.type === "password";
    input.type = isHidden ? "text" : "password";

    // アイコンを切り替え
    if (icon) {
      icon.classList.toggle("fa-eye", !isHidden);
      icon.classList.toggle("fa-eye-slash", isHidden);
    }
  });
};

document.addEventListener("DOMContentLoaded", () => {
  toggleVisibility("passwordInput", "togglePasswordVisibility");
  toggleVisibility("confirmPasswordInput", "toggleConfirmPasswordVisibility");
});

