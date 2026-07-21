// Helper escapeHtml function
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

// Mock directory structure
const db = {
  "Home": [
    { name: "DesignAssets", type: "folder", itemsCount: 12, modified: "Today", starred: true },
    { name: "photo_shoot_2025.png", type: "image", size: "2.4 MB", modified: "Yesterday", starred: false },
    { name: "Quarterly_Report.pdf", type: "doc", size: "450 KB", modified: "Jul 18", starred: true },
    { name: "podcast_interview.mp3", type: "audio", size: "8.4 MB", modified: "Jul 18", starred: false },
    { name: "backup_2025.zip", type: "archive", size: "142 MB", modified: "Jul 16", starred: true }
  ],
  "Home/DesignAssets": [
    { name: "brand_guide.pdf", type: "doc", size: "4.8 MB", modified: "Today", starred: false },
    { name: "app_logo.png", type: "image", size: "512 KB", modified: "Yesterday", starred: true },
    { name: "marketing_videos", type: "folder", itemsCount: 3, modified: "Jul 17", starred: false }
  ],
  "Home/DesignAssets/marketing_videos": [
    { name: "promo_intro.mp4", type: "video", size: "12.8 MB", modified: "Today", starred: false },
    { name: "customer_review.mp4", type: "video", size: "15.2 MB", modified: "Jul 16", starred: true }
  ]
};

let currentPath = ["Home"];
let activeTab = "file";
let viewMode = "list";
let typeFilter = "all";
let searchQuery = "";
let connectMode = "ip";
let selectedItems = [];
let lastSelectedIndex = -1;
let isCreatingFolderInMove = false;
let sortBy = "name";
let sortDirection = "asc";
let sortFolders = "top";

function setViewMode(mode) {
  viewMode = mode;
  updateViewModeDOM();
  renderDirectory();
}

function updateViewModeDOM() {
  const fileList = document.getElementById("nasFileList");
  const fileTableHead = document.getElementById("fileTableHead");
  const listBtn = document.getElementById("listViewBtn");
  const gridBtn = document.getElementById("gridViewBtn");

  const switcherPills = document.querySelectorAll(".view-switcher-pill");
  switcherPills.forEach(pill => {
    pill.style.display = "flex";
  });

  if (fileList) {
    if (viewMode === "grid") {
      fileList.classList.add("grid-mode");
      if (fileTableHead) fileTableHead.style.display = "none";
    } else {
      fileList.classList.remove("grid-mode");
      if (fileTableHead) fileTableHead.style.display = "grid";
    }
  }

  if (listBtn) listBtn.classList.toggle("active", viewMode === "list");
  if (gridBtn) gridBtn.classList.toggle("active", viewMode === "grid");
}

const connectionTargets = {
  ip: "http://192.168.1.42:5000",
  mdns: "http://lanvan.local:5000"
};
const clipboardItems = [
  { text: "https://github.com/P7XCKD/lanvan", kind: "Link", created: "Pasted 2 mins ago" }
];

function getCurrentDirectoryItems() {
  const pathStr = currentPath.join("/");
  return db[pathStr] || [];
}

function getAllItems() {
  return Object.entries(db).flatMap(([path, items]) => {
    return items.map(item => ({ ...item, parentPath: path }));
  });
}

function getVisibleItems() {
  let items = getCurrentDirectoryItems();

  if (activeTab === "recent") {
    items = getAllItems().slice().sort((a, b) => {
      const rank = { "Today": 0, "Yesterday": 1, "Jul 18": 2, "Jul 17": 3, "Jul 16": 4 };
      return (rank[a.modified] ?? 99) - (rank[b.modified] ?? 99);
    });
  } else if (activeTab === "starred") {
    items = getAllItems().filter(item => item.starred);
  }

  if (typeFilter !== "all") {
    items = items.filter(item => item.type === typeFilter);
  }

  if (searchQuery.trim()) {
    const needle = searchQuery.trim().toLowerCase();
    items = items.filter(item => item.name.toLowerCase().includes(needle));
  }

  return sortItems(items);
}

function parseSizeToBytes(sizeStr, isFolder) {
  if (isFolder) return -1;
  if (!sizeStr) return 0;
  const str = String(sizeStr).toUpperCase().trim();
  const match = str.match(/^([\d.]+)\s*([KMG]?B)$/);
  if (!match) return 0;
  const val = parseFloat(match[1]);
  const unit = match[2];
  if (unit === "KB") return val * 1024;
  if (unit === "MB") return val * 1024 * 1024;
  if (unit === "GB") return val * 1024 * 1024 * 1024;
  return val;
}

function sortItems(itemsList) {
  const list = [...itemsList];
  list.sort((a, b) => {
    if (sortFolders === "top") {
      if (a.type === "folder" && b.type !== "folder") return -1;
      if (a.type !== "folder" && b.type === "folder") return 1;
    }

    let comparison = 0;
    if (sortBy === "name") {
      comparison = a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' });
    } else if (sortBy === "date") {
      const rank = { "Today": 0, "Yesterday": 1, "Jul 18": 2, "Jul 17": 3, "Jul 16": 4 };
      const rankA = rank[a.modified] ?? 99;
      const rankB = rank[b.modified] ?? 99;
      comparison = rankA - rankB;
    } else if (sortBy === "size") {
      const bytesA = parseSizeToBytes(a.size, a.type === "folder");
      const bytesB = parseSizeToBytes(b.size, b.type === "folder");
      comparison = bytesA - bytesB;
    }

    return sortDirection === "asc" ? comparison : -comparison;
  });
  return list;
}

function toggleSortMenu(event) {
  event.stopPropagation();
  const menu = document.getElementById("sortDropdownMenu");
  if (!menu) return;
  const isVisible = menu.style.display === "block";
  closeContextMenu();
  if (!isVisible) {
    updateSortCheckmarks();
    const rect = event.currentTarget.getBoundingClientRect();
    menu.style.display = "block";
    const menuHeight = 280;
    let top = rect.bottom + 6;
    if (top + menuHeight > window.innerHeight) {
      top = Math.max(10, rect.top - menuHeight - 4);
    }
    let left = Math.max(10, rect.right - 180);
    menu.style.left = left + "px";
    menu.style.top = top + "px";
  } else {
    menu.style.display = "none";
  }
}

function setSortOption(category, value) {
  if (category === "by") sortBy = value;
  else if (category === "direction") sortDirection = value;
  else if (category === "folders") sortFolders = value;

  updateSortCheckmarks();
  renderDirectory();
}

function updateSortCheckmarks() {
  const byName = document.getElementById("check-by-name");
  const byDate = document.getElementById("check-by-date");
  const bySize = document.getElementById("check-by-size");
  if (byName) byName.style.visibility = sortBy === "name" ? "visible" : "hidden";
  if (byDate) byDate.style.visibility = sortBy === "date" ? "visible" : "hidden";
  if (bySize) bySize.style.visibility = sortBy === "size" ? "visible" : "hidden";

  const dirAsc = document.getElementById("check-dir-asc");
  const dirDesc = document.getElementById("check-dir-desc");
  if (dirAsc) dirAsc.style.visibility = sortDirection === "asc" ? "visible" : "hidden";
  if (dirDesc) dirDesc.style.visibility = sortDirection === "desc" ? "visible" : "hidden";

  const foldTop = document.getElementById("check-folders-top");
  const foldMixed = document.getElementById("check-folders-mixed");
  if (foldTop) foldTop.style.visibility = sortFolders === "top" ? "visible" : "hidden";
  if (foldMixed) foldMixed.style.visibility = sortFolders === "mixed" ? "visible" : "hidden";
}

