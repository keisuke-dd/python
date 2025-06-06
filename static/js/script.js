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


//javascriptにてボタン作成
        
            document.addEventListener('DOMContentLoaded', function() {
                const sections = document.querySelectorAll('.section');
                const navLinks = document.querySelectorAll('.nav-link');
                const prevButton = document.getElementById('prevButton');
                const nextButton = document.getElementById('nextButton');
                const progressBar = document.getElementById('progressBar');
                let currentIndex = 0;

                // 最初のセクションを表示
                sections[0].classList.add('active');
                navLinks[0].classList.add('current');
                updateProgress();

                // ナビゲーションリンクのクリックイベント
                navLinks.forEach((link, index) => {
                    link.addEventListener('click', (e) => {
                        e.preventDefault();
                        showSection(index);
                    });
                });

                // 前へボタンのクリックイベント
                prevButton.addEventListener('click', () => {
                    if (currentIndex > 0) {
                        showSection(currentIndex - 1);
                    }
                });

                // 次へボタンのクリックイベント
                nextButton.addEventListener('click', () => {
                    if (currentIndex < sections.length - 1) {
                        showSection(currentIndex + 1);
                    }
                });

                function showSection(index) {
                    // 現在のセクションを非表示
                    sections[currentIndex].classList.remove('active');
                    navLinks[currentIndex].classList.remove('current');

                    // 新しいセクションを表示
                    currentIndex = index;
                    sections[currentIndex].classList.add('active');
                    navLinks[currentIndex].classList.add('current');

                    // ボタンの状態を更新
                    prevButton.disabled = currentIndex === 0;
                    nextButton.disabled = currentIndex === sections.length - 1;

                    // プログレスバーを更新
                    updateProgress();

                    // セクションまでスクロール
                    sections[currentIndex].scrollIntoView({ behavior: 'smooth' });
                }

                function updateProgress() {
                    const progress = ((currentIndex + 1) / sections.length) * 100;
                    progressBar.style.width = `${progress}%`;
                }
            });
    