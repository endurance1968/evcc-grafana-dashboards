/**
 * Script: capture-docs-screenshots.mjs
 * Purpose: Capture curated German dashboard screenshots for docs/screenshots.
 * Version: 2026.06.30.2
 * Last modified: 2026-06-30
 */
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";
import { PNG } from "pngjs";
import {
  loadEnvFile,
  optionalEnv,
  parseArg,
  readJson,
  requireEnv,
} from "./_lib.mjs";

const SCRIPT_VERSION = "2026.06.30.2";
const SCRIPT_LAST_MODIFIED = "2026-06-30";

loadEnvFile(parseArg("env", ".env.local"));

const baseUrl = requireEnv("GRAFANA_URL").replace(/\/$/, "");
const username = requireEnv("GRAFANA_USERNAME");
const password = requireEnv("GRAFANA_PASSWORD");
const manifestPath = parseArg("manifest", "tests/artifacts/import-manifest-vm-docs-de.json");
const outDir = parseArg("out", "docs/screenshots");
const waitMs = Number(parseArg("wait-ms", optionalEnv("GRAFANA_SCREENSHOT_WAIT_MS", "3500")));
const navigationTimeoutMs = Number(parseArg("navigation-timeout-ms", optionalEnv("GRAFANA_SCREENSHOT_NAVIGATION_TIMEOUT_MS", "90000")));
const theme = parseArg("theme", "light").trim();
const deleteExisting = parseArg("delete-existing", "false") === "true";
const dryRun = parseArg("dry-run", "false") === "true";
const timeFrom = optionalEnv("GRAFANA_TIME_FROM", "").trim();
const timeTo = optionalEnv("GRAFANA_TIME_TO", "").trim();

const desktop = { name: "desktop", width: 2240, height: 1300 };
const desktopTall = { name: "desktop-tall", width: 2240, height: 1700 };
const mobile = { name: "mobile", width: 586, height: 1108 };

const capturePlan = [
  {
    match: "VM_EVCC_All-time.json",
    captures: [
      { file: "alltime-energy.png", tab: "Energie", viewport: desktop },
      { file: "alltime-finances.png", tab: "Finanzen", viewport: desktopTall },
      { file: "alltime-planthealth.png", tab: "Anlagengesundheit", viewport: desktop },
    ],
  },
  {
    match: "VM_EVCC_Year.json",
    captures: [
      { file: "year-pv.png", tab: "PV", viewport: desktopTall },
      { file: "year-home.png", tab: "Haus", viewport: desktop },
      { file: "year-battery.png", tab: "Speicher", viewport: desktop },
      { file: "year-finances.png", tab: "Finanzen", viewport: desktop },
      { file: "year-vehicles.png", tab: "Fahrzeuge", viewport: desktop },
    ],
  },
  {
    match: "VM_EVCC_Month.json",
    captures: [
      { file: "month-pv.png", tab: "PV", viewport: desktop },
      { file: "month-home.png", tab: "Haus", viewport: desktop },
      { file: "month-battery.png", tab: "Speicher", viewport: desktop },
      { file: "month-finances.png", tab: "Finanzen", viewport: desktop },
    ],
  },
  {
    match: "VM_EVCC_Today-Details.json",
    captures: [
      { file: "today-pv.png", tab: "PV", viewport: desktop },
      { file: "today-grid.png", tab: "Netz", viewport: desktop },
      { file: "today-consumption.png", tab: "Haus", viewport: desktop },
      { file: "today-tariffs.png", tab: "Tarife", viewport: desktop },
      { file: "today-loadpoints.png", tab: "Ladepunkte", viewport: desktop },
    ],
  },
  {
    match: "VM_EVCC_Today.json",
    captures: [{ file: "today.png", viewport: desktop }],
  },
  {
    match: "VM_EVCC_Today-Mobile.json",
    captures: [{ file: "today-mobile.png", viewport: mobile }],
  },
];

function sourceFileName(dashboard) {
  return String(dashboard.sourceFile || "").replace(/^.*[\\/]/, "");
}

function dashboardPath(dashboard) {
  const url = String(dashboard.url || "").trim();
  if (url.startsWith("/")) {
    return url;
  }
  return `/d/${encodeURIComponent(dashboard.uid)}`;
}