function handleHeaderSortClick(column) {
  if (sortBy === column) {
    sortDirection = sortDirection === "asc" ? "desc" : "asc";
  } else {
    sortBy = column;
    sortDirection = "asc";
  }
  updateSortHeaderArrows();
  updateSortCheckmarks();
  renderDirectory();
}

function updateSortHeaderArrows() {
  const arrowName = document.getElementById("sortArrow-name");
  const arrowDate = document.getElementById("sortArrow-date");
  const arrowSize = document.getElementById("sortArrow-size");

  const iconMarkup = sortDirection === "asc"
    ? `<span style="display:inline-flex; align-items:center; justify-content:center; width:18px; height:18px; border-radius:50%; background:var(--secondary-container); color:var(--primary); margin-left:2px;" title="${sortDirection === 'asc' ? 'A to Z' : 'Z to A'}"><i data-lucide="arrow-down" style="width:12px;height:12px;"></i></span>`
    : `<span style="display:inline-flex; align-items:center; justify-content:center; width:18px; height:18px; border-radius:50%; background:var(--secondary-container); color:var(--primary); margin-left:2px;" title="${sortDirection === 'asc' ? 'A to Z' : 'Z to A'}"><i data-lucide="arrow-up" style="width:12px;height:12px;"></i></span>`;

  if (arrowName) arrowName.innerHTML = sortBy === "name" ? iconMarkup : "";
  if (arrowDate) arrowDate.innerHTML = sortBy === "date" ? iconMarkup : "";
  if (arrowSize) arrowSize.innerHTML = sortBy === "size" ? iconMarkup : "";
  lucide.createIcons();
}

function getActiveListTitle() {
  if (activeTab === "recent") return "Recent";
  if (activeTab === "starred") return "Starred";
  return currentPath[currentPath.length - 1] + " Directory";
}

function setSearchQuery(value) {
  searchQuery = value;
  renderDirectory();
}

function toggleTypeDropdown(event) {
  event.stopPropagation();
  const menu = document.getElementById("typeDropdownMenu");
  if (!menu) return;
  const isVisible = menu.style.display === "block";
  closeContextMenu();
  menu.style.display = isVisible ? "none" : "block";
}

function clearTypeFilter(event) {
  if (event) event.stopPropagation();
  setTypeFilter('all');
}

function setTypeFilter(type) {
  typeFilter = type;
  const wrapper = document.getElementById("typeBtnWrapper");
  if (wrapper) {
    if (type === "all") {
      wrapper.innerHTML = `
        <button class="filter-chip" id="typeDropdownBtn" onclick="toggleTypeDropdown(event)" style="display: flex; align-items: center; gap: 0.35rem; font-size: 0.76rem; font-weight: 700; border: 1px solid var(--border-color); background: var(--card-bg); color: var(--text-color); border-radius: 999px; padding: 0.45rem 0.8rem; cursor: pointer;">
          <span>Type</span>
          <i data-lucide="chevron-down" style="width: 12px; height: 12px;"></i>
        </button>
      `;
    } else {
      const labelMap = {
        folder: "Folder",
        image: "Photos",
        video: "Videos",
        audio: "Audio",
        doc: "Documents",
        archive: "Archives"
      };
      const text = labelMap[type] || "Type";
      wrapper.innerHTML = `
        <div class="filter-chip active" id="typeDropdownBtn" style="display: flex; align-items: center; padding: 0; border: none; background: var(--primary-container); border-radius: 999px; overflow: hidden; height: 30px;">
          <button onclick="toggleTypeDropdown(event)" style="display: flex; align-items: center; gap: 0.25rem; font-size: 0.76rem; font-weight: 700; background: transparent; border: none; color: var(--primary); padding: 0.45rem 0.55rem 0.45rem 0.85rem; cursor: pointer; height: 100%;">
            <span>Type: ${text}</span>
            <i data-lucide="chevron-down" style="width: 12px; height: 12px;"></i>
          </button>
          <span style="width: 1px; height: 14px; background: rgba(11, 87, 208, 0.25); display: inline-block;"></span>
          <button onclick="clearTypeFilter(event)" style="display: flex; align-items: center; justify-content: center; background: transparent; border: none; color: var(--primary); width: 28px; height: 100%; padding: 0; cursor: pointer;" title="Clear filter">
            <i data-lucide="x" style="width: 13px; height: 13px;"></i>
          </button>
        </div>
      `;
    }
  }

  const menu = document.getElementById("typeDropdownMenu");
  if (menu) {
    menu.style.display = "none";
    const checkmarks = {
      all: "check",
      image: "image",
      video: "video",
      audio: "music",
      doc: "file-text",
      folder: "folder",
      archive: "archive"
    };

    const items = menu.querySelectorAll(".context-item");
    items.forEach((item, idx) => {
      const icon = item.querySelector("i");
      if (icon) {
        const keys = Object.keys(checkmarks);
        const itemType = keys[idx];
        if (itemType === type) {
          icon.setAttribute("data-lucide", "check");
          icon.style.color = "var(--primary)";
        } else {
          icon.setAttribute("data-lucide", checkmarks[itemType]);
          icon.style.color = "";
        }
      }
    });
  }

  lucide.createIcons();
  clearSelection();
}

function handleDownloadItem(name) {
  alert("Downloading: " + name);
}

function handleRenameClick(name) {
  selectedItems = [name];
  renderDirectory();
  openRenameModal();
}

function selectQuickItem(name, parentPath) {
  activeTab = "file";
  currentPath = parentPath.split("/");
  typeFilter = "all";
  searchQuery = "";
  const input = document.getElementById("searchInput");
  if (input) input.value = "";
  selectedItems = [name];
  lastSelectedIndex = -1;
  renderDirectory();
}

function renderQuickAccess() {
  const container = document.getElementById("quickAccessContainer");
  if (!container) return;

  const allFiles = getAllItems().filter(item => item.type !== 'folder');
  const rank = { "Today": 0, "Yesterday": 1, "Jul 18": 2, "Jul 17": 3, "Jul 16": 4 };
  allFiles.sort((a, b) => {
    return (rank[a.modified] ?? 99) - (rank[b.modified] ?? 99);
  });

  const recent4 = allFiles.slice(0, 4);

  container.innerHTML = "";
  recent4.forEach(item => {
    const card = document.createElement("div");
    card.className = "quick-card";
    if (selectedItems.includes(item.name)) {
      card.classList.add("selected");
    }

    let avatarClass = "avatar-doc";
    let iconName = "file-text";
    if (item.type === "image") {
      avatarClass = "avatar-image";
      iconName = "image";
    } else if (item.type === "video") {
      avatarClass = "avatar-video";
      iconName = "video";
    } else if (item.type === "audio") {
      avatarClass = "avatar-audio";
      iconName = "music";
    } else if (item.type === "archive") {
      avatarClass = "avatar-archive";
      iconName = "archive";
    }

    card.onclick = () => {
      selectQuickItem(item.name, item.parentPath);
    };

    card.innerHTML = `
      <div class="quick-icon ${avatarClass}"><i data-lucide="${iconName}"></i></div>
      <div class="quick-copy" style="flex: 1; min-width: 0;">
        <div class="quick-title">${escapeHtml(item.name)}</div>
        <div class="quick-subtitle">${item.type.toUpperCase()} - ${item.size}</div>
      </div>
      <div class="quick-hover-actions">
        <button class="btn-icon" onclick="event.stopPropagation(); handleDownloadItem('${escapeHtml(item.name.replaceAll("'", "\\'"))}')" title="Download" style="width:24px;height:24px;padding:0;display:flex;align-items:center;justify-content:center;background:transparent;border:none;">
          <i data-lucide="download" style="width:14px;height:14px;color:var(--text-muted);"></i>
        </button>
        <button class="btn-icon" onclick="openRowMenu(event, '${escapeHtml(item.name.replaceAll("'", "\\'"))}', '${escapeHtml(item.type)}')" title="More actions" style="width:24px;height:24px;padding:0;display:flex;align-items:center;justify-content:center;background:transparent;border:none;">
          <i data-lucide="more-vertical" style="width:14px;height:14px;color:var(--text-muted);"></i>
        </button>
      </div>
    `;
    container.appendChild(card);
  });
  lucide.createIcons();
}

