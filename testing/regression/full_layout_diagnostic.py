import asyncio
import json
from playwright.async_api import async_playwright

JS_FULL_DIAGNOSTIC = """
() => {
    const elements = [
        { name: "window", el: null },
        { name: "html", el: document.documentElement },
        { name: "body", el: document.body },
        { name: "#fileView", el: document.getElementById("fileView") },
        { name: ".desktop-panel-header", el: document.querySelector(".desktop-panel-header") },
        { name: "#quickAccessContainer", el: document.getElementById("quickAccessContainer") },
        { name: ".file-toolbar", el: document.getElementById("fileToolbar") },
        { name: "#nasDropzone", el: document.getElementById("nasDropzone") },
        { name: "#fileTableHead", el: document.getElementById("fileTableHead") },
        { name: "#nasFileList", el: document.getElementById("nasFileList") },
        { name: ".empty-dropzone-wrapper", el: document.querySelector(".empty-dropzone-wrapper") },
        { name: ".empty-dropzone-target", el: document.querySelector(".empty-dropzone-target") }
    ];

    const windowInnerHeight = window.innerHeight;
    const windowInnerWidth = window.innerWidth;
    const viewportCenterY = windowInnerHeight / 2;

    const data = {
        viewport: {
            innerWidth: windowInnerWidth,
            innerHeight: windowInnerHeight,
            centerY: viewportCenterY
        },
        elements: {}
    };

    elements.forEach(item => {
        if (item.name === "window") return;
        const el = item.el;
        if (!el) {
            data.elements[item.name] = { mounted: false };
            return;
        }

        const rect = el.getBoundingClientRect();
        const comp = window.getComputedStyle(el);
        const centerY = rect.top + (rect.height / 2);

        data.elements[item.name] = {
            mounted: true,
            tagName: el.tagName.toLowerCase(),
            classList: Array.from(el.classList),
            rect: {
                top: Math.round(rect.top * 10) / 10,
                bottom: Math.round(rect.bottom * 10) / 10,
                left: Math.round(rect.left * 10) / 10,
                right: Math.round(rect.right * 10) / 10,
                width: Math.round(rect.width * 10) / 10,
                height: Math.round(rect.height * 10) / 10,
                centerY: Math.round(centerY * 10) / 10
            },
            offsetHeight: el.offsetHeight,
            clientHeight: el.clientHeight,
            scrollHeight: el.scrollHeight,
            display: comp.display,
            position: comp.position,
            flex: comp.flex,
            flexGrow: comp.flexGrow,
            flexShrink: comp.flexShrink,
            flexBasis: comp.flexBasis,
            justifyContent: comp.justifyContent,
            alignItems: comp.alignItems,
            height: comp.height,
            minHeight: comp.minHeight,
            maxHeight: comp.maxHeight,
            overflow: comp.overflow,
            margin: `${comp.marginTop} ${comp.marginRight} ${comp.marginBottom} ${comp.marginLeft}`,
            padding: `${comp.paddingTop} ${comp.paddingRight} ${comp.paddingBottom} ${comp.paddingLeft}`,
            transform: comp.transform
        };
    });

    // Center calculations
    const nasDropzoneRect = data.elements["#nasDropzone"]?.rect;
    const wrapperRect = data.elements[".empty-dropzone-wrapper"]?.rect;
    const targetRect = data.elements[".empty-dropzone-target"]?.rect;

    data.centers = {
        viewportCenterY: viewportCenterY,
        nasDropzoneCenterY: nasDropzoneRect ? nasDropzoneRect.centerY : null,
        wrapperCenterY: wrapperRect ? wrapperRect.centerY : null,
        targetCenterY: targetRect ? targetRect.centerY : null
    };

    if (targetRect && wrapperRect) {
        data.differences = {
            targetVsViewport: Math.round((targetRect.centerY - viewportCenterY) * 10) / 10,
            targetVsDropzone: Math.round((targetRect.centerY - nasDropzoneRect.centerY) * 10) / 10,
            targetVsWrapper: Math.round((targetRect.centerY - wrapperRect.centerY) * 10) / 10
        };
    }

    return data;
}
"""

async def run_diagnostics():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Use 1920x1080 desktop resolution matching browser screenshots
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        
        await page.goto("http://127.0.0.1:80", wait_until="networkidle")
        await page.wait_for_timeout(1000)
        
        result = await page.evaluate(JS_FULL_DIAGNOSTIC)
        print(json.dumps(result, indent=2))
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_diagnostics())