function dashboardUrl(dashboard) {
  const params = new URLSearchParams();
  if (theme) {
    params.set("theme", theme);
  }
  if (timeFrom && timeTo) {
    params.set("from", timeFrom);
    params.set("to", timeTo);
  }
  const query = params.toString();
  return `${baseUrl}${dashboardPath(dashboard)}${query ? `?${query}` : ""}`;
}

function escapeRegex(input) {
  return String(input).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function parseRgbColor(input) {
  const match = /^rgba?\((\d+),\s*(\d+),\s*(\d+)/i.exec(String(input || ""));
  if (!match) {
    return { r: 255, g: 255, b: 255, a: 255 };
  }
  return {
    r: Number.parseInt(match[1], 10),
    g: Number.parseInt(match[2], 10),
    b: Number.parseInt(match[3], 10),
    a: 255,
  };
}

function fillCanvas(png, color) {
  for (let y = 0; y < png.height; y += 1) {
    for (let x = 0; x < png.width; x += 1) {
      const index = (png.width * y + x) * 4;
      png.data[index] = color.r;
      png.data[index + 1] = color.g;
      png.data[index + 2] = color.b;
      png.data[index + 3] = color.a;
    }
  }
}

function trimTransparentBottom(png) {
  let lastVisibleRow = png.height - 1;
  rowSearch: for (; lastVisibleRow >= 0; lastVisibleRow -= 1) {
    for (let x = 0; x < png.width; x += 1) {
      const alpha = png.data[(png.width * lastVisibleRow + x) * 4 + 3];
      if (alpha > 0) {
        break rowSearch;
      }
    }
  }
  const trimmedHeight = Math.max(1, lastVisibleRow + 1);
  if (trimmedHeight === png.height) {
    return png;
  }
  const trimmed = new PNG({ width: png.width, height: trimmedHeight });
  PNG.bitblt(png, trimmed, 0, 0, png.width, trimmedHeight, 0, 0);
  return trimmed;
}

function pixelDistance(png, x, y, color) {
  const index = (png.width * y + x) * 4;
  return Math.max(
    Math.abs(png.data[index] - color.r),
    Math.abs(png.data[index + 1] - color.g),
    Math.abs(png.data[index + 2] - color.b),
  );
}

function trimBackgroundBottom(png, backgroundColor, options = {}) {
  const bottomPadding = options.bottomPadding ?? 24;
  const ignoredRightPx = options.ignoredRightPx ?? 96;
  const maxX = Math.max(1, png.width - ignoredRightPx);
  let lastContentRow = png.height - 1;
  rowSearch: for (; lastContentRow >= 0; lastContentRow -= 1) {
    let changedPixels = 0;
    for (let x = 0; x < maxX; x += 1) {
      if (pixelDistance(png, x, lastContentRow, backgroundColor) > 8) {
        changedPixels += 1;
        if (changedPixels >= 24) {
          break rowSearch;
        }
      }
    }
  }

  const trimmedHeight = Math.min(png.height, Math.max(1, lastContentRow + 1 + bottomPadding));
  if (trimmedHeight >= png.height) {
    return png;
  }
  const trimmed = new PNG({ width: png.width, height: trimmedHeight });
  PNG.bitblt(png, trimmed, 0, 0, png.width, trimmedHeight, 0, 0);
  return trimmed;
}

async function login(page) {
  await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
  await page.fill('input[name="user"]', username);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForLoadState("networkidle");
  await dismissTransientOverlays(page);
  const closeMenu = page.getByLabel("Close menu");
  if ((await closeMenu.count()) > 0 && await closeMenu.first().isVisible()) {
    await closeMenu.first().click({ force: true }).catch(async () => {
      await page.keyboard.press("Escape").catch(() => {});
    });
    await page.waitForTimeout(500);
  }
}

async function dismissTransientOverlays(page) {
  for (let i = 0; i < 3; i += 1) {
    await page.keyboard.press("Escape").catch(() => {});
    await page.waitForTimeout(150);
  }
  await page.evaluate(() => {
    const portal = document.querySelector("#grafana-portal-container");
    if (!portal) {
      return;
    }
    for (const el of portal.children) {
      if (el instanceof HTMLElement) {
        el.style.display = "none";
      }
    }
  }).catch(() => {});
}

async function setToolbarVisibility(page, visible) {
  await page.evaluate((isVisible) => {
    const selectors = ['.css-apndj3', '.css-12rf1df'];
    for (const selector of selectors) {
      for (const el of document.querySelectorAll(selector)) {
        if (el instanceof HTMLElement) {
          el.style.display = isVisible ? "" : "none";
        }
      }
    }
  }, visible);
}

async function readLayout(page) {
  return page.evaluate(() => {
    const body = document.querySelector('.css-1wpe07w-body');
    const gridItems = [...document.querySelectorAll('.react-grid-item')]
      .map((el, index) => {
        const rect = el.getBoundingClientRect();
        return {
          index,
          left: Math.max(0, Math.round(rect.left)),
          top: Math.max(0, Math.round(rect.top + window.scrollY)),
          width: Math.round(rect.width),
          height: Math.round(rect.height),
        };
      })
      .filter((item) => item.width > 0 && item.height > 0)
      .sort((a, b) => a.top - b.top || a.left - b.left);

    const totalHeight = Math.max(
      document.body?.scrollHeight ?? 0,
      document.body?.offsetHeight ?? 0,
      document.documentElement?.scrollHeight ?? 0,
      document.documentElement?.offsetHeight ?? 0,
      ...gridItems.map((item) => item.top + item.height),
    );

    return {
      bodyTop: Math.max(0, Math.round(body ? body.getBoundingClientRect().top + window.scrollY : 64)),
      totalHeight,
      pageColor: getComputedStyle(document.body).backgroundColor,
      panels: gridItems,
    };
  });
}

async function measureContentHeight(page) {
  return page.evaluate(() => {
    const bottoms = [
      document.documentElement?.scrollHeight ?? 0,
      document.body?.scrollHeight ?? 0,
      document.scrollingElement?.scrollHeight ?? 0,
    ];

    for (const el of document.querySelectorAll("*")) {
      if (!(el instanceof HTMLElement)) {
        continue;
      }
      const rect = el.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) {
        continue;
      }
      const top = Math.max(0, rect.top + window.scrollY);
      bottoms.push(top + Math.max(rect.height, el.scrollHeight));
    }

    return Math.ceil(Math.max(...bottoms));
  });
}

async function resetAllScrollPositions(page) {
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
    for (const el of document.querySelectorAll("*")) {
      if (el instanceof HTMLElement && el.scrollTop > 0) {
        el.scrollTop = 0;
      }
    }
  });
}
async function waitForPanelContent(page, locator) {
  for (let attempt = 0; attempt < 12; attempt += 1) {
    const state = await locator.evaluate((el) => ({
      canvases: el.querySelectorAll('canvas').length,
      svgs: el.querySelectorAll('svg').length,
      text: (el.textContent || '').replace(/\s+/g, ' ').trim(),
      hasPanelChrome: !!el.querySelector('[data-testid="data-testid Panel header title"]'),
    }));
    if (state.canvases > 0 || state.svgs > 1 || state.text.length > 20 || state.hasPanelChrome) {
      return;
    }
    await page.waitForTimeout(250);
  }
}

