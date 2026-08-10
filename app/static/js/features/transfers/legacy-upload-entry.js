/**
 * Lanvan Legacy Upload Entry (legacy-upload-entry.js)
 * Coordinates file and folder picker triggers, mode toggles ('files' vs 'folder'),
 * dropzone click routing, and file input change delegation to UploadEngine.
 */

(function (window) {
    'use strict';

    if (window.LegacyUploadEntry && window.LegacyUploadEntry._initialized) {
        return;
    }

    // Expose currentUploadMode globally so dropzone-manager and app-init share state
    window.currentUploadMode = window.currentUploadMode || 'files';

    /**
     * Legacy button toggle function for single button mode switching
     */
    function toggleUploadMode() {
        var toggleBtn = document.getElementById('uploadModeToggle');
        var dropZoneText = document.getElementById('dropZoneText');

        if (window.currentUploadMode === 'files') {
            window.currentUploadMode = 'folder';
            if (toggleBtn) {
                toggleBtn.innerHTML = ' Folders';
                toggleBtn.title = 'Currently in Folders mode - Click to switch to Files';
            }
            if (dropZoneText) dropZoneText.textContent = ' Drag & Drop folders here or click to select';
        } else {
            window.currentUploadMode = 'files';
            if (toggleBtn) {
                toggleBtn.innerHTML = ' Files';
                toggleBtn.title = 'Currently in Files mode - Click to switch to Folders';
            }
            if (dropZoneText) dropZoneText.textContent = ' Drag & Drop files here or click to select';
        }
    }

    /**
     * Modern sliding toggle function for upload mode switch
     */
    function toggleUploadModeNew() {
        var slider = document.getElementById('uploadModeSlider');
        var filesLabel = document.getElementById('filesLabel');
        var foldersLabel = document.getElementById('foldersLabel');
        var dropZoneText = document.getElementById('dropZoneText');

        if (slider && slider.checked) {
            window.currentUploadMode = 'folder';
            if (filesLabel) filesLabel.classList.remove('active');
            if (foldersLabel) foldersLabel.classList.add('active');
            if (dropZoneText) dropZoneText.textContent = ' Drag & Drop folders here or click to select';
        } else {
            window.currentUploadMode = 'files';
            if (foldersLabel) foldersLabel.classList.remove('active');
            if (filesLabel) filesLabel.classList.add('active');
            if (dropZoneText) dropZoneText.textContent = ' Drag & Drop files here or click to select';
        }
    }

    /**
     * Handle main dropzone click, opening file or folder picker depending on upload mode
     */
    function handleDropZoneClick() {
        var slider = document.getElementById('uploadModeSlider');
        var isFolder = (slider && slider.checked) || window.currentUploadMode === 'folder';

        if (isFolder) {
            var folderInput = document.getElementById('folderInput') || document.getElementById('hiddenFolderInput');
            if (folderInput) {
                folderInput.setAttribute('webkitdirectory', '');
                folderInput.setAttribute('directory', '');
                folderInput.setAttribute('mozdirectory', '');
                folderInput.value = '';
                folderInput.click();
            }
        } else {
            var fileInput = document.getElementById('fileInput');
            if (fileInput) {
                fileInput.value = '';
                fileInput.click();
            }
        }
    }

    /**
     * Programmatically open file or folder picker
     * @param {string} type - 'file' or 'folder'
     */
    function handleFileSelection(type) {
        if (type === 'folder') {
            var folderInput = document.getElementById('folderInput') || document.getElementById('hiddenFolderInput');
            if (folderInput) {
                folderInput.setAttribute('webkitdirectory', '');
                folderInput.setAttribute('directory', '');
                folderInput.setAttribute('mozdirectory', '');
                folderInput.value = '';
                folderInput.click();
            }
        } else {
            var fileInput = document.getElementById('fileInput');
            if (fileInput) {
                fileInput.value = '';
                fileInput.click();
            }
        }
    }

    /**
     * Main file upload handler called on file input change
     * @param {FileList|Array} files - Selected file list
     */
    function handleFiles(files) {
        if (!files || !files.length) return;
        var validFiles = Array.from(files).filter(function (f) {
            return f && typeof f === 'object' && typeof f.name === 'string';
        });
        if (validFiles.length === 0) return;

        console.log(' handleFiles called with:', validFiles.length, 'files');

        if (typeof window.addToUploadQueue === 'function') {
            window.addToUploadQueue(validFiles);
        }
        if (typeof window.showUploadManager === 'function') {
            window.showUploadManager();
        }
        if (typeof window.startNextUpload === 'function') {
            window.startNextUpload();
        }
    }

    // Initialize toggle UI elements on DOM Ready
    document.addEventListener('DOMContentLoaded', function () {
        var oldButton = document.getElementById('uploadModeToggle');
        if (oldButton && oldButton.parentElement) {
            oldButton.parentElement.style.display = 'none';
        }

        var newSliderContainer = document.getElementById('newSliderContainer');
        if (newSliderContainer) {
            newSliderContainer.style.display = 'flex';
        }
    });

    var LegacyUploadEntry = Object.freeze({
        _initialized: true,
        toggleUploadMode: toggleUploadMode,
        toggleUploadModeNew: toggleUploadModeNew,
        handleDropZoneClick: handleDropZoneClick,
        handleFileSelection: handleFileSelection,
        handleFiles: handleFiles
    });

    window.LegacyUploadEntry = LegacyUploadEntry;
    window.toggleUploadMode = toggleUploadMode;
    window.toggleUploadModeNew = toggleUploadModeNew;
    window.handleDropZoneClick = handleDropZoneClick;
    window.handleFileSelection = handleFileSelection;
    window.handleFiles = handleFiles;

})(window);
