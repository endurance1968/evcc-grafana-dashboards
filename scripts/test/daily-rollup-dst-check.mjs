#!/usr/bin/env node
/**
 * Script: daily-rollup-dst-check.mjs
 * Purpose: Verify calendar-day rollup timestamps and MetricsQL aggregation across DST and calendar boundaries.
 * Version: 2026.07.26.1
 * Last modified: 2026-07-26
 */
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

const timeZone = "Europe/Berlin";
const image = process.env.DST_CHECK_VM_IMAGE || "victoriametrics/victoria-metrics:v1.126.0";
const port = process.env.DST_CHECK_VM_PORT || "18432";
const containerName = `evcc-dst-check-${process.pid}`;
const baseUrl = `http://127.0.0.1:${port}`;
const dashboardFiles = ["VM_EVCC_Month.json", "VM_EVCC_Year.json", "VM_EVCC_All-time.json"];

function run(command, args) {
  const result = spawnSync(command, args, { encoding: "utf8" });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${command} ${args.join(" ")} failed: ${result.stderr || result.stdout}`);
  return result.stdout.trim();
}

function zonedParts(date) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const value = (type) => Number(parts.find((part) => part.type === type)?.value || 0);
  return { year: value("year"), month: value("month"), day: value("day"), hour: value("hour"), minute: value("minute"), second: value("second") };
}

function zonedTimestamp(parts) {
  const wanted = Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour || 0, parts.minute || 0, parts.second || 0);
  let candidate = new Date(wanted);
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const actual = zonedParts(candidate);
    const actualWallTime = Date.UTC(actual.year, actual.month - 1, actual.day, actual.hour, actual.minute, actual.second);
    const correction = wanted - actualWallTime;
    if (correction === 0) return candidate;
    candidate = new Date(candidate.getTime() + correction);
  }
  return candidate;
}

function dayParts(day, hour = 0) {
  const [year, month, date] = day.split("-").map(Number);
  return { year, month, day: date, hour, minute: 0, second: 0 };
}

function localNoonMs(day) {
  return zonedTimestamp(dayParts(day, 12)).getTime();
}

function localMidnightMs(day) {
  return zonedTimestamp(dayParts(day)).getTime();
}

function rangeSeconds(startDay, endDay) {
  return Math.round((localMidnightMs(endDay) - localMidnightMs(startDay)) / 1000);
}

async function waitForVm() {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const response = await fetch(`${baseUrl}/health`);
      if (response.ok) return;
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error("VictoriaMetrics did not become ready.");
}

async function importSeries(series) {
  const response = await fetch(`${baseUrl}/api/v1/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: series.map((item) => JSON.stringify(item)).join("\n"),
  });
  if (!response.ok) throw new Error(`VictoriaMetrics import failed: ${response.status} ${await response.text()}`);
}

async function instantValue(query, time) {
  const body = new URLSearchParams({ query, time: time.toISOString().replace(".000Z", "Z"), nocache: "1" });
  const response = await fetch(`${baseUrl}/api/v1/query`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  const payload = await response.json();
  if (!response.ok || payload.status !== "success") throw new Error(`Query failed: ${query}: ${JSON.stringify(payload)}`);
  return payload.data.result.map((item) => Number(item.value[1]));
}

async function rangeValues(query, startDay, endDay) {
  const params = new URLSearchParams({
    query,
    start: String(localMidnightMs(startDay) / 1000),
    end: String(localMidnightMs(endDay) / 1000),
    step: "86400",
    nocache: "1",
  });
  const response = await fetch(`${baseUrl}/api/v1/query_range?${params}`);
  const payload = await response.json();
  if (!response.ok || payload.status !== "success") throw new Error(`Range query failed: ${query}: ${JSON.stringify(payload)}`);
  return payload.data.result.flatMap((item) => item.values.map((sample) => Number(sample[1])));
}

function assertEqual(actual, expected, label) {
  if (actual !== expected) throw new Error(`${label}: expected ${expected}, got ${actual}`);
}

function collectExpressions(value, out = []) {
  if (Array.isArray(value)) value.forEach((item) => collectExpressions(item, out));
  else if (value && typeof value === "object") {
    for (const [key, item] of Object.entries(value)) {
      if (key === "expr" && typeof item === "string") out.push(item);
      else collectExpressions(item, out);
    }
  }
  return out;
}

function checkDashboardQueries() {
  for (const name of dashboardFiles) {
    const file = path.join(process.cwd(), "dashboards", "original", "en", name);
    const expressions = collectExpressions(JSON.parse(fs.readFileSync(file, "utf8")));
    for (const expression of expressions) {
      if (/\[1d\]|:\s*1d\]/.test(expression)) throw new Error(`${name} still contains a fixed one-day rollup query: ${expression}`);
      const unbuffered = expression.match(/evcc_[A-Za-z0-9_]*daily[A-Za-z0-9_]*(?:\{.*?\})?\[\$__range\](?!\s+offset 3h)/);
      if (unbuffered) throw new Error(`${name} contains an unbuffered calendar range selector: ${unbuffered[0]}`);
    }
  }
}