async function captureComposed(page, viewport, target) {
  const layout = await readLayout(page);

  await setToolbarVisibility(page, true);
  for (const panel of layout.panels) {
    const locator = page.locator('.react-grid-item').nth(panel.index);
    await locator.scrollIntoViewIfNeeded();
    await page.waitForTimeout(150);
    await waitForPanelContent(page, locator);
  }

  await resetAllScrollPositions(page);
  await page.waitForTimeout(1000);

  let captureHeight = viewport.height;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const contentHeight = await measureContentHeight(page);
    const nextHeight = Math.min(Math.max(contentHeight + 80, viewport.height), 12000);
    if (nextHeight <= captureHeight + 8) {
      captureHeight = nextHeight;
      break;
    }
    captureHeight = nextHeight;
    await page.setViewportSize({ width: viewport.width, height: captureHeight });
    await resetAllScrollPositions(page);
    await page.waitForTimeout(1000);
  }
  await page.setViewportSize({ width: viewport.width, height: captureHeight });
  await resetAllScrollPositions(page);
  await page.waitForTimeout(1000);

  fs.mkdirSync(path.dirname(target), { recursive: true });
  await page.screenshot({ path: target, fullPage: viewport.name !== "mobile" });

  const png = PNG.sync.read(fs.readFileSync(target));
  const trimmed = trimBackgroundBottom(trimTransparentBottom(png), parseRgbColor(layout.pageColor));
  if (trimmed.height !== png.height) {
    fs.writeFileSync(target, PNG.sync.write(trimmed));
  }
}

