/**
 * Shared helpers for Grafana import, deployment and screenshot test scripts.
 */
import fs from "node:fs";
import path from "node:path";

export function loadEnvFile(filePath = ".env") {
  const resolved = path.resolve(filePath);
  if (!fs.existsSync(resolved)) return;
  const lines = fs.readFileSync(resolved, "utf8").split(/\r?\n/);
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const idx = line.indexOf("=");
    if (idx < 1) continue;
    const key = line.slice(0, idx).trim();
    let value = line.slice(idx + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (!(key in process.env)) process.env[key] = value;
  }
}

export function requireEnv(name) {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required environment variable: ${name}`);
  return value;
}

export function optionalEnv(name, fallback = "") {
  return process.env[name] ?? fallback;
}

export function parseArg(name, fallback = "") {
  const prefix = `--${name}=`;
  const hit = process.argv.find((a) => a.startsWith(prefix));
  if (!hit) return fallback;
  return hit.slice(prefix.length);
}

export function listJsonFiles(inputPath) {
  const abs = path.resolve(inputPath);
  if (!fs.existsSync(abs)) {
    throw new Error(`Path not found: ${inputPath}`);
  }
  const stat = fs.statSync(abs);
  if (stat.isFile()) {
    if (!abs.toLowerCase().endsWith('.json')) return [];
    return [abs];
  }

  const out = [];
  for (const entry of fs.readdirSync(abs, { withFileTypes: true })) {
    const full = path.join(abs, entry.name);
    if (entry.isDirectory()) out.push(...listJsonFiles(full));
    else if (entry.isFile() && entry.name.endsWith('.json')) out.push(full);
  }
  return out.sort((a, b) => a.localeCompare(b));
}

export function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

export function writeJson(filePath, data) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(data, null, 2)}\n`, "utf8");
}

export function sanitizeTag(input) {
  return String(input || "set").toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 24) || "set";
}

export function buildUid(tag, originalUid, fallbackSeed) {
  const base = originalUid || fallbackSeed || "dashboard";
  const safeBase = String(base).toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "");
  return `${sanitizeTag(tag)}-${safeBase}`.slice(0, 40);
}

export function deepReplaceDataSourcePlaceholders(node, map) {
  if (Array.isArray(node)) return node.map((x) => deepReplaceDataSourcePlaceholders(x, map));
  if (!node || typeof node !== "object") return replaceIfPlaceholder(node, map);

  const out = {};
  for (const [k, v] of Object.entries(node)) {
    out[k] = deepReplaceDataSourcePlaceholders(v, map);
  }
  return out;
}

function replaceIfPlaceholder(value, map) {
  if (typeof value !== "string") return value;
  if (!value.startsWith("${") || !value.endsWith("}")) return value;
  const key = value.slice(2, -1);
  return map[key] || value;
}

export async function grafanaApi(pathname, { method = "GET", body, token, baseUrl }) {
  const url = `${baseUrl.replace(/\/$/, "")}${pathname}`;
  const headers = {
    "Accept": "application/json",
    "Authorization": `Bearer ${token}`,
  };
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { raw: text };
  }

  if (!res.ok) {
    throw new Error(`${method} ${pathname} failed (${res.status}): ${JSON.stringify(data)}`);
  }

  return data;
}