function openRowMenu(event, name, type) {
  event.stopPropagation();

  // Capture button bounding rect BEFORE renderDirectory re-renders DOM elements
  const btn = event.currentTarget;
  const rect = btn && btn.getBoundingClientRect ? btn.getBoundingClientRect() : { left: 100, top: 100, bottom: 130, right: 130 };

  closeContextMenu();

  // If clicked item is not in current selection, select only this item
  if (!selectedItems.includes(name) || selectedItems.length <= 1) {
    selectedItems = [name];
  }
  renderDirectory();

  const genericOptions = document.getElementById("genericMenuOptions");
  const itemOptions = document.getElementById("itemMenuOptions");
  if (genericOptions) genericOptions.style.display = "none";
  if (itemOptions) itemOptions.style.display = "block";

  const isSingle = selectedItems.length === 1;
  const targetName = isSingle ? selectedItems[0] : name;
  const item = getCurrentDirectoryItems().find(i => i.name === targetName) ||
    getAllItems().find(i => i.name === targetName);

  // Hide single-item-only options like Rename if multiple items selected
  const renameOption = document.querySelector("#itemMenuOptions .context-item[onclick*='openRenameModal']");
  if (renameOption) {
    renameOption.style.display = isSingle ? "flex" : "none";
  }

  const starText = document.getElementById("menuStarText");
  const starIcon = document.getElementById("menuStarIcon");
  if (starText && item) {
    starText.textContent = item.starred ? "Remove Star" : "Add to Starred";
  }
  if (starIcon && item) {
    starIcon.style.fill = item.starred ? "var(--yellow)" : "none";
    starIcon.style.color = item.starred ? "var(--yellow)" : "currentColor";
    starIcon.style.stroke = item.starred ? "var(--yellow)" : "currentColor";
  }

  const contextMenu = document.getElementById("contextMenu");
  if (!contextMenu) return;

  contextMenu.style.display = "block";
  lucide.createIcons();

  const menuHeight = contextMenu.offsetHeight || 180;
  const menuWidth = contextMenu.offsetWidth || 170;

  let left = rect.right - menuWidth;
  if (left < 10) left = rect.left;
  if (left + menuWidth > window.innerWidth - 10) {
    left = window.innerWidth - menuWidth - 10;
  }

  let top = rect.bottom + 4;
  if (top + menuHeight > window.innerHeight - 10) {
    top = rect.top - menuHeight - 4;
  }
  if (top < 10) top = 10;

  contextMenu.style.left = left + "px";
  contextMenu.style.top = top + "px";
  console.log(`[MENU] Opened row menu at left: ${left}px, top: ${top}px for item '${name}'`);
}

function handleMenuStarToggle() {
  if (selectedItems.length === 1) {
    const item = getCurrentDirectoryItems().find(i => i.name === selectedItems[0]) ||
      getAllItems().find(i => i.name === selectedItems[0]);
    if (item) {
      toggleStar(item.name, item.parentPath || currentPath.join("/"));
    }
  }
  closeContextMenu();
}

function renderBreadcrumbs() {
  const container = document.getElementById("breadcrumbsContainer");
  if (!container) return;
  container.innerHTML = "";

  const panelTitleIcon = document.getElementById("desktopPanelTitleIcon");
  if (panelTitleIcon) {
    const isMobileFileView = isMobileInteraction() && activeTab === "file";
    const isNestedFolder = isMobileFileView && currentPath.length > 1;
    panelTitleIcon.style.display = isNestedFolder ? "none" : "";
  }

  if (isMobileInteraction() && activeTab === "file") {
    const title = document.createElement("span");
    title.className = "mobile-breadcrumb-title";
    title.textContent = currentPath[currentPath.length - 1] === "Home" ? "My files" : currentPath[currentPath.length - 1];

    if (currentPath.length > 1) {
      const backBtn = document.createElement("button");
      backBtn.type = "button";
      backBtn.className = "mobile-breadcrumb-back";
      backBtn.innerHTML = '<i data-lucide="arrow-left" style="width:16px;height:16px;"></i>';
      backBtn.title = "Go back";
      backBtn.onclick = () => {
        if (currentPath.length <= 1) return;
        currentPath = currentPath.slice(0, -1);
        selectedItems = [];
        lastSelectedIndex = -1;
        renderDirectory();
      };
      container.appendChild(backBtn);
    }

    container.appendChild(title);
    lucide.createIcons();
    return;
  }

  if (activeTab === "recent" || activeTab === "starred") {
    const item = document.createElement("span");
    item.className = "breadcrumb-item";
    item.textContent = activeTab === "recent" ? "Recent" : "Starred";
    container.appendChild(item);
    return;
  }

  currentPath.forEach((folder, idx) => {
    if (idx > 0) {
      const sep = document.createElement("span");
      sep.className = "breadcrumb-separator";
      sep.innerHTML = '<i data-lucide="chevron-right" style="width:16px;height:16px;"></i>';
      container.appendChild(sep);
    }

    const item = document.createElement("span");
    item.className = "breadcrumb-item";
    item.textContent = (idx === 0 && folder === "Home") ? "My files" : folder;
    if (idx < currentPath.length - 1) {
      item.onclick = () => {
        currentPath = currentPath.slice(0, idx + 1);
        selectedItems = [];
        lastSelectedIndex = -1;
        renderDirectory();
      };
    }
    container.appendChild(item);
  });
  lucide.createIcons();
}

