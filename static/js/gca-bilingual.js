/**
 * GENIUS CHESS ACADEMY (GCA 2026) - BILINGUAL CLIENT ENGINE
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Keyboard Shortcut: Alt + L to toggle language immediately
    document.addEventListener('keydown', (e) => {
        if (e.altKey && (e.key === 'l' || e.key === 'L')) {
            e.preventDefault();
            const currentLang = document.documentElement.lang || 'fr';
            const nextLang = currentLang === 'fr' ? 'ar' : 'fr';
            window.location.href = `/set-language/${nextLang}/`;
        }
    });

    // 2. Immediate feedback on language buttons
    const langButtons = document.querySelectorAll('.lang-btn');
    langButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            btn.style.opacity = '0.7';
        });
    });

    // 3. Search auto-focus and clear
    const searchInput = document.querySelector('.search-input');
    if (searchInput && window.location.search.includes('q=')) {
        searchInput.focus();
    }
});