function makeSeries() {
  const periods = [
    ["spring", ["2026-03-27", "2026-03-28", "2026-03-29", "2026-03-30", "2026-03-31"]],
    ["autumn", ["2025-10-23", "2025-10-24", "2025-10-25", "2025-10-26", "2025-10-27"]],
    ["leap", ["2024-02-28", "2024-02-29"]],
    ["year_end", ["2025-12-31", "2026-01-01"]],
  ];
  const sources = ["evcc", "sma", "vrm"];
  const series = [];
  for (const [period, days] of periods) {
    for (const source of sources) {
      series.push({
        metric: { __name__: "issue32_daily_wh", period, source },
        values: days.map(() => 1),
        timestamps: days.map(localNoonMs),
      });
    }
  }
  series.push({
    metric: { __name__: "issue32_compat_daily_wh", source: "evcc" },
    values: [1, 2, 3, 4, 5],
    timestamps: ["2025-10-23", "2025-10-24", "2025-10-25"].map(localMidnightMs).concat(["2025-10-26", "2025-10-27"].map(localNoonMs)),
  });
  return series;
}

async function verifyPeriod(period, startDay, endDay, expectedDays) {
  const seconds = rangeSeconds(startDay, endDay);
  const selector = `issue32_daily_wh{period="${period}"}[${seconds}s] offset 3h`;
  const time = new Date(localMidnightMs(endDay));
  const sums = await instantValue(`sum(sum_over_time(${selector}))`, time);
  const counts = await instantValue(`sum(count_over_time(${selector}))`, time);
  if (sums.length !== 1 || counts.length !== 1) {
    throw new Error(`${period} query returned no scalar result: selector=${selector} time=${time.toISOString()} sums=${JSON.stringify(sums)} counts=${JSON.stringify(counts)}`);
  }
  assertEqual(sums[0], expectedDays * 3, `${period} mixed-source sum`);
  assertEqual(counts[0], expectedDays * 3, `${period} mixed-source count`);
}

async function main() {
  checkDashboardQueries();
  assertEqual(rangeSeconds("2026-03-29", "2026-03-30"), 82800, "spring DST day");
  assertEqual(rangeSeconds("2025-10-26", "2025-10-27"), 90000, "autumn DST day");
  assertEqual(new Date(localNoonMs("2024-02-29")).toISOString(), "2024-02-29T11:00:00.000Z", "leap-day noon");

  run("docker", ["run", "-d", "--name", containerName, "-p", `127.0.0.1:${port}:8428`, image, "-retentionPeriod=100y"]);
  try {
    await waitForVm();
    await importSeries(makeSeries());
    await new Promise((resolve) => setTimeout(resolve, 5000));
    await verifyPeriod("spring", "2026-03-27", "2026-04-01", 5);
    await verifyPeriod("autumn", "2025-10-23", "2025-10-28", 5);
    await verifyPeriod("leap", "2024-02-28", "2024-03-01", 2);
    await verifyPeriod("year_end", "2025-12-31", "2026-01-02", 2);

    const compatibilityQuery = "(last_over_time(issue32_compat_daily_wh[3h] offset -13h) or last_over_time(issue32_compat_daily_wh[3h] offset -1h))";
    const values = await rangeValues(compatibilityQuery, "2025-10-23", "2025-10-28");
    assertEqual(JSON.stringify(values), JSON.stringify([1, 2, 3, 4, 5]), "legacy-midnight compatibility curve");

    console.log("Daily rollup DST check");
    console.log("======================");
    console.log("Version:       2026.07.26.1");
    console.log("Last modified: 2026-07-26");
    console.log("Result:        OK");
    console.log("Covered:       Europe/Berlin 23h/25h days, leap day, month/year boundaries, EVCC/SMA/VRM mixing");
  } finally {
    if (process.env.DST_CHECK_KEEP_CONTAINER !== "1") {
      spawnSync("docker", ["rm", "-f", containerName], { encoding: "utf8" });
    } else {
      console.error(`Keeping debug container ${containerName}.`);
    }
  }
}

main().catch((error) => {
  console.error(error.message || error);
  process.exit(1);
});