function renderDirectory() {
  const quickContainer = document.getElementById("quickAccessContainer");
  if (quickContainer) {
    quickContainer.style.display = (activeTab === "recent" || activeTab === "starred" || currentPath.length > 1) ? "none" : "grid";
  }

  renderBreadcrumbs();
  renderQuickAccess();
  updateViewModeDOM();
  updateSortHeaderArrows();

  const fileList = document.getElementById("nasFileList");
  if (!fileList) return;
  fileList.innerHTML = "";
  const panelMeta = document.getElementById("filePanelMeta");
  if (panelMeta) {
    panelMeta.textContent = activeTab === "recent"
      ? "Recently changed items"
      : activeTab === "starred"
        ? "Important files and folders"
        : "";
  }

  const items = getVisibleItems();

  if (items.length === 0) {
    fileList.innerHTML = `
      <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding: 3rem 0; width: 100%; grid-column: 1 / -1;">
        <div class="avatar-icon avatar-folder" style="width:72px;height:72px;border-radius:18px;margin-bottom:1rem;"><i data-lucide="folder-open" style="width:34px;height:34px;"></i></div>
        <div style="font-size: 1.05rem; font-weight: 500; color: var(--text-color); margin-bottom: 0.25rem;">Drop files here</div>
        <div style="font-size: 0.8rem; color: var(--text-muted);">or right-click to upload / create folders.</div>
      </div>
    `;
    lucide.createIcons();
    return;
  }

  items.forEach(item => {
    const row = document.createElement("div");
    row.className = "m3-list-item";
    if (selectedItems.includes(item.name)) {
      row.classList.add("selected");
    }

    let avatarClass = "avatar-doc";
    let iconName = "file-text";
    if (item.type === "folder") {
      avatarClass = "avatar-folder";
      iconName = "folder";
    } else if (item.type === "image") {
      avatarClass = "avatar-image";
      iconName = "image";
    } else if (item.type === "video") {
      avatarClass = "avatar-video";
      iconName = "video";
    } else if (item.type === "audio") {
      avatarClass = "avatar-audio";
      iconName = "music";
    } else if (item.type === "archive") {
      avatarClass = "avatar-archive";
      iconName = "archive";
    }

    let count = 0;
    if (item.type === "folder") {
      const folderPath = (item.parentPath || currentPath.join("/")) + "/" + item.name;
      count = db[folderPath] ? db[folderPath].length : 0;
    }
    const subtitle = item.type === "folder" ? `${count} items` : item.size;
    const modified = activeTab === "recent" || activeTab === "starred" ? (item.parentPath || currentPath.join("/")) : (item.modified || "Today");
    const size = item.type === "folder" ? "-" : item.size;

    if (viewMode === "grid") {
      let previewMarkup = "";
      if (item.type === "image") {
        previewMarkup = `
          <div class="grid-card-preview" style="padding:0; background:#1a1c22;">
            <svg width="100%" height="100%" viewBox="0 0 240 140" preserveAspectRatio="xMidYMid slice" style="display:block;">
              <rect width="240" height="140" fill="#2d3748"/>
              <path d="M0 100 L70 40 L130 90 L180 50 L240 110 L240 140 L0 140 Z" fill="#4a5568"/>
              <circle cx="180" cy="35" r="14" fill="#ecc94b"/>
              <path d="M40 110 L100 60 L160 110 Z" fill="#718096"/>
            </svg>
          </div>
        `;
      } else if (item.type === "video") {
        previewMarkup = `
          <div class="grid-card-preview" style="padding:0;">
            <div class="video-preview-box">
              <div class="video-play-badge">
                <i data-lucide="play" style="width:20px;height:20px;margin-left:2px;fill:white;"></i>
              </div>
            </div>
          </div>
        `;
      } else if (item.type === "doc") {
        previewMarkup = `
          <div class="grid-card-preview">
            <div class="doc-preview-sheet">
              <div class="doc-preview-line title"></div>
              <div class="doc-preview-line"></div>
              <div class="doc-preview-line"></div>
              <div class="doc-preview-line short"></div>
              <div style="margin-top:auto; display:flex; justify-content:center; align-items:center; flex:1;">
                <i data-lucide="file-text" style="width:32px;height:32px;color:var(--red);opacity:0.8;"></i>
              </div>
            </div>
          </div>
        `;
      } else if (item.type === "folder") {
        previewMarkup = `
          <div class="grid-card-preview" style="background:var(--card-bg);">
            <i data-lucide="folder" style="width:64px;height:64px;color:var(--primary);stroke-width:1.5;"></i>
          </div>
        `;
      } else {
        previewMarkup = `
          <div class="grid-card-preview">
            <i data-lucide="${iconName}" style="width:48px;height:48px;color:var(--text-muted);opacity:0.6;"></i>
          </div>
        `;
      }

      row.innerHTML = `
        <div class="grid-card-head">
          <div style="display:flex; align-items:center; gap:0.45rem; min-width:0; flex:1;">
            <div class="avatar-icon ${avatarClass}"><i data-lucide="${iconName}"></i></div>
            <span class="item-title" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</span>
          </div>
          <button class="btn-icon" onclick="openRowMenu(event, '${escapeHtml(item.name.replaceAll("'", "\\'"))}', '${escapeHtml(item.type)}')" title="More actions" style="width:28px;height:28px;padding:0;flex-shrink:0;">
            <i data-lucide="more-vertical" style="width:14px;height:14px;color:var(--text-muted);"></i>
          </button>
        </div>
        ${previewMarkup}
      `;
    } else {
      const showInlineRowActions = !isMobileInteraction();
      row.innerHTML = `
        <div class="file-name-cell">
          <div class="avatar-icon ${avatarClass}"><i data-lucide="${iconName}"></i></div>
          <div class="item-main">
            <div class="item-title">${escapeHtml(item.name)}</div>
            <div class="item-subtitle">${subtitle}</div>
          </div>
        </div>
        <div class="item-date">${modified}</div>
        <div class="item-size">${size}</div>
        <div class="row-actions">
          ${showInlineRowActions ? `<button class="btn-icon hover-btn" onclick="event.stopPropagation(); handleDownloadItem('${escapeHtml(item.name.replaceAll("'", "\\'"))}')" title="Download" style="color:var(--text-muted);">
            <i data-lucide="download" style="width:16px;height:16px;"></i>
          </button>
          <button class="btn-icon hover-btn" onclick="event.stopPropagation(); handleRenameClick('${escapeHtml(item.name.replaceAll("'", "\\'"))}')" title="Rename" style="color:var(--text-muted);">
            <i data-lucide="edit-2" style="width:16px;height:16px;"></i>
          </button>
          <button class="btn-icon hover-btn ${item.starred ? 'starred-btn' : ''}" onclick="event.stopPropagation(); toggleStar('${escapeHtml(item.name.replaceAll("'", "\\'"))}', '${escapeHtml((item.parentPath || currentPath.join("/")).replaceAll("'", "\\'"))}')" title="Star">
            <i data-lucide="star" style="width:16px;height:16px;"></i>
          </button>` : ''}
          <button class="btn-icon" onclick="openRowMenu(event, '${escapeHtml(item.name.replaceAll("'", "\\'"))}', '${escapeHtml(item.type)}')" title="More actions" style="color:var(--text-muted);">
            <i data-lucide="more-vertical" style="width:16px;height:16px;"></i>
          </button>
        </div>
      `;
    }

    row.addEventListener("click", (e) => {
      if (e.target.closest("button")) return;
      e.stopPropagation();

      const idx = items.indexOf(item);
      const isMobile = document.getElementById("simFrame").classList.contains("mobile-sim") || window.innerWidth < 768;

      if (e.shiftKey && lastSelectedIndex !== -1) {
        const start = Math.min(lastSelectedIndex, idx);
        const end = Math.max(lastSelectedIndex, idx);
        selectedItems = [];
        for (let i = start; i <= end; i++) {
          selectedItems.push(items[i].name);
        }
      } else if (selectedItems.length > 0) {
        const pos = selectedItems.indexOf(item.name);
        if (pos > -1) {
          selectedItems.splice(pos, 1);
        } else {
          selectedItems.push(item.name);
        }
        lastSelectedIndex = idx;
      } else {
        if (isMobile && item.type === "folder") {
          currentPath = (item.parentPath || currentPath.join("/")).split("/");
          currentPath.push(item.name);
          activeTab = "file";
          selectedItems = [];
          lastSelectedIndex = -1;
        } else {
          selectedItems = [item.name];
          lastSelectedIndex = idx;
        }
      }
      renderDirectory();
    });

    row.addEventListener("dblclick", (e) => {
      if (isMobileInteraction()) return;
      if (e.target.closest("button")) return;
      e.stopPropagation();

      if (item.type === "folder") {
        currentPath = (item.parentPath || currentPath.join("/")).split("/");
        currentPath.push(item.name);
        activeTab = "file";
        selectedItems = [];
        lastSelectedIndex = -1;
        renderDirectory();
      }
    });

    fileList.appendChild(row);
  });

  renderSelectionHeader();
  lucide.createIcons();
}

