// ハンバーガーメニューの開閉
    var hamburger = document.querySelector('.hamburger');
    var hamburgerNav = document.querySelector('.nav-links');

    if (hamburger && hamburgerNav) {
        hamburger.addEventListener('click', function() {
            hamburgerNav.classList.toggle('active');
        });
    }