// This file contains the JavaScript for the Switch button dropdown and navigation logic
function showSwitchDropdown(event, dropdownId) {
  event.stopPropagation();
  const dropdown = document.getElementById(dropdownId);
  if (dropdown.style.display === 'block') {
    dropdown.style.display = 'none';
  } else {
    dropdown.style.display = 'block';
    // Hide dropdown if clicked outside
    document.addEventListener('click', function handler(e) {
      if (!dropdown.contains(e.target)) {
        dropdown.style.display = 'none';
        document.removeEventListener('click', handler);
      }
    });
  }
}

function switchToPage(page) {
  if (page === 'clipboard') {
    openClipboardModal();
  } else if (page === 'file') {
    // Reload main page (file sharing)
    window.location.href = '/';
  }
}
