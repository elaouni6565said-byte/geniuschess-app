/**
 * GENIUS CHESS ACADEMY (GCA 2026) - CLIENT ENGINE
 * - Bilingual LTR / RTL Switching & Keyboard Shortcuts
 * - Device Display Mode Switcher (PC / Smartphone / Auto)
 * - Responsive Mobile Navigation Drawer
 */

(function () {
    // Early execution to ensure correct attribute before full DOM load
    const savedMode = localStorage.getItem('gca_device_mode') || 'auto';
    document.documentElement.setAttribute('data-device-mode', savedMode);
})();

document.addEventListener('DOMContentLoaded', () => {
    const currentLang = document.documentElement.lang || 'fr';

    /* ==========================================================================
       1. DEVICE DISPLAY MODE SWITCHER (PC / SMARTPHONE / AUTO)
       ========================================================================== */
    const modeLabels = {
        fr: {
            pc: 'Mode PC / Bureau',
            mobile: 'Mode Smartphone',
            auto: 'Automatique (Écran)',
            toast_pc: '💻 Mode Ordinateur activé',
            toast_mobile: '📱 Mode Smartphone activé',
            toast_auto: '🔄 Mode Automatique activé'
        },
        ar: {
            pc: 'وضع الحاسوب',
            mobile: 'وضع الهاتف الذكي',
            auto: 'تلقائي (حسب الشاشة)',
            toast_pc: '💻 تم تفعيل وضع الحاسوب',
            toast_mobile: '📱 تم تفعيل وضع الهاتف الذكي',
            toast_auto: '🔄 تم تفعيل الوضع التلقائي'
        }
    };

    const deviceBtns = document.querySelectorAll('.device-btn');
    const footerLabel = document.getElementById('footerActiveDeviceLabel');

    function showToast(message) {
        let toast = document.getElementById('gcaDeviceToast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'gcaDeviceToast';
            toast.className = 'gca-toast';
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        toast.classList.add('visible');
        clearTimeout(toast._timer);
        toast._timer = setTimeout(() => {
            toast.classList.remove('visible');
        }, 2200);
    }

    function setDeviceMode(mode, showFeedback = false) {
        if (!['pc', 'mobile', 'auto'].includes(mode)) {
            mode = 'auto';
        }

        document.documentElement.setAttribute('data-device-mode', mode);
        try {
            localStorage.setItem('gca_device_mode', mode);
        } catch (e) {}

        // Update button states
        deviceBtns.forEach(btn => {
            if (btn.dataset.mode === mode) {
                btn.classList.add('active');
                btn.setAttribute('aria-pressed', 'true');
            } else {
                btn.classList.remove('active');
                btn.setAttribute('aria-pressed', 'false');
            }
        });

        // Update footer label
        if (footerLabel) {
            const langDict = modeLabels[currentLang] || modeLabels['fr'];
            footerLabel.textContent = langDict[mode] || mode.toUpperCase();
        }

        if (showFeedback) {
            const langDict = modeLabels[currentLang] || modeLabels['fr'];
            showToast(langDict['toast_' + mode] || `Mode ${mode.toUpperCase()}`);
        }
    }

    // Initialize current mode on UI
    const initialMode = localStorage.getItem('gca_device_mode') || 'auto';
    setDeviceMode(initialMode, false);

    deviceBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const targetMode = btn.dataset.mode;
            setDeviceMode(targetMode, true);
        });
    });

    /* ==========================================================================
       2. RESPONSIVE MOBILE NAVIGATION DRAWER
       ========================================================================== */
    const mobileToggle = document.getElementById('gcaMobileNavToggle');
    const navMenu = document.getElementById('gcaNavMenu');

    if (mobileToggle && navMenu) {
        function toggleMobileMenu(forceState) {
            const isOpen = typeof forceState === 'boolean' ? !forceState : navMenu.classList.contains('is-open');
            if (isOpen) {
                navMenu.classList.remove('is-open');
                mobileToggle.classList.remove('open');
                mobileToggle.setAttribute('aria-expanded', 'false');
            } else {
                navMenu.classList.add('is-open');
                mobileToggle.classList.add('open');
                mobileToggle.setAttribute('aria-expanded', 'true');
            }
        }

        mobileToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleMobileMenu();
        });

        // Close menu when clicking outside
        document.addEventListener('click', (e) => {
            if (navMenu.classList.contains('is-open') && !navMenu.contains(e.target) && !mobileToggle.contains(e.target)) {
                toggleMobileMenu(false);
            }
        });

        // Close menu on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && navMenu.classList.contains('is-open')) {
                toggleMobileMenu(false);
            }
        });

        // Close menu on item navigation
        navMenu.querySelectorAll('.nav-item a').forEach(link => {
            link.addEventListener('click', () => {
                toggleMobileMenu(false);
            });
        });
    }

    /* ==========================================================================
       3. BILINGUAL SHORTCUT & INTERACTION
       ========================================================================== */
    // Keyboard Shortcut: Alt + L to toggle language immediately
    document.addEventListener('keydown', (e) => {
        if (e.altKey && (e.key === 'l' || e.key === 'L')) {
            e.preventDefault();
            const nextLang = currentLang === 'fr' ? 'ar' : 'fr';
            window.location.href = `/set-language/${nextLang}/`;
        }
    });

    // Language button visual feedback
    const langButtons = document.querySelectorAll('.lang-btn');
    langButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            btn.style.opacity = '0.7';
        });
    });

    // Search auto-focus
    const searchInput = document.querySelector('.search-input');
    if (searchInput && window.location.search.includes('q=')) {
        searchInput.focus();
    }
});
