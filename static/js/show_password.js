const toggleVisibility = (inputId, buttonId) => {
  const input = document.getElementById(inputId);
  const button = document.getElementById(buttonId);

  if (!input || !button) return;

  button.addEventListener("click", () => {
    if (input.type === "password") {
      input.type = "text";
      button.textContent = "非表示";
    } else {
      input.type = "password";
      button.textContent = "表示";
    }
  });
};

document.addEventListener("DOMContentLoaded", () => {
  toggleVisibility("passwordInput", "showPasswordButton");
  toggleVisibility("confirmPasswordInput", "showConfirmPasswordButton");
});