async function selectTab(page, tabName) {
  if (!tabName) {
    return;
  }
  await dismissTransientOverlays(page);
  const exact = new RegExp(`^\\s*${escapeRegex(tabName)}\\s*$`);
  const candidates = [
    page.getByRole("tab", { name: exact }),
    page.getByRole("button", { name: exact }),
    page.locator('a,button,[role="tab"]').filter({ hasText: exact }),
  ];
  for (const locator of candidates) {
    const count = await locator.count();
    for (let index = 0; index < count; index += 1) {
      const item = locator.nth(index);
      if (await item.isVisible()) {
        const selected = await item.getAttribute("aria-selected").catch(() => "");
        if (selected === "true") {
          return;
        }
        await item.click({ force: true });
        await page.waitForTimeout(waitMs);
        await dismissTransientOverlays(page);
        return;
      }
    }
  }
  throw new Error(`Could not find visible tab '${tabName}'`);
}

function expectedCaptures(manifest) {
  const bySourceFile = new Map((manifest.dashboards || []).map((dashboard) => [sourceFileName(dashboard), dashboard]));
  const out = [];
  for (const entry of capturePlan) {
    const dashboard = bySourceFile.get(entry.match);
    if (!dashboard) {
      throw new Error(`Manifest does not contain ${entry.match}`);
    }
    for (const capture of entry.captures) {
      out.push({ dashboard, ...capture });
    }
  }
  return out;
}

function deleteExistingPngs() {
  if (!fs.existsSync(outDir)) {
    return;
  }
  for (const entry of fs.readdirSync(outDir, { withFileTypes: true })) {
    if (entry.isFile() && entry.name.toLowerCase().endsWith(".png")) {
      fs.unlinkSync(path.join(outDir, entry.name));
    }
  }
}

async function main() {
  const manifest = readJson(manifestPath);
  const captures = expectedCaptures(manifest);

  console.log(`capture-docs-screenshots.mjs v${SCRIPT_VERSION} (last modified ${SCRIPT_LAST_MODIFIED}, run ${new Date().toISOString()})`);
  console.log(`Manifest: ${manifestPath}`);
  console.log(`Output:   ${outDir}`);
  console.log(`Theme:    ${theme || "Grafana default"}`);
  console.log(`Captures: ${captures.length}`);

  if (dryRun) {
    for (const capture of captures) {
      console.log(`${capture.file}: ${sourceFileName(capture.dashboard)}${capture.tab ? ` / ${capture.tab}` : ""} / ${capture.viewport.name}`);
    }
    return;
  }

  if (deleteExisting) {
    deleteExistingPngs();
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: desktop.width, height: desktop.height } });
  const page = await context.newPage();
  page.setDefaultNavigationTimeout(navigationTimeoutMs);
  page.setDefaultTimeout(navigationTimeoutMs);

  await login(page);

  for (const capture of captures) {
    await page.setViewportSize({ width: capture.viewport.width, height: capture.viewport.height });
    await page.goto(dashboardUrl(capture.dashboard), { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(waitMs);
    await dismissTransientOverlays(page);
    await selectTab(page, capture.tab);
    const target = path.join(outDir, capture.file);
    await captureComposed(page, capture.viewport, target);
    console.log(`Screenshot: ${target}`);
  }

  await browser.close();
  console.log("Docs screenshot capture finished.");
}

main().catch((error) => {
  console.error(error.message || error);
  process.exit(1);
});












