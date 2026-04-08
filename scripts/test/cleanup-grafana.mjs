/**
 * Remove imported Grafana test dashboards and folders created during test runs.
 */
import {
  grafanaApi,
  loadEnvFile,
  optionalEnv,
  parseArg,
  requireEnv,
} from "./_lib.mjs";

loadEnvFile(parseArg("env", ".env"));

const baseUrl = requireEnv("GRAFANA_URL");
const token = requireEnv("GRAFANA_API_TOKEN");
const folderUid = parseArg("folderUid", optionalEnv("GRAFANA_TEST_FOLDER_UID", "evcc-test"));

async function listDashboardsInFolder() {
  const query = `/api/search?type=dash-db&limit=5000&folderUIDs=${encodeURIComponent(folderUid)}`;
  return await grafanaApi(query, { token, baseUrl });
}

async function listAllLibraryElements() {
  const all = [];
  let page = 1;

  while (true) {
    const res = await grafanaApi(`/api/library-elements?page=${page}&perPage=500`, {
      token,
      baseUrl,
    });
    const chunk = res?.result?.elements || [];
    all.push(...chunk);
    if (!chunk.length || chunk.length < 500) {
      break;
    }
    page += 1;
  }

  return all;
}

async function main() {
  console.log(`Cleaning Grafana test folder '${folderUid}'...`);

  const dashboards = await listDashboardsInFolder();
  for (const d of dashboards) {
    await grafanaApi(`/api/dashboards/uid/${encodeURIComponent(d.uid)}`, {
      method: "DELETE",
      token,
      baseUrl,
    });
    console.log(`Deleted dashboard: ${d.uid} | ${d.title}`);
  }

  const libraryElements = await listAllLibraryElements();
  const inFolder = libraryElements.filter((el) => el.folderUid === folderUid);
  for (const el of inFolder) {
    await grafanaApi(`/api/library-elements/${encodeURIComponent(el.uid)}`, {
      method: "DELETE",
      token,
      baseUrl,
    });
    console.log(`Deleted library panel: ${el.uid} | ${el.name}`);
  }

  console.log(
    `Cleanup complete. Dashboards deleted=${dashboards.length}, library panels deleted=${inFolder.length}. Datasources untouched.`,
  );
}

main().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});
