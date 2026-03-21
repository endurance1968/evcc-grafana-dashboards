import path from "node:path";
import fs from "node:fs";
import { chromium } from "playwright";
import { PNG } from "pngjs";
import {
  loadEnvFile,
  optionalEnv,
  parseArg,
  readJson,
  requireEnv,
} from "./_lib.mjs";

loadEnvFile(parseArg("env", ".env"));

const baseUrl = requireEnv("GRAFANA_URL").replace(/\/$/, "");
const username = requireEnv("GRAFANA_USERNAME");
const password = requireEnv("GRAFANA_PASSWORD");
const manifestPath = parseArg("manifest", "tests/artifacts/import-manifest-set.json");
const outDir = parseArg("out", "tests/artifacts/screenshots");
const waitMs = Number(optionalEnv("GRAFANA_SCREENSHOT_WAIT_MS", "3500"));
const timeFrom = optionalEnv("GRAFANA_TIME_FROM", "").trim();
const timeTo = optionalEnv("GRAFANA_TIME_TO", "").trim();

const viewports = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "mobile", width: 390, height: 844 },
];

function safeName(input) {
  return String(input)
    .normalize("NFKD")
    .replace(/\p{M}+/gu, "")
    .replace(/[^a-zA-Z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase();
}

function screenshotName(dashboard) {
  const titleSlug = safeName(dashboard.title || "");
  const uidSlug = safeName(dashboard.uid || "dashboard");
  if (!titleSlug || titleSlug === "evcc" || titleSlug.endsWith("-evcc")) {
    return uidSlug;
  }
  if (titleSlug.length < 12) {
    return `${titleSlug}-${uidSlug}`;
  }
  return titleSlug;
}

function sourceFileName(dashboard) {
  return String(dashboard.sourceFile || "").replace(/^.*[\\/]/, "");
}
function familyFolderName(manifest) {
  return String(manifest?.family || "").trim();
}

function tagFolderName(manifest) {
  const rawTag = String(manifest?.tag || "set").trim() || "set";
  const family = familyFolderName(manifest);
  const prefix = family === "influx-legacy" ? "influx-" : family === "vm" ? "vm-" : "";
  if (prefix && rawTag.startsWith(prefix)) {
    return rawTag.slice(prefix.length);
  }
  return rawTag;
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

function parseRgbColor(input) {
  const match = /^rgba?\((\d+),\s*(\d+),\s*(\d+)/i.exec(String(input || ""));
  if (!match) {
    return { r: 17, g: 24, b: 39, a: 255 };
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

async function login(page) {
  await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
  await page.fill('input[name="user"]', username);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForLoadState("networkidle");
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

async function captureComposed(page, viewport, target) {
  const layout = await readLayout(page);
  const canvas = new PNG({ width: viewport.width, height: layout.totalHeight });
  fillCanvas(canvas, parseRgbColor(layout.pageColor));

  await setToolbarVisibility(page, true);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(800);

  const topHeight = Math.min(viewport.height, Math.max(0, layout.bodyTop));
  if (topHeight > 0) {
    const topBuffer = await page.screenshot({ clip: { x: 0, y: 0, width: viewport.width, height: topHeight } });
    const topPng = PNG.sync.read(topBuffer);
    PNG.bitblt(topPng, canvas, 0, 0, topPng.width, topPng.height, 0, 0);
  }

  await setToolbarVisibility(page, false);
  await page.waitForTimeout(200);

  for (const panel of layout.panels) {
    const locator = page.locator('.react-grid-item').nth(panel.index);
    await locator.scrollIntoViewIfNeeded();
    await page.waitForTimeout(250);
    await waitForPanelContent(page, locator);
    const buffer = await locator.screenshot();
    const panelPng = PNG.sync.read(buffer);
    PNG.bitblt(panelPng, canvas, 0, 0, panelPng.width, panelPng.height, panel.left, panel.top);
  }

  await setToolbarVisibility(page, true);

  const output = PNG.sync.write(trimTransparentBottom(canvas));
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, output);
}

function shouldCaptureInViewport(dashboard, viewportName) {
  const title = String(dashboard.title || "");
  const uid = safeName(dashboard.uid || "");
  const sourceFile = sourceFileName(dashboard);
  const isMobileVariant =
    /today\s*\(mobile\)/i.test(sourceFile) ||
    /today\s*-\s*mobile/i.test(sourceFile) ||
    /mobile/i.test(title) ||
    /mobile/.test(uid);
  if (viewportName === "desktop") {
    return !isMobileVariant;
  }
  if (viewportName === "mobile") {
    return isMobileVariant;
  }
  return true;
}

function dashboardKind(dashboard) {
  const title = String(dashboard.title || "");
  const uid = safeName(dashboard.uid || "");
  const sourceFile = sourceFileName(dashboard);

  if (/all[-\s]?time/i.test(sourceFile) || /all[-\s]?time/i.test(title) || /all[-_]?time/.test(uid)) {
    return "all-time";
  }
  if (/jahr/i.test(sourceFile) || /\bjahr\b/i.test(title) || /-jahr\b/.test(uid)) {
    return "year";
  }
  if (/monat/i.test(sourceFile) || /\bmonat\b/i.test(title) || /-monat\b/.test(uid)) {
    return "month";
  }
  if (/today\s*-\s*details/i.test(sourceFile) || /today\s*-\s*details/i.test(title) || /today[-_]?details/.test(uid)) {
    return "today-details";
  }

  return "";
}

function resolveTimeRange(dashboard) {
  if (timeFrom && timeTo) {
    return { from: timeFrom, to: timeTo };
  }

  const kind = dashboardKind(dashboard);
  if (kind === "all-time") {
    return { from: "now-1y/y", to: "now" };
  }
  if (kind === "year") {
    return { from: "now-1y/y", to: "now/y" };
  }
  if (kind === "month") {
    return { from: "now-1M/M", to: "now/M" };
  }
  if (kind === "today-details") {
    return { from: "now-1d/d", to: "now/d" };
  }
  return { from: timeFrom, to: timeTo };
}

async function captureDashboard(page, dashboard, manifest) {
  const dashboardPath = dashboard.url || `/d/${encodeURIComponent(dashboard.uid)}`;
  const range = resolveTimeRange(dashboard);
  const rangeQuery = range.from && range.to
    ? `&from=${encodeURIComponent(range.from)}&to=${encodeURIComponent(range.to)}`
    : "";
  const url = `${baseUrl}${dashboardPath}?kiosk${rangeQuery}`;

  for (const vp of viewports) {
    if (!shouldCaptureInViewport(dashboard, vp.name)) {
      continue;
    }

    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto(url, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(waitMs);

    const hasPluginError = await page.locator('text=Panel plugin not found').count();
    const hasTemplatingError = await page.locator('text=Templating').count();
    if (hasPluginError || hasTemplatingError) {
      console.warn(`WARN ${dashboard.uid}: visible error hint in ${vp.name}`);
    }

    const familyDir = familyFolderName(manifest);
    const tagDir = tagFolderName(manifest);
    const target = familyDir
      ? path.join(outDir, familyDir, tagDir, vp.name, `${screenshotName(dashboard)}.png`)
      : path.join(outDir, tagDir, vp.name, `${screenshotName(dashboard)}.png`);
    await captureComposed(page, vp, target);
    console.log(`Screenshot: ${target}`);
  }
}

async function main() {
  const manifest = readJson(manifestPath);
  const tag = manifest.tag || "set";

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  await login(page);

  for (const dashboard of manifest.dashboards || []) {
    await captureDashboard(page, dashboard, manifest);
  }

  await browser.close();
  console.log("Screenshot capture finished.");
}

main().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});

