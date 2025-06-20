// プロフィール入力フォームのスクリプト
  
  function addCertification() {
    const container = document.getElementById("certifications-container");
    const newField = document.createElement("div");
    newField.className = "certification-item";
    newField.innerHTML = `
      <input type="text" name="certifications[]" placeholder="例：基本情報技術者">
      <button type="button" onclick="removeField(this)">削除</button>
    `;
    container.appendChild(newField);
  }

  function removeField(button) {
    button.parentElement.remove();
  }

