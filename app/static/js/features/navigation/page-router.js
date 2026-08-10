/**
 * Lanvan Page Router (page-router.js)
 * Manages view switching between File Transfer and Clipboard pages,
 * page switch dropdown UI, browser history pushState/popstate navigation,
 * and page dynamic update triggers.
 */

(function (window) {
    'use strict';

    if (window.PageRouter && window.PageRouter._initialized) {
        return;
    }

    /**
     * Show/hide dropdown menu for page switching
     * @param {Event} event - Trigger event
     * @param {string} dropdownId - Element ID of target dropdown
     */
    function showSwitchDropdown(event, dropdownId) {
        if (event && typeof event.stopPropagation === 'function') {
            event.stopPropagation();
        }
        var dropdown = document.getElementById(dropdownId);
        if (!dropdown) return;

        if (dropdown.style.display === 'block') {
            dropdown.style.display = 'none';
        } else {
            dropdown.style.display = 'block';
            document.addEventListener('click', function handler(e) {
                if (!dropdown.contains(e.target)) {
                    dropdown.style.display = 'none';
                    document.removeEventListener('click', handler);
                }
            });
        }
    }

    /**
     * Switch active application page view ('file' or 'clipboard')
     * @param {string} page - Target page name
     */
    function switchToPage(page) {
        var dropdowns = [
            document.getElementById('switchDropdownMain'),
            document.getElementById('switchDropdownClipboard')
        ];
        dropdowns.forEach(function (dd) {
            if (dd) dd.style.display = 'none';
        });

        var fileTransferSection = document.getElementById('fileTransferSection');
        var fileListSection = document.getElementById('fileListSection');
        var clipboardSection = document.getElementById('clipboardSection');

        if (page === 'clipboard' && !clipboardSection) {
            window.location.href = '/clipboard';
            return;
        }
        if (page === 'file' && (!fileTransferSection || !fileListSection)) {
            window.location.href = '/';
            return;
        }

        document.documentElement.setAttribute('data-active-tab', page);
        if (typeof window.switchView === 'function') {
            window.switchView(page);
        }

        if (page === 'clipboard') {
            if (typeof window.currentActiveSection !== 'undefined') {
                window.currentActiveSection = 'clipboard';
            }
            if (fileTransferSection) fileTransferSection.style.opacity = '1';
            if (fileListSection) fileListSection.style.opacity = '1';
            if (clipboardSection) clipboardSection.style.opacity = '1';
            history.pushState({ page: 'clipboard' }, 'Lanvan - Clipboard', '/clipboard');
            document.title = 'Lanvan - Clipboard';
        } else if (page === 'file') {
            if (typeof window.currentActiveSection !== 'undefined') {
                window.currentActiveSection = 'file';
            }
            if (fileTransferSection) fileTransferSection.style.opacity = '1';
            if (fileListSection) fileListSection.style.opacity = '1';
            if (clipboardSection) clipboardSection.style.opacity = '1';
            history.pushState({ page: 'file' }, 'Lanvan - File Transfer', '/');
            document.title = 'Lanvan - File Transfer';
        }

        setTimeout(function () {
            if (page === 'file') {
                if (typeof window.refreshFileList === 'function') {
                    window.refreshFileList();
                } else if (typeof window.updateFileList === 'function') {
                    window.updateFileList();
                }
            } else if (page === 'clipboard') {
                if (typeof window.refreshClipboardHistory === 'function') {
                    window.refreshClipboardHistory();
                }
            }
        }, 150);

        if (typeof window.showToast === 'function') {
            var sectionName = page === 'clipboard' ? 'Clipboard' : 'File Transfer';
            window.showToast(' Switched to ' + sectionName, 1500);
        }
    }

    // Wire up popstate listener with standard window.__popstateWired guard
    if (!window.__popstateWired) {
        window.__popstateWired = true;
        window.addEventListener('popstate', function (event) {
            if (event.state && event.state.page) {
                var targetPage = event.state.page;

                if (typeof window.currentActiveSection !== 'undefined') {
                    window.currentActiveSection = targetPage;
                }
                console.log(' Browser navigation - active section: ' + targetPage);

                if (targetPage === 'clipboard') {
                    document.title = 'Lanvan - Clipboard';
                } else {
                    document.title = 'Lanvan - File Transfer';
                }

                if (typeof window.switchView === 'function') {
                    window.switchView(targetPage);
                }
            }
        });
    }

    var PageRouter = Object.freeze({
        _initialized: true,
        showSwitchDropdown: showSwitchDropdown,
        switchToPage: switchToPage
    });

    window.PageRouter = PageRouter;
    window.showSwitchDropdown = showSwitchDropdown;
    window.switchToPage = switchToPage;

})(window);
