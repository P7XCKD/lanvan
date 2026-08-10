/**
 * Breadcrumb Navigation & Explorer Navigation Controller
 *
 * Renders the folder path breadcrumb trail, manages folder path normalization,
 * handles current folder navigation, view switching, and layout state toggles.
 */

(function (window) {
    'use strict';

    function cleanFolderPath(path) {
        if (!path) return "";
        var cleaned = String(path).replace(/\\/g, "/").replace(/^Home \(Root\)\/?/, "").replace(/^Home\/?/, "");
        cleaned = cleaned.replace(/^\/+|\/+$/g, "");
        if (cleaned === "Home (Root)" || cleaned === "Home" || cleaned === "Home/") return "";
        return cleaned;
    }

    function tagFilesWithFolder(files, folderPath) {
        var list = Array.isArray(files) ? files : [];
        try {
            Object.defineProperty(list, "__folderPath", {
                value: cleanFolderPath(folderPath),
                enumerable: false,
                configurable: true,
                writable: true
            });
        } catch (e) {
            list.__folderPath = cleanFolderPath(folderPath);
        }
        return list;
    }

    function getTaggedFolderPath(files) {
        return files && files.__folderPath !== undefined ? cleanFolderPath(files.__folderPath) : null;
    }

    function getRelativeItemDir(itemDir, normCurrentDir) {
        var cleanItem = cleanFolderPath(itemDir);
        var cleanCurrent = cleanFolderPath(normCurrentDir);
        if (!cleanCurrent) return cleanItem;
        if (cleanItem === cleanCurrent) return "";
        if (cleanItem.startsWith(cleanCurrent + "/")) {
            return cleanItem.substring(cleanCurrent.length + 1);
        }
        return null;
    }

    function renderBreadcrumbs() {
        var container = document.getElementById("breadcrumbsContainer");
        if (!container) return;
        container.innerHTML = "";

        var activeFolder = typeof window.getCurrentFolderPath === "function" ? window.getCurrentFolderPath() : (window.currentFolderPath || "");
        var currentPath = (activeFolder === "" || activeFolder === "Home" || activeFolder === "Home/") ? "Home" : activeFolder;

        var fullParts = ["Home"];
        if (currentPath && currentPath !== "Home" && currentPath !== "") {
            var subParts = currentPath.split("/");
            fullParts = fullParts.concat(subParts);
        }

        for (var i = 0; i < fullParts.length; i++) {
            if (i > 0) {
                var sep = document.createElement("span");
                sep.className = "breadcrumb-separator";
                sep.innerHTML = '<i data-lucide="chevron-right" style="width:16px;height:16px;"></i>';
                container.appendChild(sep);
            }
            var bItem = document.createElement("span");
            bItem.className = "breadcrumb-item";
            bItem.textContent = fullParts[i];
            if (i < fullParts.length - 1) {
                (function (idx) {
                    bItem.onclick = function () {
                        var targetPath = (idx === 0) ? "" : fullParts.slice(1, idx + 1).join("/");
                        if (typeof window.navigateToFolder === "function") {
                            window.navigateToFolder(targetPath);
                        } else if (window.LanvanStore) {
                            window.LanvanStore.dispatch("SET_CURRENT_FOLDER", { folderPath: targetPath });
                        }
                        if (typeof window.clearSelection === "function") {
                            window.clearSelection();
                        } else {
                            window.selectedItems = [];
                            window.prototypeSelectedItems = window.selectedItems;
                        }
                        if (typeof updateSelectionToolbar === "function") updateSelectionToolbar();
                    };
                })(i);
                bItem.style.cursor = "pointer";
            }
            container.appendChild(bItem);
        }

        if (typeof lucide !== "undefined" && typeof lucide.createIcons === "function") {
            lucide.createIcons();
        }
    }

    var lastFolderNavTime = 0;
    function navigateIntoFolder(folderName) {
        var now = Date.now();
        if (now - lastFolderNavTime < 400) {
            return;
        }
        lastFolderNavTime = now;

        var base = (typeof window.getCurrentFolderPath === "function")
            ? window.getCurrentFolderPath()
            : (window.currentFolderPath || "");
        if (base === "Home") base = "";
        base = cleanFolderPath(base);

        var newPath = base ? (base + "/" + folderName) : folderName;
        if (newPath === cleanFolderPath((typeof window.getCurrentFolderPath === "function") ? window.getCurrentFolderPath() : window.currentFolderPath)) {
            return;
        }

        console.log("%c[LANVAN UI] 📂 Navigating into folder: '%s'", "color:#3b82f6; font-weight:bold;", newPath);

        if (typeof window.clearSelection === "function") {
            window.clearSelection();
        } else {
            window.selectedItems = [];
        }

        if (window.navigateToFolder) {
            window.navigateToFolder(newPath);
        } else if (window.LanvanStore) {
            window.LanvanStore.dispatch("SET_CURRENT_FOLDER", { folderPath: newPath });
        } else {
            window.currentFolderPath = newPath;
        }

        if (window.history && typeof window.history.replaceState === "function") {
            try {
                window.history.replaceState({ folder: newPath }, "", window.location.pathname);
            } catch (e) { }
        }
    }

    function navigateToFolder(folderPath) {
        var cleanFolder = cleanFolderPath(folderPath);
        window._contextMenuFolderPath = "";
        window._contextMenuTarget = "";
        console.log("📂 [LANVAN UI] Navigating to folder: '" + (cleanFolder || "Home") + "'");
        if (window.LanvanStore) {
            window.LanvanStore.dispatch("SET_CURRENT_FOLDER", { folderPath: cleanFolder });
        } else {
            window.currentFolderPath = cleanFolder;
            if (window.FileRepository) {
                window.FileRepository.fetchFolderContents(cleanFolder);
            }
        }
    }

    function navigateToPathAndSelect(targetPath, filename) {
        window.currentFolderPath = targetPath || "";
        if (typeof window.clearSelection === "function") window.clearSelection();
        renderBreadcrumbs();
        if (typeof fetchFilesData === "function") {
            fetchFilesData().then(function (fd) {
                if (typeof renderFileList === "function") renderFileList(fd);
                setTimeout(function () {
                    var allItems = document.querySelectorAll("#nasFileList .m3-list-item");
                    var matchedEl = null;
                    var matchedName = null;

                    for (var i = 0; i < allItems.length; i++) {
                        var curName = allItems[i].getAttribute("data-filename");
                        if (curName === filename) {
                            matchedEl = allItems[i];
                            matchedName = curName;
                            break;
                        }
                    }

                    if (!matchedEl) {
                        for (var j = 0; j < allItems.length; j++) {
                            var fn = allItems[j].getAttribute("data-filename");
                            if (fn && filename && (fn.toLowerCase().indexOf(filename.toLowerCase()) !== -1 || filename.toLowerCase().indexOf(fn.toLowerCase()) !== -1)) {
                                matchedEl = allItems[j];
                                matchedName = fn;
                                break;
                            }
                        }
                    }

                    if (matchedEl && matchedName) {
                        window.selectedItems = [matchedName];
                        matchedEl.classList.add("selected");
                        if (typeof updateSelectionToolbar === "function") updateSelectionToolbar();
                        matchedEl.scrollIntoView({ behavior: "smooth", block: "center" });
                    }
                }, 100);
            });
        }
    }

    function switchView(tab) {
        if (!tab || tab === "recent") tab = "file";
        window.activeTab = tab;
        document.documentElement.setAttribute('data-active-tab', tab);
        try { localStorage.setItem("lanvan_active_tab", tab); } catch (e) {}

        var fileView = document.getElementById("fileView");
        var clipView = document.getElementById("clipboardView");

        var sideFile = document.getElementById("sideItemFile");
        var sideClip = document.getElementById("sideItemClipboard");

        var navFile = document.getElementById("navItemFile");
        var navClip = document.getElementById("navItemClipboard");

        if (typeof window.clearSelection === "function") window.clearSelection();

        var isFile = (tab === "file");
        if (sideFile) {
            sideFile.classList.toggle("active", isFile);
            sideFile.setAttribute("aria-current", isFile ? "page" : "false");
        }
        if (sideClip) {
            sideClip.classList.toggle("active", !isFile);
            sideClip.setAttribute("aria-current", !isFile ? "page" : "false");
        }
        if (navFile) {
            navFile.classList.toggle("active", isFile);
            navFile.setAttribute("aria-current", isFile ? "page" : "false");
        }
        if (navClip) {
            navClip.classList.toggle("active", !isFile);
            navClip.setAttribute("aria-current", !isFile ? "page" : "false");
        }

        if (tab === "clipboard") {
            if (fileView) fileView.style.display = "none";
            if (clipView) clipView.style.display = "flex";
            if (!window._clipboardViewInitialized) {
                window._clipboardViewInitialized = true;
                if (typeof refreshClipboardHistory === "function") refreshClipboardHistory();
            }
        } else {
            if (fileView) fileView.style.display = "flex";
            if (clipView) clipView.style.display = "none";
            if (!window._fileViewInitialized) {
                window._fileViewInitialized = true;
                if (typeof window.refreshFileList === "function") window.refreshFileList();
            } else if (typeof lastRenderedFiles !== "undefined" && lastRenderedFiles) {
                if (typeof renderFileList === "function") renderFileList(lastRenderedFiles, "view_mode_switch");
            }
        }
        if (typeof syncFileTableHeadWidth === "function") syncFileTableHeadWidth();
    }

    function updateExplorerLayoutState(options) {
        var nasDropzone = document.getElementById("nasDropzone");
        var fileList = document.getElementById("nasFileList");
        var fileTableHead = document.getElementById("fileTableHead");
        var quickContainer = document.getElementById("quickAccessContainer");
        var listBtn = document.getElementById("listViewBtn");
        var gridBtn = document.getElementById("gridViewBtn");

        var viewMode = (options && options.viewMode) ||
            document.documentElement.getAttribute("data-view-mode") ||
            (fileList && fileList.classList.contains("grid-mode") ? "grid" : "list");

        var hasFiles = options && typeof options.hasFiles === "boolean"
            ? options.hasFiles
            : (fileList ? !fileList.classList.contains("empty-state") : false);

        var normCurrentDir = typeof window.getCurrentFolderPath === "function" ? window.getCurrentFolderPath() : (window.currentFolderPath || "");
        var isSubfolder = (normCurrentDir && normCurrentDir !== "" && normCurrentDir !== "Home");
        var hasRecents = hasFiles && !isSubfolder;

        if (nasDropzone) {
            nasDropzone.classList.toggle("is-empty", !hasFiles);
            nasDropzone.classList.toggle("is-grid", viewMode === "grid");
            nasDropzone.classList.toggle("is-list", viewMode === "list");
        }

        if (fileList) {
            fileList.classList.toggle("empty-state", !hasFiles);
            fileList.classList.toggle("grid-mode", viewMode === "grid");
        }

        if (fileTableHead) {
            fileTableHead.style.display = (viewMode === "grid" || !hasFiles) ? "none" : "";
        }

        if (quickContainer) {
            quickContainer.style.display = hasRecents ? "" : "none";
        }

        if (listBtn) listBtn.classList.toggle("active", viewMode === "list");
        if (gridBtn) gridBtn.classList.toggle("active", viewMode === "grid");
    }

    window.BreadcrumbNav = {
        renderBreadcrumbs: renderBreadcrumbs,
        cleanFolderPath: cleanFolderPath,
        tagFilesWithFolder: tagFilesWithFolder,
        getTaggedFolderPath: getTaggedFolderPath,
        getRelativeItemDir: getRelativeItemDir,
        navigateIntoFolder: navigateIntoFolder,
        navigateToFolder: navigateToFolder,
        navigateToPathAndSelect: navigateToPathAndSelect,
        switchView: switchView,
        updateExplorerLayoutState: updateExplorerLayoutState
    };

    window.renderBreadcrumbs = renderBreadcrumbs;
    window.cleanFolderPath = cleanFolderPath;
    window.tagFilesWithFolder = tagFilesWithFolder;
    window.getTaggedFolderPath = getTaggedFolderPath;
    window.getRelativeItemDir = getRelativeItemDir;
    window.navigateIntoFolder = navigateIntoFolder;
    window.navigateToFolder = navigateToFolder;
    window.navigateToPathAndSelect = navigateToPathAndSelect;
    window.switchView = switchView;
    window.updateExplorerLayoutState = updateExplorerLayoutState;

})(window);