function renderSelectionHeader() {
  const defaultContent = document.getElementById("toolbarDefaultContent");
  const selectionContent = document.getElementById("toolbarSelectionContent");
  if (!defaultContent || !selectionContent) return;

  if (selectedItems.length > 0) {
    defaultContent.style.display = "none";
    selectionContent.style.display = "flex";
    selectionContent.innerHTML = `
      <div style="display: flex; align-items: center; gap: 0.5rem; font-size: 0.85rem; font-weight: 700; color: var(--primary);">
        <button class="btn-icon" onclick="clearSelection()" title="Clear selection" style="width: 32px; height: 32px; color: var(--primary);">
          <i data-lucide="x" style="width: 18px; height: 18px;"></i>
        </button>
        <span>${selectedItems.length} selected</span>
      </div>
      <div style="display: flex; align-items: center; gap: 0.5rem;">
        <div style="display: flex; align-items: center; gap: 0.25rem;">
          ${selectedItems.length === 1 ? `<button class="btn-icon" onclick="openRenameModal()" title="Rename" style="width: 34px; height: 34px; color: var(--primary);"><i data-lucide="pencil" style="width:16px;height:16px;"></i></button>` : ''}
          <button class="btn-icon" onclick="downloadSelected()" title="Download selected" style="width: 34px; height: 34px; color: var(--primary);"><i data-lucide="download" style="width:16px;height:16px;"></i></button>
          <button class="btn-icon" onclick="openMoveModal()" title="Move selected" style="width: 34px; height: 34px; color: var(--primary);"><i data-lucide="folder-input" style="width:16px;height:16px;"></i></button>
          <button class="btn-icon" onclick="deleteSelected()" title="Delete selected" style="width: 34px; height: 34px; color: var(--danger);"><i data-lucide="trash-2" style="width:16px;height:16px;"></i></button>
        </div>
        <div class="view-switcher-pill">
          <button id="listViewBtnSel" class="view-switcher-btn ${viewMode === 'list' ? 'active' : ''}" onclick="setViewMode('list')" title="List View">
            <i data-lucide="menu" style="width:16px;height:16px;"></i>
          </button>
          <button id="gridViewBtnSel" class="view-switcher-btn ${viewMode === 'grid' ? 'active' : ''}" onclick="setViewMode('grid')" title="Grid View">
            <i data-lucide="layout-grid" style="width:16px;height:16px;"></i>
          </button>
        </div>
      </div>
    `;
  } else {
    defaultContent.style.display = "flex";
    selectionContent.style.display = "none";
    selectionContent.innerHTML = "";
  }
  lucide.createIcons();
}

function toggleStar(name, parentPath) {
  const items = db[parentPath];
  if (!items) return;
  const item = items.find(entry => entry.name === name);
  if (!item) return;
  item.starred = !item.starred;
  renderDirectory();
}

function triggerFileInput(type) {
  closeContextMenu();
  if (type === 'file') {
    document.getElementById("hiddenFileInput").click();
  } else {
    document.getElementById("hiddenFolderInput").click();
  }
}

function handleMockUpload(event) {
  const files = event.target.files;
  if (files.length === 0) return;

  activeTab = "file";
  const pathStr = currentPath.join("/");
  if (!db[pathStr]) db[pathStr] = [];

  for (let file of files) {
    let type = "doc";
    if (file.type.startsWith("image/")) type = "image";
    else if (file.type.startsWith("video/")) type = "video";

    db[pathStr].push({
      name: file.name,
      type: type,
      size: (file.size / (1024 * 1024)).toFixed(1) + " MB",
      modified: "Today",
      starred: false
    });
  }

  event.target.value = "";
  renderDirectory();
}

function openNewFolderDialog() {
  closeContextMenu();
  document.getElementById("newFolderDialog").style.display = "flex";
  const input = document.getElementById("newFolderNameInput");
  input.value = "Untitled folder";
  input.focus();
  input.select();
}

function closeNewFolderDialog() {
  document.getElementById("newFolderDialog").style.display = "none";
  isCreatingFolderInMove = false;
}

function submitNewFolder() {
  const name = document.getElementById("newFolderNameInput").value.trim() || "Untitled folder";
  if (isCreatingFolderInMove) {
    const target = moveCurrentPath.join("/");
    console.log(`[FOLDER] Creating new folder '${name}' inside Move target path: '${target}'`);
    if (!db[target]) db[target] = [];
    db[target].push({ name: name, type: "folder", itemsCount: 0, modified: "Today", starred: false });
    db[target + "/" + name] = [];

    closeNewFolderDialog();
    renderMoveFolderContents();
  } else {
    const pathStr = currentPath.join("/");
    console.log(`[FOLDER] Creating new folder '${name}' inside active directory path: '${pathStr}'`);
    if (!db[pathStr]) db[pathStr] = [];
    db[pathStr].push({ name: name, type: "folder", itemsCount: 0, modified: "Today", starred: false });
    db[pathStr + "/" + name] = [];

    closeNewFolderDialog();
    renderDirectory();
  }
}

let selectedClipboardItems = [];

function renderClipboardHistory() {
  const container = document.getElementById("clipboardHistory");
  if (!container) return;

  container.innerHTML = "";
  if (clipboardItems.length === 0) {
    container.innerHTML = `
      <div style="text-align:center; padding:2rem; color:var(--text-muted); font-size:0.85rem;">
        No items in clipboard history yet.
      </div>
    `;
    return;
  }

  clipboardItems.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = "m3-list-item";
    row.style.cursor = "pointer";

    if (selectedClipboardItems.includes(index)) {
      row.classList.add("selected");
    }

    row.onclick = (e) => {
      if (e.target.closest("button")) return;
      if (selectedClipboardItems.includes(index)) {
        selectedClipboardItems = selectedClipboardItems.filter(i => i !== index);
      } else {
        selectedClipboardItems.push(index);
      }
      renderClipboardHistory();
    };

    row.innerHTML = `
      <div class="file-name-cell" style="flex:1; min-width:0; margin-right:1rem;">
        <div class="avatar-icon avatar-folder" style="background:#e8def8; color:#1d192b;"><i data-lucide="${item.kind === 'Link' ? 'link' : 'file-text'}"></i></div>
        <div class="item-main" style="flex:1; min-width:0;">
          <div class="item-title" style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${escapeHtml(item.text)}">${escapeHtml(item.text)}</div>
          <div class="item-subtitle">${item.kind} - ${item.created}</div>
        </div>
      </div>
      <div class="row-actions" style="display:flex; align-items:center; gap:0.35rem;">
        <button class="btn-icon" onclick="event.stopPropagation(); copyClipboardItem(${index})" title="Copy to clipboard" style="color:var(--text-muted); width:32px; height:32px;">
          <i data-lucide="copy" style="width:16px;height:16px;"></i>
        </button>
        <button class="btn-icon" onclick="event.stopPropagation(); downloadClipboardItem(${index})" title="Download as text file" style="color:var(--primary); width:32px; height:32px;">
          <i data-lucide="download" style="width:16px;height:16px;"></i>
        </button>
        <button class="btn-icon" onclick="event.stopPropagation(); deleteClipboardItem(${index})" title="Delete item" style="color:var(--danger); width:32px; height:32px;">
          <i data-lucide="trash-2" style="width:16px;height:16px;"></i>
        </button>
      </div>
    `;
    container.appendChild(row);
  });
  lucide.createIcons();
}

