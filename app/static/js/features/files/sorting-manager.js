/**
 * @file sorting-manager.js
 * @description File list comparator & sorting manager.
 * @module SortingManager
 */

(function (window) {
    'use strict';

    function parseSizeToBytes(sizeStr, isFolder) {
        if (isFolder) return -1;
        if (sizeStr === null || sizeStr === undefined) return 0;
        if (typeof sizeStr === "number") return sizeStr;
        var str = String(sizeStr).toUpperCase().trim();
        if (!str || str === "--" || str === "-") return 0;

        if (/^\d+(\.\d+)?$/.test(str)) {
            return parseFloat(str);
        }

        var match = str.match(/^([\d.]+)\s*([KMGTP]?B)?$/i);
        if (!match) return 0;
        var val = parseFloat(match[1]);
        var unit = match[2] ? match[2].toUpperCase() : "B";
        if (unit === "KB") return val * 1024;
        if (unit === "MB") return val * 1024 * 1024;
        if (unit === "GB") return val * 1024 * 1024 * 1024;
        if (unit === "TB") return val * 1024 * 1024 * 1024 * 1024;
        return val;
    }

    function parseDateToTimestamp(dateVal) {
        if (!dateVal) return 0;
        if (typeof dateVal === "number") {
            return dateVal < 1e11 ? dateVal * 1000 : dateVal;
        }
        var str = String(dateVal).trim();
        if (!str || str === "--" || str === "-") return 0;

        if (/^\d+(\.\d+)?$/.test(str)) {
            var num = parseFloat(str);
            return num < 1e11 ? num * 1000 : num;
        }

        var lower = str.toLowerCase();
        if (lower === "just now" || lower === "today") {
            return Date.now();
        }
        var minMatch = lower.match(/^(\d+)\s*(min|minute)s?\s*ago$/);
        if (minMatch) {
            return Date.now() - parseInt(minMatch[1], 10) * 60 * 1000;
        }
        var hrMatch = lower.match(/^(\d+)\s*(hour|hr)s?\s*ago$/);
        if (hrMatch) {
            return Date.now() - parseInt(hrMatch[1], 10) * 3600 * 1000;
        }
        var dayMatch = lower.match(/^(\d+)\s*days?\s*ago$/);
        if (dayMatch) {
            return Date.now() - parseInt(dayMatch[1], 10) * 86400 * 1000;
        }

        var parsed = Date.parse(str);
        return isNaN(parsed) ? 0 : parsed;
    }

    function compareFiles(a, b, field, direction) {
        var dir = direction === "desc" ? -1 : 1;
        var isFolderA = !!a.isFolder;
        var isFolderB = !!b.isFolder;

        // Folders always sorted first
        if (isFolderA && !isFolderB) return -1;
        if (!isFolderA && isFolderB) return 1;

        if (field === "size") {
            var sizeA = parseSizeToBytes(a.size || a.fileSize, isFolderA);
            var sizeB = parseSizeToBytes(b.size || b.fileSize, isFolderB);
            return (sizeA - sizeB) * dir;
        } else if (field === "date") {
            var timeA = parseDateToTimestamp(a.mtime || a.date || a.modified);
            var timeB = parseDateToTimestamp(b.mtime || b.date || b.modified);
            return (timeA - timeB) * dir;
        } else if (field === "type") {
            var extA = (a.name || "").split(".").pop().toLowerCase();
            var extB = (b.name || "").split(".").pop().toLowerCase();
            return extA.localeCompare(extB) * dir;
        } else {
            // Default: name
            var nameA = (a.name || "").toLowerCase();
            var nameB = (b.name || "").toLowerCase();
            return nameA.localeCompare(nameB, undefined, { numeric: true, sensitivity: 'base' }) * dir;
        }
    }

    function getFileItemType(fileData) {
        if (fileData.isFolder) return "folder";
        var name = fileData.name || "";
        var ext = name.split(".").pop().toLowerCase();

        var imageExts = ["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "ico"];
        var videoExts = ["mp4", "mov", "avi", "mkv", "webm", "flv", "wmv"];
        var audioExts = ["mp3", "wav", "ogg", "flac", "aac", "m4a"];
        var archiveExts = ["zip", "rar", "7z", "tar", "gz", "bz2"];
        var docExts = ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "md", "csv"];

        if (imageExts.indexOf(ext) !== -1) return "image";
        if (videoExts.indexOf(ext) !== -1) return "video";
        if (audioExts.indexOf(ext) !== -1) return "audio";
        if (archiveExts.indexOf(ext) !== -1) return "archive";
        if (docExts.indexOf(ext) !== -1) return "doc";
        return "doc";
    }

    function updateSortCheckmarks() {
        var byName = document.getElementById("check-by-name");
        var byDate = document.getElementById("check-by-date");
        var bySize = document.getElementById("check-by-size");
        var sb = window.sortBy || "name";
        var sd = window.sortDirection || "asc";
        var sf = window.sortFolders || "top";

        if (byName) byName.style.visibility = sb === "name" ? "visible" : "hidden";
        if (byDate) byDate.style.visibility = sb === "date" ? "visible" : "hidden";
        if (bySize) bySize.style.visibility = sb === "size" ? "visible" : "hidden";

        var dirAsc = document.getElementById("check-dir-asc");
        var dirDesc = document.getElementById("check-dir-desc");
        if (dirAsc) dirAsc.style.visibility = sd === "asc" ? "visible" : "hidden";
        if (dirDesc) dirDesc.style.visibility = sd === "desc" ? "visible" : "hidden";

        var foldTop = document.getElementById("check-folders-top");
        var foldMixed = document.getElementById("check-folders-mixed");
        if (foldTop) foldTop.style.visibility = sf === "top" ? "visible" : "hidden";
        if (foldMixed) foldMixed.style.visibility = sf === "mixed" ? "visible" : "hidden";
    }

    function updateSortHeaderArrows() {
        var arrowName = document.getElementById("sortArrow-name");
        var arrowDate = document.getElementById("sortArrow-date");
        var arrowSize = document.getElementById("sortArrow-size");
        var sb = window.sortBy || "name";
        var sd = window.sortDirection || "asc";

        function getArrowMarkup(col) {
            if (sb === col) {
                return sd === "asc"
                    ? '<i data-lucide="chevron-down" class="sort-header-icon active" title="Ascending" style="width:13px;height:13px;color:var(--primary);vertical-align:middle;margin-left:2px;"></i>'
                    : '<i data-lucide="chevron-up" class="sort-header-icon active" title="Descending" style="width:13px;height:13px;color:var(--primary);vertical-align:middle;margin-left:2px;"></i>';
            }
            return '<i data-lucide="chevron-down" class="sort-header-icon inactive" title="Sort by ' + col + '" style="width:13px;height:13px;color:var(--text-muted);opacity:0.3;vertical-align:middle;margin-left:2px;"></i>';
        }

        if (arrowName) arrowName.innerHTML = getArrowMarkup("name");
        if (arrowDate) arrowDate.innerHTML = getArrowMarkup("date");
        if (arrowSize) arrowSize.innerHTML = getArrowMarkup("size");
        if (window.lucide && typeof window.lucide.createIcons === "function") {
            window.lucide.createIcons();
        }
    }

    function setSortOption(category, value) {
        if (category === "by") window.sortBy = value;
        else if (category === "direction") window.sortDirection = value;
        else if (category === "folders") window.sortFolders = value;

        if (window.LanvanStore && window.LanvanStore.state) {
            window.LanvanStore.state.sortBy = window.sortBy;
            window.LanvanStore.state.sortDirection = window.sortDirection;
            window.LanvanStore.state.sortFolders = window.sortFolders;
        }

        var el = document.getElementById("sortDropdownMenu");
        if (el) el.style.display = "none";

        window._lastRenderSignature = null;
        updateSortCheckmarks();
        updateSortHeaderArrows();

        if (typeof window.refreshFileList === "function") {
            window.refreshFileList('sort_changed');
        }
    }

    function setTypeFilter(type) {
        window.typeFilter = type;
        if (window.LanvanStore && window.LanvanStore.state) {
            window.LanvanStore.state.typeFilter = type;
        }
        var wrapper = document.getElementById("typeBtnWrapper");
        if (wrapper) {
            if (type === "all") {
                wrapper.innerHTML =
                    '<button class="filter-chip" id="typeDropdownBtn" onclick="toggleTypeDropdown(event)" style="display: inline-flex; align-items: center; gap: 0.35rem; font-size: 0.76rem; font-weight: 700; border: 1px solid var(--border-color); background: var(--card-bg); color: var(--text-color); border-radius: 999px; padding: 0 0.8rem; height: 32px; box-sizing: border-box; cursor: pointer;">' +
                    '<span>Type</span>' +
                    '<i data-lucide="chevron-down" style="width: 12px; height: 12px;"></i>' +
                    '</button>';
            } else {
                var labelMap = {
                    folder: "Folder",
                    image: "Photos",
                    video: "Videos",
                    audio: "Audio",
                    doc: "Documents",
                    archive: "Archives"
                };
                var text = labelMap[type] || "Type";
                wrapper.innerHTML =
                    '<div class="filter-chip active" id="typeDropdownBtn" style="display: inline-flex; align-items: center; padding: 0; border: none; background: var(--primary-container); border-radius: 999px; overflow: hidden; height: 32px; box-sizing: border-box;">' +
                    '<button onclick="toggleTypeDropdown(event)" style="display: flex; align-items: center; gap: 0.25rem; font-size: 0.76rem; font-weight: 700; background: transparent; border: none; color: var(--primary); padding: 0 0.55rem 0 0.85rem; cursor: pointer; height: 100%;">' +
                    '<span>Type: ' + text + '</span>' +
                    '<i data-lucide="chevron-down" style="width: 12px; height: 12px;"></i>' +
                    '</button>' +
                    '<span style="width: 1px; height: 14px; background: rgba(11, 87, 208, 0.25); display: inline-block;"></span>' +
                    '<button onclick="clearTypeFilter(event)" style="display: flex; align-items: center; justify-content: center; background: transparent; border: none; color: var(--primary); width: 28px; height: 100%; padding: 0; cursor: pointer;" title="Clear filter">' +
                    '<i data-lucide="x" style="width: 13px; height: 13px;"></i>' +
                    '</button>' +
                    '</div>';
            }
        }

        var menu = document.getElementById("typeDropdownMenu");
        if (menu) {
            menu.style.display = "none";
            var checkmarks = {
                all: "check",
                image: "image",
                video: "video",
                audio: "music",
                doc: "file-text",
                folder: "folder",
                archive: "archive"
            };

            var items = menu.querySelectorAll(".context-item");
            var keys = Object.keys(checkmarks);
            for (var idx = 0; idx < items.length; idx++) {
                var item = items[idx];
                var icon = item.querySelector("i");
                if (icon) {
                    var itemType = keys[idx];
                    if (itemType === type) {
                        icon.setAttribute("data-lucide", "check");
                        icon.style.color = "var(--primary)";
                    } else {
                        icon.setAttribute("data-lucide", checkmarks[itemType]);
                        icon.style.color = "";
                    }
                }
            }
        }

        if (window.lucide) lucide.createIcons();
        if (typeof window.clearSelection === "function") window.clearSelection();

        if (typeof window.refreshFileList === "function") {
            window.refreshFileList('filter_changed');
        }
    }

    function clearTypeFilter(event) {
        if (event) event.stopPropagation();
        setTypeFilter("all");
    }

    function toggleSortMenu(event) {
        if (event) event.stopPropagation();
        var menu = document.getElementById("sortDropdownMenu");
        if (!menu) return;
        var isVisible = menu.style.display === "block";

        var contextMenu = document.getElementById("contextMenu");
        if (contextMenu) contextMenu.style.display = "none";

        if (!isVisible) {
            updateSortCheckmarks();
            var rect = event.currentTarget.getBoundingClientRect();
            menu.style.display = "block";
            var menuHeight = 280;
            var top = rect.bottom + 6;
            if (top + menuHeight > window.innerHeight) {
                top = Math.max(10, rect.top - menuHeight - 4);
            }
            var left = Math.max(10, rect.right - 180);
            menu.style.left = left + "px";
            menu.style.top = top + "px";
        } else {
            menu.style.display = "none";
        }
    }

    function toggleTypeDropdown(event) {
        if (event) event.stopPropagation();
        var menu = document.getElementById("typeDropdownMenu");
        if (!menu) return;
        menu.style.display = menu.style.display === "block" ? "none" : "block";
    }

    function handleHeaderSortClick(column) {
        var sb = window.sortBy || "name";
        var sd = window.sortDirection || "asc";
        if (sb === column) {
            sd = sd === "asc" ? "desc" : "asc";
        } else {
            sb = column;
            sd = "asc";
        }
        window.sortBy = sb;
        window.sortDirection = sd;

        if (window.LanvanStore && window.LanvanStore.state) {
            window.LanvanStore.state.sortBy = sb;
            window.LanvanStore.state.sortDirection = sd;
        }

        window._lastRenderSignature = null;
        updateSortHeaderArrows();
        updateSortCheckmarks();
        if (typeof window.refreshFileList === "function") {
            window.refreshFileList('header_sort_changed');
        }
    }

    window.SortingManager = {
        parseSizeToBytes: parseSizeToBytes,
        parseDateToTimestamp: parseDateToTimestamp,
        compareFiles: compareFiles,
        getFileItemType: getFileItemType,
        updateSortCheckmarks: updateSortCheckmarks,
        updateSortHeaderArrows: updateSortHeaderArrows,
        setSortOption: setSortOption,
        setTypeFilter: setTypeFilter,
        clearTypeFilter: clearTypeFilter,
        toggleSortMenu: toggleSortMenu,
        toggleTypeDropdown: toggleTypeDropdown,
        handleHeaderSortClick: handleHeaderSortClick
    };

    window.parseSizeToBytes = parseSizeToBytes;
    window.parseDateToTimestamp = parseDateToTimestamp;
    window.compareFiles = compareFiles;
    window.getFileItemType = getFileItemType;

    window.setSortOption = setSortOption;
    window.setTypeFilter = setTypeFilter;
    window.clearTypeFilter = clearTypeFilter;
    window.toggleSortMenu = toggleSortMenu;
    window.toggleTypeDropdown = toggleTypeDropdown;
    window.handleHeaderSortClick = handleHeaderSortClick;

})(window);
