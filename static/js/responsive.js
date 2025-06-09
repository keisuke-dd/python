document.addEventListener('DOMContentLoaded', function() {
    // ハンバーガーメニューの開閉
    var hamburger = document.querySelector('.hamburger');
    var hamburgerNav = document.querySelector('.nav-links');

    if (hamburger && hamburgerNav) {
        hamburger.addEventListener('click', function() {
            hamburgerNav.classList.toggle('active');
        });
    }

    // ドロップダウンメニューの開閉（必要な場合）
    // ハンバーガーメニューとドロップダウンを同時に管理する場合、ここに追加
    // 例えば、モバイルでドロップダウンを自動で開くようにするなどのロジック
});