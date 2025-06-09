document.addEventListener('DOMContentLoaded', function() {
    // 個別スキルアコーディオンの開閉
    var skillHeaders = document.querySelectorAll('.accordion-header');
    skillHeaders.forEach(function(header) {
        header.addEventListener('click', function() {
            var content = this.nextElementSibling;
            this.classList.toggle('active');
            if (content.style.maxHeight) {
                content.style.maxHeight = null;
                content.style.padding = '0 1.25rem'; // パディングをリセット
            } else {
                content.style.maxHeight = content.scrollHeight + 'px';
                content.style.padding = '1rem 1.25rem'; // パディングを設定
            }
        });
    });

    // カテゴリアコーディオンの開閉
    var categoryHeaders = document.querySelectorAll('.accordion-category-header');
    categoryHeaders.forEach(function(header) {
        header.addEventListener('click', function() {
            var content = this.nextElementSibling;
            this.classList.toggle('active');
            if (content.style.maxHeight) {
                content.style.maxHeight = null;
                content.style.padding = '0 1.25rem'; // パディングをリセット
            } else {
                content.style.maxHeight = content.scrollHeight + 'px';
                content.style.padding = '1rem 1.25rem'; // パディングを設定
            }
        });
    });
});

// テキストエリア自動リサイズ（class="auto-expand" が対象）
var textareas = document.querySelectorAll("textarea.auto-expand");
textareas.forEach(function(textarea) {
    // 初期高さを調整
    textarea.style.height = textarea.scrollHeight + "px";

    textarea.addEventListener("input", function() {
        this.style.height = "auto";
        this.style.height = this.scrollHeight + "px";
    });
});



    