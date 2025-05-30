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