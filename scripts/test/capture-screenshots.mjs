import path from "node:path";
import fs from "node:fs";
import { chromium } from "playwright";
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
  return String(input).replace(/[^a-zA-Z0-9_-]+/g, "-").replace(/^-+|-+$/g, "").toLowerCase();
}

async function login(page) {
  await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
  await page.fill('input[name="user"]', username);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForLoadState("networkidle");
}

async function captureDashboard(page, dashboard, tag) {
  const dashboardPath = dashboard.url || `/d/${encodeURIComponent(dashboard.uid)}`;
  const rangeQuery = timeFrom && timeTo
    ? `&from=${encodeURIComponent(timeFrom)}&to=${encodeURIComponent(timeTo)}`
    : "";
  const url = `${baseUrl}${dashboardPath}?kiosk${rangeQuery}`;
  for (const vp of viewports) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto(url, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(waitMs);

    const hasPluginError = await page.locator('text=Panel plugin not found').count();
    const hasTemplatingError = await page.locator('text=Templating').count();
    if (hasPluginError || hasTemplatingError) {
      console.warn(`WARN ${dashboard.uid}: visible error hint in ${vp.name}`);
    }

    const target = path.join(outDir, tag, vp.name, `${safeName(dashboard.uid)}.png`);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    await page.screenshot({ path: target, fullPage: true });
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
    await captureDashboard(page, dashboard, tag);
  }

  await browser.close();
  console.log("Screenshot capture finished.");
}

main().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});

