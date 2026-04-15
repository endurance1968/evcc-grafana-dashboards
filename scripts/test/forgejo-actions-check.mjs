#!/usr/bin/env node
/*
 * Purpose: Verify that the Forgejo repository has Actions enabled and that the latest workflow run is picked up by a runner.
 * Version: 2026.04.15.3
 * Last modified: 2026-04-15
 */

const scriptName = "forgejo-actions-check.mjs";
const scriptVersion = "2026.04.15.3";
const scriptLastModified = "2026-04-15";

const args = process.argv.slice(2);

function readArg(name, fallback = "") {
  const prefix = `--${name}=`;
  const inline = args.find((arg) => arg.startsWith(prefix));
  if (inline) {
    return inline.slice(prefix.length);
  }
  const index = args.indexOf(`--${name}`);
  if (index >= 0 && index + 1 < args.length) {
    return args[index + 1];
  }
  return fallback;
}

function hasFlag(name) {
  return args.includes(`--${name}`);
}

class CliError extends Error {
  constructor(message, code = 1) {
    super(message);
    this.code = code;
  }
}

function fail(message, code = 1) {
  throw new CliError(message, code);
}

async function forgejoGetJson(baseUrl, path, token) {
  const headers = { Accept: "application/json" };
  if (token) {
    headers.Authorization = `token ${token}`;
  }
  const response = await fetch(`${baseUrl.replace(/\/+$/, "")}${path}`, { headers });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`GET ${path} failed with HTTP ${response.status}: ${text.trim()}`);
  }
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new Error(`GET ${path} did not return JSON: ${error.message}`);
  }
}

function latestRun(runs) {
  return [...runs].sort((left, right) => Number(right.id || 0) - Number(left.id || 0))[0] || null;
}

function statusIsTerminal(status) {
  return ["success", "failure", "cancelled", "skipped"].includes(String(status || "").toLowerCase());
}

function statusIsRunning(status) {
  return ["running", "success", "failure", "cancelled", "skipped"].includes(String(status || "").toLowerCase());
}

async function main() {
  const baseUrl = readArg("base-url", process.env.FORGEJO_BASE_URL || "http://192.168.0.127:3000");
  const repo = readArg("repo", process.env.FORGEJO_REPO || "olaf-krause/evcc-grafana-dashboards");
  const token = readArg("token", process.env.FORGEJO_TOKEN || "");
  const allowWaiting = hasFlag("allow-waiting");

  const [owner, name] = repo.split("/", 2);
  if (!owner || !name) {
    fail(`Invalid --repo '${repo}'. Expected owner/name.`);
  }

  console.log("Forgejo Actions check");
  console.log("=====================");
  console.log(`Script:        ${scriptName}`);
  console.log(`Version:       ${scriptVersion}`);
  console.log(`Last modified: ${scriptLastModified}`);
  console.log(`Base URL:      ${baseUrl}`);
  console.log(`Repository:    ${repo}`);
  console.log(`Allow waiting: ${allowWaiting ? "yes" : "no"}`);
  console.log("");

  const repoInfo = await forgejoGetJson(baseUrl, `/api/v1/repos/${encodeURIComponent(owner)}/${encodeURIComponent(name)}`, token);
  const runsInfo = await forgejoGetJson(
    baseUrl,
    `/api/v1/repos/${encodeURIComponent(owner)}/${encodeURIComponent(name)}/actions/runs`,
    token,
  );
  const runs = Array.isArray(runsInfo.workflow_runs) ? runsInfo.workflow_runs : [];
  const run = latestRun(runs);

  console.log("Checks");
  console.log("------");
  console.log(`${repoInfo.has_actions ? "OK" : "CRITICAL"}    Actions enabled: ${repoInfo.has_actions ? "yes" : "no"}`);
  console.log(`${runs.length > 0 ? "OK" : "CRITICAL"}    Workflow runs visible: ${runs.length}`);
  if (run) {
    console.log(`INFO  Latest run: #${run.id} status=${run.status} event=${run.event} commit=${run.commit_sha || "-"}`);
    console.log(`INFO  Latest run URL: ${run.html_url || "-"}`);
  }
  console.log("");

  if (!repoInfo.has_actions) {
    fail("Result: CRITICAL - Forgejo Actions are not enabled for this repository.", 2);
  }
  if (!run) {
    fail("Result: CRITICAL - no workflow run exists; push a commit or trigger workflow_dispatch first.", 2);
  }
  if (!allowWaiting && String(run.status || "").toLowerCase() === "waiting") {
    fail(
      "Result: CRITICAL - latest workflow is waiting. A matching Forgejo runner is missing, offline, busy, or cannot accept this job.",
      2,
    );
  }
  if (allowWaiting && String(run.status || "").toLowerCase() === "waiting") {
    console.log("Result");
    console.log("------");
    console.log("WARNING: Forgejo Actions are enabled, but the latest workflow is waiting for a runner.");
    return;
  }
  if (!statusIsRunning(run.status) && !statusIsTerminal(run.status)) {
    fail(`Result: WARNING - latest workflow has unexpected status '${run.status}'.`, 1);
  }

  console.log("Result");
  console.log("------");
  console.log("OK: Forgejo Actions are enabled and the latest workflow is not stuck waiting.");
}

main().catch((error) => {
  console.error(error.message.startsWith("Result:") ? error.message : `Result: CRITICAL - ${error.message}`);
  process.exitCode = Number.isInteger(error.code) ? error.code : 2;
});
