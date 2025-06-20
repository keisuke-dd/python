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



        // スキルシートのカスタムスキル追加機能
        function addCustomSkill(button, category) {
        const container = button.previousElementSibling;

        const wrapper = document.createElement("div");
        wrapper.className = "custom-skill-entry";  // ← 変更ポイント①

        wrapper.innerHTML = `
            <input type="hidden" name="custom_category[]" value="${category}">
            <input type="text" name="custom_skill_name[]" placeholder="スキル名 (例: PHP)" required>
            <select name="custom_skill_level[]" required>
                <option value="">レベルを選択</option>
                <option value="S">S (上級、教育可能)</option>
                <option value="A">A (中級、1人称対応可能)</option>
                <option value="B">B (業務経験あり)</option>
                <option value="C">C (知識のみ、研修レベル)</option>
                <option value="D">D (経験なし)</option>
            </select>
            <button type="button" class="remove-custom-skill">×</button>  <!-- ← 変更ポイント② -->
        `;

        container.appendChild(wrapper);
    }

        // カスタムスキルの削除機能
        document.addEventListener("click", function(e) {
        if (e.target.classList.contains("remove-custom-skill")) {
            e.target.closest(".custom-skill-entry").remove();
        }
    });