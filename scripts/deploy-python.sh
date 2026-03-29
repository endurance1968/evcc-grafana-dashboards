#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CONFIG_PATH="$SCRIPT_DIR/vm-dashboard-install.env"
CLI_URL=""
CLI_TOKEN=""
CLI_PURGE=""
CLI_YES="false"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --config)
      CONFIG_PATH="$2"
      shift 2
      ;;
    --url)
      CLI_URL="$2"
      shift 2
      ;;
    --token)
      CLI_TOKEN="$2"
      shift 2
      ;;
    --purge)
      CLI_PURGE="$2"
      shift 2
      ;;
    --yes|-y)
      CLI_YES="true"
      shift 1
      ;;
    --help|-h)
      cat <<'EOF'
Usage: sh ./deploy-python.sh [--config <path>] [--url <url>] [--token <token>] [--purge true|false] [--yes]
EOF
      exit 0
      ;;
    *)
      if [ "$CONFIG_PATH" = "$SCRIPT_DIR/vm-dashboard-install.env" ] && [ -f "$1" ]; then
        CONFIG_PATH="$1"
        shift 1
      else
        echo "Unknown argument: $1" >&2
        exit 1
      fi
      ;;
  esac
done

export CLI_URL CLI_TOKEN CLI_PURGE CLI_YES

python3 - "$CONFIG_PATH" <<'PY'
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

config_path = Path(sys.argv[1])

settings = {
    "GRAFANA_URL": "http://localhost:3000",
    "GRAFANA_API_TOKEN": "",
    "GRAFANA_DS_VM_EVCC_UID": "vm-evcc",
    "GRAFANA_FOLDER_UID": "evcc",
    "GRAFANA_FOLDER_TITLE": "EVCC",
    "DASHBOARD_SOURCE_MODE": "github",
    "GITHUB_REPO": "endurance1968/evcc-grafana-dashboards",
    "GITHUB_REF": "main",
    "DASHBOARD_LANGUAGE": "en",
    "DASHBOARD_VARIANT": "gen",
    "DASHBOARD_LOCAL_DIR": "",
    "PURGE": "false",
}

if config_path.exists():
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        settings[key.strip()] = value.strip().strip('"\'')

for key in list(settings):
    if os.environ.get(key):
        settings[key] = os.environ[key]

if os.environ.get("CLI_URL"):
    settings["GRAFANA_URL"] = os.environ["CLI_URL"]
if os.environ.get("CLI_TOKEN"):
    settings["GRAFANA_API_TOKEN"] = os.environ["CLI_TOKEN"]
if os.environ.get("CLI_PURGE"):
    settings["PURGE"] = os.environ["CLI_PURGE"]
if os.environ.get("CLI_YES"):
    settings["CLI_YES"] = os.environ["CLI_YES"]
if "DEPLOY_PURGE" in settings and "PURGE" not in settings:
    settings["PURGE"] = settings["DEPLOY_PURGE"]

if not settings["GRAFANA_API_TOKEN"]:
    raise SystemExit("Missing GRAFANA_API_TOKEN. Set it in the config file, environment, or --token.")
if settings["DASHBOARD_SOURCE_MODE"] == "local" and not settings["DASHBOARD_LOCAL_DIR"]:
    raise SystemExit("DASHBOARD_LOCAL_DIR is required when DASHBOARD_SOURCE_MODE=local.")

DASHBOARD_FILES = [
    "VM_ EVCC_ All-time.json",
    "VM_ EVCC_ Jahr.json",
    "VM_ EVCC_ Monat.json",
    "VM_ EVCC_ Today - Details.json",
    "VM_ EVCC_ Today.json",
    "VM_ EVCC_ Today - Mobile.json",
]

def api(method, path, body=None, allow_404=False):
    url = settings["GRAFANA_URL"].rstrip("/") + path
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {settings['GRAFANA_API_TOKEN']}")
    req.add_header("Accept", "application/json")
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data) as resp:
            text = resp.read().decode("utf-8")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        if allow_404 and exc.code == 404:
            return None
        raise RuntimeError(f"{method} {path} failed ({exc.code}): {exc.read().decode('utf-8')}")

def get_source_text(filename):
    if settings["DASHBOARD_SOURCE_MODE"] == "local":
        return (Path(settings["DASHBOARD_LOCAL_DIR"]) / filename).read_text(encoding="utf-8")
    subdir = f"dashboards/original/{settings['DASHBOARD_LANGUAGE']}" if settings["DASHBOARD_VARIANT"] == "orig" else f"dashboards/translation/{settings['DASHBOARD_LANGUAGE']}"
    quoted = "/".join(urllib.parse.quote(part) for part in filename.split("/"))
    url = f"https://raw.githubusercontent.com/{settings['GITHUB_REPO']}/{settings['GITHUB_REF']}/{subdir}/{quoted}"
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode("utf-8")

def replace_ds(node):
    if isinstance(node, str):
        return settings["GRAFANA_DS_VM_EVCC_UID"] if node == "${DS_VM-EVCC}" else node
    if isinstance(node, list):
        return [replace_ds(item) for item in node]
    if isinstance(node, dict):
        return {k: replace_ds(v) for k, v in node.items()}
    return node