function downloadClipboardItem(index) {
  const item = clipboardItems[index];
  if (!item) return;
  const blob = new Blob([item.text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${item.kind.toLowerCase()}_${index + 1}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function deleteClipboardItem(index) {
  clipboardItems.splice(index, 1);
  selectedClipboardItems = selectedClipboardItems.filter(i => i !== index);
  renderClipboardHistory();
}

function handleClipboardMenuDownload() {
  if (selectedClipboardItems.length === 0) return;
  selectedClipboardItems.forEach(idx => {
    downloadClipboardItem(idx);
  });
  selectedClipboardItems = [];
  renderClipboardHistory();
  closeContextMenu();
}

function handleClipboardMenuDelete() {
  if (selectedClipboardItems.length === 0) return;
  const sorted = [...selectedClipboardItems].sort((a, b) => b - a);
  sorted.forEach(idx => {
    clipboardItems.splice(idx, 1);
  });
  selectedClipboardItems = [];
  renderClipboardHistory();
  closeContextMenu();
}

function addClipboardItem() {
  const input = document.getElementById("clipboardInput");
  const text = input.value.trim();
  if (!text) {
    input.focus();
    return;
  }

  clipboardItems.unshift({
    text,
    kind: /^https?:\/\//i.test(text) ? "Link" : "Text",
    created: "Just now"
  });
  input.value = "";
  renderClipboardHistory();
}

function clearClipboardInput() {
  const input = document.getElementById("clipboardInput");
  if (input) {
    input.value = "";
    input.focus();
  }
}

function copyClipboardItem(index) {
  const item = clipboardItems[index];
  if (!item) return;

  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(item.text);
  }
  document.getElementById("clipboardInput").value = item.text;
}

function clearSelection() {
  selectedItems = [];
  lastSelectedIndex = -1;
  renderDirectory();
}

function deleteSelected() {
  if (selectedItems.length === 0) return;
  console.log("[DELETE] Attempting to delete items:", selectedItems);
  if (confirm(`Delete ${selectedItems.length} selected item(s)?`)) {
    selectedItems.forEach(name => {
      for (const [folderPath, itemsList] of Object.entries(db)) {
        if (!Array.isArray(itemsList)) continue;
        const idx = itemsList.findIndex(entry => entry && entry.name === name);
        if (idx !== -1) {
          const [deleted] = itemsList.splice(idx, 1);
          console.log(`[DELETE] Deleted item '${name}' from '${folderPath}'`);
          if (deleted && deleted.type === "folder") {
            const oldFolderPath = folderPath + "/" + name;
            Object.keys(db).forEach(k => {
              if (k === oldFolderPath || k.startsWith(oldFolderPath + "/")) {
                delete db[k];
                console.log(`[DELETE] Cleaned up folder sub-key: '${k}'`);
              }
            });
          }
        }
      }
    });
    clearSelection();
    console.log("[DELETE] Delete operation completed successfully.");
  }
}

function downloadSelected() {
  if (selectedItems.length === 0) return;
  alert(`Simulated Download started for: \n${selectedItems.join("\n")}`);
  clearSelection();
}

let moveCurrentPath = ["Home"];
let moveTargetFolder = "Home";
let itemsToMove = [];

function openMoveModal() {
  const targets = selectedItems.map(s => typeof s === "string" ? s : (s && s.name ? s.name : "")).filter(Boolean);
  if (targets.length === 0) {
    console.warn("[MOVE] Cannot open Move dialog: no items selected");
    return;
  }

  itemsToMove = [...targets];
  console.log("[MOVE] Opening Move dialog for targets:", itemsToMove);
  closeContextMenu();
  const titleNode = document.getElementById("moveDialogTitle");
  if (titleNode) {
    titleNode.textContent = itemsToMove.length === 1
      ? `Move ${itemsToMove[0]}`
      : `Move ${itemsToMove.length} items`;
  }

  moveCurrentPath = [...currentPath];
  moveTargetFolder = moveCurrentPath.join("/");
  renderMoveFolderContents();
  const dialog = document.getElementById("moveFileDialog");
  if (dialog) dialog.style.display = "flex";
}

function closeMoveDialog() {
  console.log("[MOVE] Closing Move dialog");
  itemsToMove = [];
  const dialog = document.getElementById("moveFileDialog");
  if (dialog) dialog.style.display = "none";
}

function closeMoveModal() {
  closeMoveDialog();
}

function renderMoveFolderContents() {
  const optionsList = document.getElementById("moveFolderOptions");
  const prevBtn = document.getElementById("movePrevBtn");
  const breadcrumbs = document.getElementById("moveBreadcrumbs");

  if (!optionsList) return;

  const currentFolderStr = moveCurrentPath.join("/");
  moveTargetFolder = currentFolderStr;
  console.log("[MOVE] Target folder in Move modal:", currentFolderStr);

  if (prevBtn) {
    prevBtn.style.display = moveCurrentPath.length > 1 ? "flex" : "none";
  }

  if (breadcrumbs) {
    breadcrumbs.innerHTML = "";
    moveCurrentPath.forEach((folder, idx) => {
      if (idx > 0) {
        const sep = document.createElement("span");
        sep.className = "breadcrumb-separator";
        sep.innerHTML = '<i data-lucide="chevron-right" style="width:12px;height:12px;"></i>';
        breadcrumbs.appendChild(sep);
      }
      const item = document.createElement("span");
      item.style.cursor = idx < moveCurrentPath.length - 1 ? "pointer" : "default";
      item.style.color = idx < moveCurrentPath.length - 1 ? "var(--primary)" : "var(--text-color)";
      item.textContent = folder;
      if (idx < moveCurrentPath.length - 1) {
        item.onclick = () => {
          moveCurrentPath = moveCurrentPath.slice(0, idx + 1);
          renderMoveFolderContents();
        };
      }
      breadcrumbs.appendChild(item);
    });
  }

  optionsList.innerHTML = "";
  const items = db[currentFolderStr] || [];

  const selectedNames = itemsToMove.length > 0
    ? itemsToMove
    : selectedItems.map(s => typeof s === "string" ? s : (s && s.name ? s.name : ""));
  const visibleItems = items.filter(item => !selectedNames.includes(item.name));

  if (visibleItems.length === 0) {
    optionsList.innerHTML = `
      <div style="padding: 1.5rem; text-align: center; color: var(--text-muted); font-size: 0.8rem;">
        Folder is empty
      </div>
    `;
    lucide.createIcons();
    return;
  }

  visibleItems.forEach(item => {
    const row = document.createElement("div");
    row.style = "display: grid; grid-template-columns: 1fr 100px; align-items: center; padding: 0.55rem 0.6rem; font-size: 0.78rem; border-radius: 6px; cursor: pointer; transition: background-color 0.15s ease;";

    let iconName = item.type === "folder" ? "folder" : "file-text";
    if (item.type === "image") iconName = "image";
    else if (item.type === "video") iconName = "video";

    row.innerHTML = `
      <div style="display: flex; align-items: center; gap: 0.5rem; min-width: 0;">
        <i data-lucide="${iconName}" style="width: 16px; height: 16px; color: ${item.type === 'folder' ? 'var(--primary)' : 'var(--text-muted)'};"></i>
        <span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 600;">${escapeHtml(item.name)}</span>
      </div>
      <span style="color: var(--text-muted); font-size: 0.72rem;">${item.modified || 'Today'}</span>
    `;

    row.onmouseover = () => row.style.backgroundColor = "var(--hover-bg)";
    row.onmouseout = () => row.style.backgroundColor = "transparent";

    if (item.type === "folder") {
      row.onclick = () => {
        moveCurrentPath.push(item.name);
        renderMoveFolderContents();
      };
    }

    optionsList.appendChild(row);
  });

  lucide.createIcons();
}

function navigateMoveUp() {
  if (moveCurrentPath.length > 1) {
    moveCurrentPath.pop();
    renderMoveFolderContents();
  }
}

function handleNewFolderInMove() {
  console.log("[FOLDER] User clicked 'New folder' inside Move modal");
  isCreatingFolderInMove = true;
  document.getElementById("newFolderDialog").style.display = "flex";
  const input = document.getElementById("newFolderNameInput");
  input.value = "Untitled folder";
  input.focus();
  input.select();
}

function submitMove() {
  const targets = itemsToMove.length > 0
    ? [...itemsToMove]
    : selectedItems.map(s => typeof s === "string" ? s : (s && s.name ? s.name : "")).filter(Boolean);

  if (targets.length === 0) {
    console.warn("[MOVE] Move operation aborted: no targets specified");
    closeMoveDialog();
    return;
  }

  const targetPathStr = moveTargetFolder;
  console.log("[MOVE] Executing Move operation. Targets:", targets, "Destination:", targetPathStr);

  targets.forEach(name => {
    if (!name) return;

    let sourcePath = currentPath.join("/");
    let itemIndex = -1;

    if (Array.isArray(db[sourcePath])) {
      itemIndex = db[sourcePath].findIndex(entry => entry && entry.name === name);
    }

    if (itemIndex === -1) {
      for (const [folderPath, itemsList] of Object.entries(db)) {
        if (!Array.isArray(itemsList)) continue;
        const idx = itemsList.findIndex(entry => entry && entry.name === name);
        if (idx !== -1) {
          sourcePath = folderPath;
          itemIndex = idx;
          break;
        }
      }
    }

    if (itemIndex > -1 && sourcePath !== targetPathStr) {
      if (!Array.isArray(db[targetPathStr])) db[targetPathStr] = [];
      const spliced = db[sourcePath].splice(itemIndex, 1);
      if (spliced && spliced.length > 0) {
        const movedItem = spliced[0];
        movedItem.parentPath = targetPathStr;
        db[targetPathStr].push(movedItem);
        console.log(`[MOVE] Moved '${name}' from '${sourcePath}' -> '${targetPathStr}'`);

        if (movedItem.type === "folder") {
          const oldFolderPath = sourcePath + "/" + name;
          const newFolderPath = targetPathStr + "/" + name;

          Object.keys(db).forEach(k => {
            if (k === oldFolderPath || k.startsWith(oldFolderPath + "/")) {
              const suffix = k.substring(oldFolderPath.length);
              db[newFolderPath + suffix] = db[k];
              delete db[k];
              console.log(`[MOVE] Re-keyed nested folder: '${k}' -> '${newFolderPath + suffix}'`);
            }
          });
        }
      }
    } else {
      console.warn(`[MOVE] Skipped item '${name}': source ('${sourcePath}') matches destination ('${targetPathStr}') or item not found.`);
    }
  });

  itemsToMove = [];
  closeMoveDialog();
  clearSelection();
  renderDirectory();
  console.log("[MOVE] Move operation completed successfully.");
}

function openRenameModal() {
  if (selectedItems.length !== 1) return;
  closeContextMenu();
  const currentName = selectedItems[0];
  const input = document.getElementById("renameInput");
  input.value = currentName;
  document.getElementById("renameDialog").style.display = "flex";
  input.focus();
  input.select();
}

function closeRenameDialog() {
  document.getElementById("renameDialog").style.display = "none";
}

function closeRenameModal() {
  closeRenameDialog();
}

function submitRename() {
  if (selectedItems.length !== 1) return;
  const oldName = selectedItems[0];
  const newName = document.getElementById("renameInput").value.trim();
  if (!newName || newName === oldName) {
    console.log("[RENAME] Rename cancelled: new name empty or identical");
    closeRenameDialog();
    return;
  }

  console.log(`[RENAME] Renaming '${oldName}' -> '${newName}'`);
  const pathStr = currentPath.join("/");
  const items = db[pathStr];
  if (items) {
    const item = items.find(entry => entry.name === oldName);
    if (item) {
      item.name = newName;
      if (item.type === "folder") {
        const oldFolderPath = pathStr + "/" + oldName;
        const newFolderPath = pathStr + "/" + newName;
        if (db[oldFolderPath]) {
          db[newFolderPath] = db[oldFolderPath];
          delete db[oldFolderPath];
          console.log(`[RENAME] Re-keyed folder key '${oldFolderPath}' -> '${newFolderPath}'`);
        }
      }
    }
  }

  closeRenameDialog();
  clearSelection();
  renderDirectory();
  console.log("[RENAME] Rename operation completed successfully.");
}

function toggleDarkMode() {
  const currentTheme = document.documentElement.getAttribute("data-theme");
  const nextTheme = currentTheme === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", nextTheme);
}


function setConnectMode(mode) {
  connectMode = mode;
  const address = connectionTargets[mode] || connectionTargets.ip;
  const addressNode = document.getElementById("connectAddress");
  if (addressNode) addressNode.textContent = address;

  const lanTab = document.getElementById("lanIpTab");
  const mdnsTab = document.getElementById("mdnsTab");
  if (lanTab) lanTab.classList.toggle("active", mode === "ip");
  if (mdnsTab) mdnsTab.classList.toggle("active", mode === "mdns");

  renderQrPreview(address);
}

function openSettingsDialog() {
  const dialog = document.getElementById("settingsDialog");
  if (dialog) dialog.style.display = "flex";
  const darkToggle = document.getElementById("darkThemeSettingToggle");
  if (darkToggle) {
    darkToggle.checked = document.documentElement.getAttribute("data-theme") === "dark";
  }
}

function closeSettingsDialog() {
  const dialog = document.getElementById("settingsDialog");
  if (dialog) dialog.style.display = "none";
}


function openPreviewModal(item) {
  closeContextMenu();
  const modal = document.getElementById("previewModal");
  const title = document.getElementById("previewTitle");
  const body = document.getElementById("previewBody");
  if (title && item) title.textContent = item.name;
  if (body && item) {
    body.innerHTML = `<div style="text-align: center; color: var(--text-muted);">
      <i data-lucide="${item.kind === 'Folder' ? 'folder' : 'file-text'}" style="width: 48px; height: 48px; margin-bottom: 0.5rem; color: var(--primary);"></i>
      <p style="margin: 0; font-size: 0.95rem; font-weight: 650; color: var(--text-color);">${item.name}</p>
      <p style="margin: 0.25rem 0 0 0; font-size: 0.8rem;">${item.size || '--'} • ${item.modified || 'Recent'}</p>
    </div>`;
    if (window.lucide) lucide.createIcons();
  }
  if (modal) modal.style.display = "flex";
}

function closePreviewModal() {
  const modal = document.getElementById("previewModal");
  if (modal) modal.style.display = "none";
}

function renderQrPreview(value) {
  const box = document.getElementById("qrBox");
  if (!box) return;

  box.innerHTML = "";
  const chars = String(value);
  for (let i = 0; i < 81; i++) {
    const pixel = document.createElement("span");
    pixel.className = "qr-pixel";
    const row = Math.floor(i / 9);
    const col = i % 9;
    const finder = (row < 3 && col < 3) || (row < 3 && col > 5) || (row > 5 && col < 3);
    const code = chars.charCodeAt(i % chars.length);
    const on = finder || ((code + row * 7 + col * 11 + i) % 4 < 2);
    if (on) pixel.classList.add("on");
    box.appendChild(pixel);
  }
}

function copyConnectAddress() {
  const address = connectionTargets[connectMode] || connectionTargets.ip;
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(address);
  }
  const input = document.getElementById("clipboardInput");
  if (input) input.value = address;
}

function closeContextMenu() {
  const contextMenu = document.getElementById("contextMenu");
  if (contextMenu) contextMenu.style.display = "none";
  const sortMenu = document.getElementById("sortDropdownMenu");
  if (sortMenu) sortMenu.style.display = "none";
  const typeMenu = document.getElementById("typeDropdownMenu");
  if (typeMenu) typeMenu.style.display = "none";
  const clipMenu = document.getElementById("clipboardMenuOptions");
  if (clipMenu) clipMenu.style.display = "none";
}

function isMobileInteraction() {
  const frame = document.getElementById("simFrame");
  return !!(frame && frame.classList.contains("mobile-sim")) || window.innerWidth < 768;
}

function switchView(tab) {
  activeTab = tab;
  selectedItems = [];
  selectedClipboardItems = [];
  closeContextMenu();
  renderSelectionHeader();

  const fileView = document.getElementById("fileView");
  const clipboardView = document.getElementById("clipboardView");

  const sideFile = document.getElementById("sideItemFile");
  const sideClip = document.getElementById("sideItemClipboard");
  const sideRecent = document.getElementById("sideItemRecent");
  const sideStarred = document.getElementById("sideItemStarred");

  const navFile = document.getElementById("navItemFile");
  const navClip = document.getElementById("navItemClipboard");
  const navRecent = document.getElementById("navItemRecent");
  const navStarred = document.getElementById("navItemStarred");

  if (sideFile) sideFile.classList.toggle("active", tab === 'file');
  if (sideClip) sideClip.classList.toggle("active", tab === 'clipboard');
  if (sideRecent) sideRecent.classList.toggle("active", tab === 'recent');
  if (sideStarred) sideStarred.classList.toggle("active", tab === 'starred');

  if (navFile) navFile.classList.toggle("active", tab === 'file');
  if (navClip) navClip.classList.toggle("active", tab === 'clipboard');
  if (navRecent) navRecent.classList.toggle("active", tab === 'recent');
  if (navStarred) navStarred.classList.toggle("active", tab === 'starred');

  if (tab === 'file' || tab === 'recent' || tab === 'starred') {
    if (fileView) fileView.style.display = "flex";
    if (clipboardView) clipboardView.style.display = "none";
    renderDirectory();
  } else if (tab === 'clipboard') {
    if (fileView) fileView.style.display = "none";
    if (clipboardView) clipboardView.style.display = "flex";
    renderClipboardHistory();
  }
}

function showMobileUploadMenu(event) {
  if (event) event.stopPropagation();
  closeContextMenu();

  const sheetOverlay = document.getElementById("mobileAddSheetOverlay");
  if (sheetOverlay) {
    sheetOverlay.classList.add("active");
    lucide.createIcons();
    console.log("[MOBILE] Opened animated mobile upload bottom sheet");
  } else {
    openNewFolderDialog();
  }
}

function closeMobileAddSheet() {
  const sheetOverlay = document.getElementById("mobileAddSheetOverlay");
  if (sheetOverlay) {
    sheetOverlay.classList.remove("active");
    console.log("[MOBILE] Closed mobile upload bottom sheet");
  }
}

function setSim(mode) {
  const frame = document.getElementById("simFrame");
  const deskBtn = document.getElementById("simDesktopBtn");
  const mobBtn = document.getElementById("simMobileBtn");

  if (mode === 'mobile') {
    frame.classList.add("mobile-sim");
    deskBtn.classList.remove("active");
    mobBtn.classList.add("active");
  } else {
    frame.classList.remove("mobile-sim");
    mobBtn.classList.remove("active");
    deskBtn.classList.add("active");
  }

  if (activeTab === "clipboard") {
    renderClipboardHistory();
  } else {
    renderDirectory();
  }
}

// Initial setup on DOM load
document.addEventListener("DOMContentLoaded", () => {
  renderQrPreview(connectionTargets.ip);

  // Context Menu Handling
  const contextMenu = document.getElementById("contextMenu");
  const appContainer = document.querySelector(".android-app");

  if (appContainer) {
    appContainer.addEventListener("contextmenu", (e) => {
      if (isMobileInteraction()) {
        e.preventDefault();
        closeContextMenu();
        return;
      }
      e.preventDefault();
      closeContextMenu();

      const itemRow = e.target.closest(".m3-list-item");
      const quickCard = e.target.closest(".quick-card");
      const targetItem = itemRow || quickCard;

      const genericOptions = document.getElementById("genericMenuOptions");
      const itemOptions = document.getElementById("itemMenuOptions");
      const clipboardOptions = document.getElementById("clipboardMenuOptions");

      if (activeTab === "clipboard") {
        if (genericOptions) genericOptions.style.display = "none";
        if (itemOptions) itemOptions.style.display = "none";
        if (clipboardOptions) clipboardOptions.style.display = "block";
      } else {
        if (clipboardOptions) clipboardOptions.style.display = "none";
        if (targetItem) {
          const itemNameElement = targetItem.querySelector(".item-title, .quick-title");
          if (itemNameElement) {
            const itemName = itemNameElement.textContent.trim();
            if (!selectedItems.includes(itemName)) {
              selectedItems = [itemName];
              renderDirectory();
            }
          }
          if (genericOptions) genericOptions.style.display = "none";
          if (itemOptions) itemOptions.style.display = "block";
        } else {
          if (genericOptions) genericOptions.style.display = "block";
          if (itemOptions) itemOptions.style.display = "none";
        }
      }

      contextMenu.style.display = "block";
      let top = e.clientY;
      let left = e.clientX;
      if (top + 220 > window.innerHeight) top = window.innerHeight - 230;
      if (left + 190 > window.innerWidth) left = window.innerWidth - 200;
      contextMenu.style.left = left + "px";
      contextMenu.style.top = top + "px";
    });

    appContainer.addEventListener("click", (e) => {
      if (!e.target.closest(".m3-list-item") && !e.target.closest(".quick-card") && !e.target.closest("button") && !e.target.closest(".custom-context-menu") && !e.target.closest(".m3-dialog")) {
        clearSelection();
      }
    });
  }

  document.addEventListener("click", () => {
    closeContextMenu();
  });

  window.addEventListener("scroll", () => {
    closeContextMenu();
  }, true);

  // Drag and Drop implementation
  const nasDropzone = document.getElementById("nasDropzone");
  if (nasDropzone) {
    nasDropzone.addEventListener("dragenter", (e) => {
      e.preventDefault();
      nasDropzone.classList.add("drag-over");
    });

    nasDropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
    });

    nasDropzone.addEventListener("dragleave", () => {
      nasDropzone.classList.remove("drag-over");
    });

    nasDropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      nasDropzone.classList.remove("drag-over");

      const files = e.dataTransfer.files;
      if (files.length > 0) {
        handleMockUpload({ target: { files: files, value: "" } });
      }
    });
  }

  renderDirectory();
});
