/**
 * @file settings-menu.js
 * @description Settings Dropdown Menu Controller for Lanvan.
 * @module SettingsMenu
 */

(function (window) {
  'use strict';

  /**
   * Event handler to close settings dropdown menu when clicking outside
   * @param {MouseEvent} e 
   */
  function closeSettingsOnOutsideClick(e) {
    var settingsMenu = document.getElementById('settingsMenu');
    var settingsBtn = document.getElementById('settingsBtn');
    if (settingsMenu && settingsBtn) {
      if (!settingsMenu.contains(e.target) && !settingsBtn.contains(e.target)) {
        settingsMenu.style.display = 'none';
        document.removeEventListener('click', closeSettingsOnOutsideClick);
      }
    }
  }

  /**
   * Toggle visibility of settings menu dropdown
   */
  function toggleSettingsMenu() {
    var settingsMenu = document.getElementById('settingsMenu');
    if (!settingsMenu) return;

    if (settingsMenu.style.display === 'none' || settingsMenu.style.display === '') {
      settingsMenu.style.display = 'block';
      setTimeout(function () {
        document.addEventListener('click', closeSettingsOnOutsideClick);
      }, 100);
    } else {
      settingsMenu.style.display = 'none';
      document.removeEventListener('click', closeSettingsOnOutsideClick);
    }
  }

  /**
   * Show placeholder toast for access control settings
   */
  function showAccessControlSettings() {
    if (typeof window.showToast === 'function') {
      window.showToast(' Access Control features coming soon! Stay tuned for host-guest permissions, device whitelisting, and access tokens.', 5000);
    }
  }

  const SettingsMenu = Object.freeze({
    toggleSettingsMenu: toggleSettingsMenu,
    showAccessControlSettings: showAccessControlSettings,
    closeSettingsOnOutsideClick: closeSettingsOnOutsideClick
  });

  window.SettingsMenu = SettingsMenu;
  window.toggleSettingsMenu = toggleSettingsMenu;
  window.showAccessControlSettings = showAccessControlSettings;

})(window);
