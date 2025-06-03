window.onload = function () {
  const hash = window.location.hash.substring(1);
  const params = new URLSearchParams(hash);
  const accessToken = params.get("access_token");

  if (accessToken) {
    window.location.href = `/update_password_form?access_token=${accessToken}`;
  } else {
    document.body.innerHTML = "<p>トークンが見つかりません。</p>";
  }
};