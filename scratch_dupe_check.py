import re
from pathlib import Path

JS_DIR = Path('app/static/js')

dupes_of_interest = ['_doInstantUIUpdate', 'connectClipboardWS', 'connectRegularClipboardWS',
    'displayDeviceLogsWithPagination', 'escapeHandler', 'escapeHtml', 'formatFileSize',
    'formatSpeed', 'getBrowserInfo', 'getControlButtons', 'getCurrentDeviceId', 'getDeviceInfo',
    'getStatusDisplay', 'hideSearchAutocomplete', 'populateDeviceLogsModal', 'renderPage',
    'renderPagination', 'renderSearchAutocomplete', 'renderSearchResults', 'saveToDeviceUploadHistory',
    'setupDropzone', 'setupSearch', 'showUploadManager', 'startProgressUpdateSafetyNet',
    'storeFileMetadata', 'toggleDeviceLogs', 'updateAutocompleteHighlight', 'updateNetworkSpeed']

for func in dupes_of_interest:
    files = []
    for f in sorted(JS_DIR.glob('*.js')):
        content = f.read_text(encoding='utf-8', errors='ignore')
        count = len(re.findall(rf'function\s+{func}\s*\(', content))
        if count > 0:
            files.append(f'{f.name}({count})')
    sep = ' | '
    print(f'{func}: {sep.join(files)}')
