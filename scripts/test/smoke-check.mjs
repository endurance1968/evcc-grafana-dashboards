import {
  grafanaApi,
  loadEnvFile,
  parseArg,
  readJson,
  requireEnv,
} from "./_lib.mjs";

loadEnvFile(parseArg("env", ".env"));

const baseUrl = requireEnv("GRAFANA_URL");
const token = requireEnv("GRAFANA_API_TOKEN");
const manifestPath = parseArg("manifest", "tests/artifacts/import-manifest-set.json");

function countPanels(node) {
  if (!node || typeof node !== "object") return 0;
  let count = 0;
  if (Array.isArray(node.panels)) count += node.panels.length;
  if (Array.isArray(node.rows)) {
    for (const row of node.rows) {
      if (Array.isArray(row.panels)) count += row.panels.length;
    }
  }
  return count;
}

function findUnresolvedImportPlaceholders(node, currentPath = "$", hits = []) {
  if (hits.length >= 20) {
    return hits;
  }

  if (typeof node === "string") {
    if (/\$\{(?:VAR|DS)_[A-Z0-9_]+\}/.test(node)) {
      hits.push(`${currentPath} => ${node}`);
    }
    return hits;
  }

  if (Array.isArray(node)) {
    for (let i = 0; i < node.length; i += 1) {
      findUnresolvedImportPlaceholders(node[i], `${currentPath}[${i}]`, hits);
      if (hits.length >= 20) break;
    }
    return hits;
  }

  if (node && typeof node === "object") {
    for (const [key, value] of Object.entries(node)) {
      findUnresolvedImportPlaceholders(value, `${currentPath}.${key}`, hits);
      if (hits.length >= 20) break;
    }
  }

  return hits;
}

async function main() {
  const manifest = readJson(manifestPath);
  let failures = 0;

  for (const item of manifest.dashboards || []) {
    try {
      const data = await grafanaApi(`/api/dashboards/uid/${item.uid}`, { token, baseUrl });
      const dashboard = data.dashboard || {};
      const panelCount = countPanels(dashboard);
      if (!dashboard.title || panelCount === 0) {
        throw new Error(`invalid dashboard metadata (title=${dashboard.title}, panels=${panelCount})`);
      }

      const unresolved = findUnresolvedImportPlaceholders(dashboard);
      if (unresolved.length > 0) {
        throw new Error(
          `unresolved import placeholders found: ${unresolved.slice(0, 3).join(" | ")}`,
        );
      }

      console.log(`OK ${item.uid} | panels=${panelCount} | title=${dashboard.title}`);
    } catch (err) {
      failures += 1;
      console.error(`FAIL ${item.uid} | ${err.message || err}`);
    }
  }

  if (failures > 0) {
    console.error(`Smoke check failed: ${failures} dashboards`);
    process.exit(1);
  }

  console.log("Smoke check passed.");
}

main().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});
