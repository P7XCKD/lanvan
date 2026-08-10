/**
 * Lanvan Theme Manager (theme-manager.js)
 * Manages 3-way theme preferences (light, dark, system), DOM attribute updates,
 * system color scheme listeners, and header/settings UI sync.
 */

(function (window) {
    'use strict';

    if (window.ThemeManager && window.ThemeManager._initialized) {
        return;
    }

    var DOM_CACHE = window.DOM_CACHE || {};

    function updateProtocolStatusHover(isDarkMode) {
        var protocolStatus = DOM_CACHE.protocolStatus || document.getElementById('protocolStatus');
        if (protocolStatus) {
            if (isDarkMode) {
                protocolStatus.onmouseover = function () { this.style.backgroundColor = '#1e40af'; };
                protocolStatus.onmouseout = function () { this.style.backgroundColor = 'var(--protocol-bg)'; };
            } else {
                protocolStatus.onmouseover = function () { this.style.backgroundColor = '#d0e9f7'; };
                protocolStatus.onmouseout = function () { this.style.backgroundColor = 'var(--protocol-bg)'; };
            }
        }
    }

    function fixRemainingColors(isDarkMode) {
        if (isDarkMode) {
            var darkTextElements = document.querySelectorAll('[style*="color: #333"], [style*="color:#333"], [style*="color: #666"], [style*="color:#666"], [style*="color: #999"], [style*="color:#999"]');
            darkTextElements.forEach(function (el) {
                el.style.color = 'var(--text-color)';
            });

            var whiteBgElements = document.querySelectorAll('[style*="background: #fff"], [style*="background-color: #fff"], [style*="background: #f8f9fa"], [style*="background: white"]');
            whiteBgElements.forEach(function (el) {
                el.style.backgroundColor = 'var(--section-bg)';
                el.style.color = 'var(--text-color)';
            });

            var fileNameElements = document.querySelectorAll('.file-name, .upload-file-name');
            fileNameElements.forEach(function (el) {
                el.style.color = 'var(--text-color)';
            });

            var clipboardElements = document.querySelectorAll('#clipboardHistoryContent div');
            clipboardElements.forEach(function (el) {
                if (el.style.color && (el.style.color.includes('#333') || el.style.color.includes('#666') || el.style.color.includes('#999'))) {
                    el.style.color = 'var(--text-color)';
                }
            });

            var textElements = document.querySelectorAll('label, span:not(.slider), .file-name, strong');
            textElements.forEach(function (el) {
                if (el.id === 'qrHintText' && el.innerHTML.includes('mDNS:')) {
                    return;
                }
                if (!el.classList.contains('slider') && !el.classList.contains('toggle-text')) {
                    if (el.style.color && (el.style.color.includes('#333') || el.style.color.includes('#666'))) {
                        el.style.color = 'var(--text-color)';
                    }
                }
            });
        } else {
            var allElements = document.querySelectorAll('*');
            allElements.forEach(function (el) {
                if (el.style.color && el.style.color.includes('var(--text-color)')) {
                    el.style.color = '';
                }
                if (el.style.backgroundColor && el.style.backgroundColor.includes('var(--')) {
                    el.style.backgroundColor = '';
                }
            });
        }
    }

    function applyDarkMode(isDarkMode) {
        if (isDarkMode) {
            document.documentElement.setAttribute('data-theme', 'dark');
        } else {
            document.documentElement.setAttribute('data-theme', 'light');
        }

        var darkModeLabel = document.getElementById('darkModeLabel');
        if (darkModeLabel) {
            if (isDarkMode) {
                darkModeLabel.innerHTML = '<b> Dark Mode</b>';
            } else {
                darkModeLabel.innerHTML = '<b> Light Mode</b>';
            }
        }

        updateProtocolStatusHover(isDarkMode);
        fixRemainingColors(isDarkMode);
    }

    function applyThemePreference(themePref) {
        if (!themePref) {
            themePref = localStorage.getItem('theme_preference');
            if (themePref === null) {
                var legacyDark = localStorage.getItem('dark_mode_enabled');
                if (legacyDark !== null) {
                    themePref = legacyDark === '1' ? 'dark' : 'light';
                } else {
                    themePref = 'system';
                }
                localStorage.setItem('theme_preference', themePref);
            }
        }

        var isDarkMode = false;
        if (themePref === 'dark') {
            isDarkMode = true;
        } else if (themePref === 'light') {
            isDarkMode = false;
        } else {
            isDarkMode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        }

        applyDarkMode(isDarkMode);

        var themeLightRadio = document.getElementById('themeLight');
        var themeDarkRadio = document.getElementById('themeDark');
        var themeSystemRadio = document.getElementById('themeSystem');

        if (themeLightRadio && themeDarkRadio && themeSystemRadio) {
            themeLightRadio.checked = themePref === 'light';
            themeDarkRadio.checked = themePref === 'dark';
            themeSystemRadio.checked = themePref === 'system';
        }

        if (DOM_CACHE.darkModeToggle) {
            DOM_CACHE.darkModeToggle.checked = isDarkMode;
        }
        var settingsToggle = document.getElementById("darkThemeSettingToggle");
        if (settingsToggle) {
            settingsToggle.checked = isDarkMode;
        }

        var themeIcon = document.getElementById('themeSettingIcon');
        var themeTitle = document.getElementById('themeSettingTitle');
        var themeDesc = document.getElementById('themeSettingDesc');

        if (themeIcon && themeTitle && themeDesc) {
            if (themePref === 'light') {
                themeIcon.setAttribute('data-lucide', 'sun');
                themeTitle.textContent = 'Light Theme';
                themeDesc.textContent = 'Use clean light mode interface';
            } else if (themePref === 'dark') {
                themeIcon.setAttribute('data-lucide', 'moon');
                themeTitle.textContent = 'Dark Theme';
                themeDesc.textContent = 'Use sleek dark mode interface';
            } else {
                themeIcon.setAttribute('data-lucide', 'monitor');
                themeTitle.textContent = 'System Theme';
                themeDesc.textContent = "Follow device's theme settings";
            }
            if (window.refreshLucideIcons) {
                window.refreshLucideIcons(themeIcon ? themeIcon.parentElement : null);
            } else if (window.lucide && typeof window.lucide.createIcons === 'function') {
                window.lucide.createIcons();
            }
        }

        var headerToggleBtn = document.querySelector('button[onclick="toggleDarkMode()"]');
        if (headerToggleBtn) {
            var iconEl = headerToggleBtn.querySelector('i');
            if (iconEl) {
                var iconName = 'monitor';
                if (themePref === 'light') iconName = 'sun';
                else if (themePref === 'dark') iconName = 'moon';
                iconEl.setAttribute('data-lucide', iconName);
                if (window.refreshLucideIcons) {
                    window.refreshLucideIcons(headerToggleBtn);
                } else if (window.lucide && typeof window.lucide.createIcons === 'function') {
                    window.lucide.createIcons();
                }
            }
        }
    }

    // Run initialization
    applyThemePreference(null);

    // Dynamic system theme change listener
    if (window.matchMedia) {
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (e) {
            var themePref = localStorage.getItem('theme_preference') || 'system';
            if (themePref === 'system') {
                applyDarkMode(e.matches);
            }
        });
    }

    var ThemeManager = Object.freeze({
        _initialized: true,
        applyThemePreference: applyThemePreference,
        applyDarkMode: applyDarkMode
    });

    window.ThemeManager = ThemeManager;
    window.applyThemePreference = applyThemePreference;
    window.applyDarkMode = applyDarkMode;

})(window);
