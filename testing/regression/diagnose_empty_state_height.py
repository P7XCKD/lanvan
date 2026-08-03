import asyncio
import json
import sys
from playwright.async_api import async_playwright

CONTAINERS = [
    "desktop-panel-header",
    "quickAccessContainer",
    "fileToolbar",
    "nasDropzone",
    "fileTableHead",
    "nasFileList",
    "empty-dropzone-wrapper",
    "empty-dropzone-target"
]

JS_MEASURE = """
() => {
    const ids = [
        "fileView",
        "desktopPanelHeader",
        "quickAccessContainer",
        "fileToolbar",
        "nasDropzone",
        "fileTableHead",
        "nasFileList"
    ];
    
    const results = {};
    
    function measure(el, name) {
        if (!el) {
            results[name] = { mounted: false };
            return;
        }
        const rect = el.getBoundingClientRect();
        const comp = window.getComputedStyle(el);
        results[name] = {
            mounted: true,
            tagName: el.tagName.toLowerCase(),
            classList: Array.from(el.classList),
            childrenCount: el.children.length,
            rect: {
                top: Math.round(rect.top * 10) / 10,
                bottom: Math.round(rect.bottom * 10) / 10,
                left: Math.round(rect.left * 10) / 10,
                right: Math.round(rect.right * 10) / 10,
                width: Math.round(rect.width * 10) / 10,
                height: Math.round(rect.height * 10) / 10
            },
            offsetHeight: el.offsetHeight,
            clientHeight: el.clientHeight,
            scrollHeight: el.scrollHeight,
            display: comp.display,
            position: comp.position,
            flexGrow: comp.flexGrow,
            flexShrink: comp.flexShrink,
            flexBasis: comp.flexBasis,
            minHeight: comp.minHeight,
            maxHeight: comp.maxHeight,
            overflow: comp.overflow,
            padding: `${comp.paddingTop} ${comp.paddingRight} ${comp.paddingBottom} ${comp.paddingLeft}`,
            margin: `${comp.marginTop} ${comp.marginRight} ${comp.marginBottom} ${comp.marginLeft}`
        };
    }
    
    const fileView = document.getElementById("fileView");
    measure(fileView, "#fileView");
    measure(document.querySelector(".desktop-panel-header"), ".desktop-panel-header");
    measure(document.getElementById("quickAccessContainer"), "#quickAccessContainer");
    measure(document.getElementById("fileToolbar"), "#fileToolbar");
    measure(document.getElementById("nasDropzone"), "#nasDropzone");
    measure(document.getElementById("fileTableHead"), "#fileTableHead");
    measure(document.getElementById("nasFileList"), "#nasFileList");
    measure(document.querySelector(".empty-dropzone-wrapper"), ".empty-dropzone-wrapper");
    measure(document.querySelector(".empty-dropzone-target"), ".empty-dropzone-target");
    
    return results;
}
"""

async def run_diagnostics():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        
        report = {}
        
        # State 1: Fresh page load
        await page.goto("http://127.0.0.1:80", wait_until="networkidle")
        await page.wait_for_timeout(1000)
        report["1_fresh_page_load"] = await page.evaluate(JS_MEASURE)
        
        # State 2: Empty List Mode
        await page.evaluate("setViewMode('list')")
        await page.wait_for_timeout(500)
        report["2_empty_list_mode"] = await page.evaluate(JS_MEASURE)
        
        # State 3: Empty Grid Mode
        await page.evaluate("setViewMode('grid')")
        await page.wait_for_timeout(500)
        report["3_empty_grid_mode"] = await page.evaluate(JS_MEASURE)
        
        # State 4: After switching List -> Grid
        await page.evaluate("setViewMode('list')")
        await page.wait_for_timeout(300)
        await page.evaluate("setViewMode('grid')")
        await page.wait_for_timeout(500)
        report["4_switch_list_to_grid"] = await page.evaluate(JS_MEASURE)
        
        # State 5: After switching Grid -> List
        await page.evaluate("setViewMode('list')")
        await page.wait_for_timeout(500)
        report["5_switch_grid_to_list"] = await page.evaluate(JS_MEASURE)
        
        # State 6: Upload then delete all files (simulated via API refresh)
        await page.evaluate("refreshFileListManually && refreshFileListManually()")
        await page.wait_for_timeout(500)
        report["6_upload_delete_simulated"] = await page.evaluate(JS_MEASURE)
        
        # State 7: After refresh
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(1000)
        report["7_after_refresh"] = await page.evaluate(JS_MEASURE)
        
        await browser.close()
        
        print(json.dumps(report, indent=2))

if __name__ == "__main__":
    asyncio.run(run_diagnostics())