def build_inputs(raw):
    out = []
    for item in raw.get("__inputs", []):
        if not item or not item.get("name") or not item.get("type"):
            continue
        if item["type"] == "datasource":
            if item["name"] == "DS_VM-EVCC":
                value = settings["GRAFANA_DS_VM_EVCC_UID"]
            elif item.get("pluginId") == "__expr__":
                value = "__expr__"
            else:
                raise RuntimeError(f"Missing datasource mapping for {item['name']}")
            out.append({"name": item["name"], "type": item["type"], "pluginId": item.get("pluginId"), "value": value})
        else:
            out.append({"name": item["name"], "type": item["type"], "value": item.get("value", "")})
    return out

def confirm_apply():
    if settings.get("CLI_YES", "").lower() == "true":
        return True
    try:
        with open("/dev/tty", "r", encoding="utf-8", errors="replace") as tty:
            sys.stdout.write("Proceed with dashboard deployment? [y/N] ")
            sys.stdout.flush()
            answer = tty.readline()
    except OSError:
        return False
    return answer.strip().lower() in ("y", "yes")

def delete_and_report(kind, name, uid, path):
    existing = api("GET", path, allow_404=True)
    if existing is None:
        print(f"Skipping {kind} delete (not found): {name} [{uid}]")
        return
    api("DELETE", path, allow_404=True)
    after_delete = api("GET", path, allow_404=True)
    if after_delete is None:
        print(f"Deleted {kind}: {name} [{uid}]")
    else:
        raise RuntimeError(f"Failed to delete {kind} {name} [{uid}]")
dashboards = []
library = {}
for filename in DASHBOARD_FILES:
    raw = json.loads(get_source_text(filename))
    dashboards.append({"raw": raw, "inputs": build_inputs(raw)})
    for uid, element in raw.get("__elements", {}).items():
        library[uid] = element

api("GET", "/api/search?limit=1")
print("Grafana check: OK")
print(f"URL: {settings['GRAFANA_URL']}")
print(f"Folder: {settings['GRAFANA_FOLDER_TITLE']} ({settings['GRAFANA_FOLDER_UID']})")
print(f"Datasource UID: {settings['GRAFANA_DS_VM_EVCC_UID']}")
if settings["DASHBOARD_SOURCE_MODE"] == "local":
    print(f"Source: local / {settings['DASHBOARD_LOCAL_DIR']}")
else:
    print(f"Source: github / {settings['GITHUB_REPO']} / {settings['GITHUB_REF']}")
print(f"Language: {settings['DASHBOARD_LANGUAGE']}")
print(f"Variant: {settings['DASHBOARD_VARIANT']}")
print(f"Purge: {settings['PURGE']}")
print()
print("Will import dashboards:")
for dashboard in dashboards:
    print(f"- {dashboard['raw'].get('title')} [{dashboard['raw'].get('uid')}]")
print()
print("Dashboards embed these library panels:")
for element in library.values():
    print(f"- {element.get('name')} [{element.get('uid')}]")

existing_library = {}
for element in library.values():
    uid = element.get("uid")
    if not uid:
        continue
    existing = api("GET", f"/api/library-elements/{urllib.parse.quote(uid)}", allow_404=True)
    if existing is not None:
        existing_library[uid] = existing["result"]

if settings["PURGE"].lower() != "true" and existing_library:
    print()
    print("Existing library panels already present and will be left in place because purge=false:")
    for item in existing_library.values():
        print(f"- {item.get('name')} [{item.get('uid')}]")
    print("Dashboard import will rely on the embedded __elements definitions.")

if settings["PURGE"].lower() == "true":
    existing_dashboards = []
    for dashboard in dashboards:
        uid = dashboard["raw"].get("uid")
        if not uid:
            continue
        existing = api("GET", f"/api/dashboards/uid/{urllib.parse.quote(uid)}", allow_404=True)
        if existing is not None:
            existing_dashboards.append(existing["dashboard"])

    print()
    print("Will delete existing dashboards before import:")
    if not existing_dashboards:
        print("- none")
    else:
        for item in existing_dashboards:
            print(f"- {item.get('title')} [{item.get('uid')}]")

    print()
    print("Will delete existing library panels before import:")
    if not existing_library:
        print("- none")
    else:
        for item in existing_library.values():
            print(f"- {item.get('name')} [{item.get('uid')}]")

print()
if not confirm_apply():
    print("Aborted. No changes applied.")
    raise SystemExit(0)

folder_uid = urllib.parse.quote(settings["GRAFANA_FOLDER_UID"])
if api("GET", f"/api/folders/{folder_uid}", allow_404=True) is None:
    api("POST", "/api/folders", {"uid": settings["GRAFANA_FOLDER_UID"], "title": settings["GRAFANA_FOLDER_TITLE"]})

if settings["PURGE"].lower() == "true":
    for dashboard in dashboards:
        uid = dashboard["raw"].get("uid")
        if uid:
            delete_and_report("dashboard", dashboard["raw"].get("title"), uid, f"/api/dashboards/uid/{urllib.parse.quote(uid)}")
    for uid, item in existing_library.items():
        delete_and_report("library panel", item.get("name"), uid, f"/api/library-elements/{urllib.parse.quote(uid)}")
for dashboard in dashboards:
    body = {
        "dashboard": dashboard["raw"],
        "folderUid": settings["GRAFANA_FOLDER_UID"],
        "overwrite": True,
        "message": "EVCC VM dashboard install",
        "inputs": dashboard["inputs"],
    }
    api("POST", "/api/dashboards/import", body)
    print(f"Imported dashboard: {dashboard['raw'].get('title')}")

print()
print("Install finished.")
print(f"Folder: {settings['GRAFANA_FOLDER_TITLE']} ({settings['GRAFANA_FOLDER_UID']})")
PY

