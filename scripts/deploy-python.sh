#!/usr/bin/env sh
# Deploy dashboards to Grafana with the portable POSIX shell flow.
# Reads vm-dashboard-install.env, resolves the dashboard file list and uploads dashboards.
set -eu
SCRIPT_VERSION="2026.06.02.2"
SCRIPT_BUILD_DATE="2026-05-31"
SCRIPT_LAST_MODIFIED="2026-06-02"
SCRIPT_NAME="${0##*/}"

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
CONFIG_PATH="$SCRIPT_DIR/vm-dashboard-install.env"
CLI_URL=""
CLI_TOKEN=""
CLI_PURGE=""
CLI_PURGE_ONLY=""
CLI_THEME=""
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
    --purge-only)
      CLI_PURGE_ONLY="$2"
      shift 2
      ;;
    --theme)
      CLI_THEME="$2"
      shift 2
      ;;
    --yes|-y)
      CLI_YES="true"
      shift 1
      ;;
    --help|-h)
      cat <<'EOF'
Usage: sh ./deploy-python.sh [--config <path>] [--url <url>] [--token <token>] [--theme dark|light|bright|default] [--purge true|false] [--purge-only true|false] [--yes]
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

printf '%s v%s (build %s, last modified %s, run %s)\n' "$SCRIPT_NAME" "$SCRIPT_VERSION" "$SCRIPT_BUILD_DATE" "$SCRIPT_LAST_MODIFIED" "$(date '+%Y-%m-%dT%H:%M:%S%z')"

PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"
export CLI_URL CLI_TOKEN CLI_PURGE CLI_PURGE_ONLY CLI_THEME CLI_YES SCRIPT_DIR PYTHONIOENCODING

python3 - "$CONFIG_PATH" <<'PY'
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

config_path = Path(sys.argv[1])

settings = {
    "GRAFANA_URL": "http://localhost:3000",
    "GRAFANA_AUTH_MODE": "auto",
    "GRAFANA_API_TOKEN": "",
    "GRAFANA_SERVICE_ACCOUNT_TOKEN": "",
    "GRAFANA_USER": "",
    "GRAFANA_PASSWORD": "",
    "GRAFANA_DS_VM_EVCC_UID": "vm-evcc",
    "GRAFANA_FOLDER_UID": "evcc",
    "GRAFANA_FOLDER_TITLE": "EVCC",
    "GRAFANA_THEME": "",
    "DASHBOARD_SOURCE_MODE": "github",
    "GITHUB_REPO": "endurance1968/evcc-grafana-dashboards",
    "GITHUB_REF": "main",
    "DASHBOARD_RAW_BASE_URL": "",
    "DASHBOARD_LANGUAGE": "de",
    "DASHBOARD_VARIANT": "gen",
    "DASHBOARD_LOCAL_DIR": "",
    "PURGE": "false",
    "PURGE_ONLY": "false",
    "DASHBOARD_FILTER_PEAK_POWER_LIMIT": "",
    "DASHBOARD_ENERGY_SAMPLE_INTERVAL": "",
    "DASHBOARD_TARIFF_PRICE_INTERVAL": "",
    "DASHBOARD_FILTER_ENERGY_SAMPLE_INTERVAL": "",
    "DASHBOARD_FILTER_TARIFF_PRICE_INTERVAL": "",
    "DASHBOARD_INSTALLED_WATT_PEAK": "",
    "DASHBOARD_VEHICLE_CONSUMPTION_L_PER_100KM": "",
    "DASHBOARD_FUEL_COST_PER_L": "",
    "DASHBOARD_STORAGE_CAPACITY_WH": "",
    "DASHBOARD_ICE_CONSUMPTION_L_PER_100KM": "",
    "DASHBOARD_FUEL_PRICE_PER_L": "",
    "DASHBOARD_PV_PURCHASE_PRICE": "",
    "DASHBOARD_BATTERY_PURCHASE_PRICE": "",
    "DASHBOARD_RUNNING_COSTS_YEARLY": "",
    "DASHBOARD_BATTERY_CAPACITY_WH": "",
    "DASHBOARD_HEAT_PUMP_LOADPOINT_REGEX": "",
    "DASHBOARD_FILTER_LOADPOINT_BLOCKLIST": "",
    "DASHBOARD_FILTER_EXT_BLOCKLIST": "",
    "DASHBOARD_FILTER_AUX_BLOCKLIST": "",
    "DASHBOARD_FILTER_VEHICLE_BLOCKLIST": "",
    "DASHBOARD_EVCC_URL": "",
    "DASHBOARD_PORTAL_TITLE": "",
    "DASHBOARD_PORTAL_URL": "",
}

if config_path.exists():
    seen_config_keys = set()
    for line_number, raw_line in enumerate(config_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in seen_config_keys:
            raise SystemExit(f"Duplicate key in {config_path} line {line_number}: {key}. Define each key only once; comment out old alternatives.")
        seen_config_keys.add(key)
        settings[key] = value.strip().strip('"\'')

for key in list(settings):
    if os.environ.get(key):
        settings[key] = os.environ[key]

if os.environ.get("CLI_URL"):
    settings["GRAFANA_URL"] = os.environ["CLI_URL"]
if os.environ.get("CLI_TOKEN"):
    settings["GRAFANA_API_TOKEN"] = os.environ["CLI_TOKEN"]
if os.environ.get("CLI_PURGE"):
    settings["PURGE"] = os.environ["CLI_PURGE"]
if os.environ.get("CLI_PURGE_ONLY"):
    settings["PURGE_ONLY"] = os.environ["CLI_PURGE_ONLY"]
if os.environ.get("CLI_THEME"):
    settings["GRAFANA_THEME"] = os.environ["CLI_THEME"]
if os.environ.get("CLI_YES"):
    settings["CLI_YES"] = os.environ["CLI_YES"]
def is_truthy(value):
    return str(value).strip().lower() in {"1", "true", "yes", "on"}

if "DEPLOY_PURGE" in settings and "PURGE" not in settings:
    settings["PURGE"] = settings["DEPLOY_PURGE"]
if "DEPLOY_PURGE_ONLY" in settings and not is_truthy(settings.get("PURGE_ONLY", "false")):
    settings["PURGE_ONLY"] = settings["DEPLOY_PURGE_ONLY"]

if not settings["GRAFANA_API_TOKEN"] and settings.get("GRAFANA_SERVICE_ACCOUNT_TOKEN"):
    settings["GRAFANA_API_TOKEN"] = settings["GRAFANA_SERVICE_ACCOUNT_TOKEN"]

settings["DASHBOARD_SOURCE_MODE"] = (settings.get("DASHBOARD_SOURCE_MODE") or "github").strip().lower()
FIXED_DASHBOARD_FILES = [
    "VM_EVCC_All-time.json",
    "VM_EVCC_Year.json",
    "VM_EVCC_Month.json",
    "VM_EVCC_Today-Details.json",
    "VM_EVCC_Today.json",
    "VM_EVCC_Today-Gauges.json",
    "VM_EVCC_Today-Mobile.json",
]


def require_setting(key, mode):
    if not str(settings.get(key, "") or "").strip():
        raise SystemExit(f"{key} is required when DASHBOARD_SOURCE_MODE={mode}.")


mode = settings["DASHBOARD_SOURCE_MODE"]
if mode == "github":
    require_setting("GITHUB_REPO", mode)
    require_setting("GITHUB_REF", mode)
elif mode == "rawurl":
    require_setting("DASHBOARD_RAW_BASE_URL", mode)
elif mode == "localdir":
    require_setting("DASHBOARD_LOCAL_DIR", mode)
    if not Path(settings["DASHBOARD_LOCAL_DIR"]).is_dir():
        raise SystemExit(f"DASHBOARD_LOCAL_DIR does not exist or is not a directory: {settings['DASHBOARD_LOCAL_DIR']}")
else:
    raise SystemExit("Unsupported DASHBOARD_SOURCE_MODE. Use github, rawurl, or localdir.")



def remote_source_url(relative_path):
    quoted = "/".join(urllib.parse.quote(part) for part in str(relative_path).split("/"))
    if settings["DASHBOARD_SOURCE_MODE"] == "rawurl":
        return f"{settings['DASHBOARD_RAW_BASE_URL'].rstrip('/')}/{quoted}"
    return f"https://raw.githubusercontent.com/{settings['GITHUB_REPO']}/{settings['GITHUB_REF']}/{quoted}"


def fetch_remote_text(relative_path):
    url = remote_source_url(relative_path)
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Failed to download {relative_path} from {url} ({exc.code} {exc.reason})") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to download {relative_path} from {url}: {exc.reason}") from exc


def repo_file_text(relative_path):
    return fetch_remote_text(relative_path)


def load_dashboard_files():
    if settings["DASHBOARD_SOURCE_MODE"] == "localdir":
        missing = [file for file in FIXED_DASHBOARD_FILES if not (Path(settings["DASHBOARD_LOCAL_DIR"]) / file).is_file()]
        if missing:
            raise RuntimeError("DASHBOARD_LOCAL_DIR is missing required dashboard files: " + ", ".join(missing))
        return list(FIXED_DASHBOARD_FILES)
    manifest_path = "dashboards/deploy-manifest.json"
    manifest = json.loads(repo_file_text(manifest_path))
    files = manifest.get("files") or []
    if not isinstance(files, list) or not files:
        raise RuntimeError(f"{manifest_path} from {remote_source_url(manifest_path)} is missing a non-empty files array. Check DASHBOARD_SOURCE_MODE={settings['DASHBOARD_SOURCE_MODE']} and the selected source variables.")
    return [str(file) for file in files]

def auth_mode():
    mode = (settings.get("GRAFANA_AUTH_MODE") or "auto").strip().lower()
    if mode in ("", "auto"):
        if settings.get("GRAFANA_API_TOKEN"):
            return "token"
        if settings.get("GRAFANA_USER") and settings.get("GRAFANA_PASSWORD"):
            return "basic"
        return "token"
    if mode in ("token", "bearer", "service-account", "service_account"):
        return "token"
    if mode in ("basic", "userpass", "user-password"):
        return "basic"
    raise SystemExit(f"Unsupported GRAFANA_AUTH_MODE '{settings.get('GRAFANA_AUTH_MODE')}'. Use auto, token, or basic.")

def add_auth_headers(req):
    mode = auth_mode()
    if mode == "basic":
        if not settings.get("GRAFANA_USER") or not settings.get("GRAFANA_PASSWORD"):
            raise SystemExit("Missing GRAFANA_USER or GRAFANA_PASSWORD for GRAFANA_AUTH_MODE=basic.")
        import base64
        raw = f"{settings['GRAFANA_USER']}:{settings['GRAFANA_PASSWORD']}".encode("utf-8")
        req.add_header("Authorization", f"Basic {base64.b64encode(raw).decode('ascii')}")
        return
    if not settings.get("GRAFANA_API_TOKEN"):
        raise SystemExit("Missing GRAFANA_API_TOKEN. For Grafana 13 set a service-account token in GRAFANA_API_TOKEN, or use GRAFANA_AUTH_MODE=basic with GRAFANA_USER and GRAFANA_PASSWORD.")
    req.add_header("Authorization", f"Bearer {settings['GRAFANA_API_TOKEN']}")

def grafana_version():
    url = settings["GRAFANA_URL"].rstrip("/") + "/api/health"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8") or "{}")
            return payload.get("version") or "unknown"
    except Exception:
        return "unknown"

def api(method, path, body=None, allow_404=False):
    url = settings["GRAFANA_URL"].rstrip("/") + path
    req = urllib.request.Request(url, method=method)
    add_auth_headers(req)
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
        response = exc.read().decode("utf-8", errors="replace")
        if exc.code == 401:
            raise RuntimeError(
                f"Grafana authentication failed for {method} {path} (401). Response: {response}\n"
                "Grafana 13 still supports the legacy /api routes, but API keys are deprecated. "
                "Create a Grafana service-account token and set GRAFANA_API_TOKEN, or set "
                "GRAFANA_AUTH_MODE=basic with GRAFANA_USER and GRAFANA_PASSWORD."
            )
        raise RuntimeError(f"{method} {path} failed ({exc.code}): {response}")


def normalize_grafana_theme():
    raw = str(settings.get("GRAFANA_THEME", "") or "").strip().lower()
    if not raw:
        return None
    if raw in {"dark", "light"}:
        return raw
    if raw in {"bright", "bright-mode", "brightmode"}:
        return "light"
    if raw in {"default", "grafana-default", "system"}:
        return ""
    raise SystemExit("Unsupported GRAFANA_THEME. Use dark, light, bright, or default.")


def grafana_theme_display(theme):
    if theme == "":
        return "default"
    return theme


def apply_grafana_theme(theme):
    preferences = api("GET", "/api/org/preferences") or {}
    body = {}
    for key in ("homeDashboardId", "homeDashboardUID", "timezone", "weekStart"):
        if key in preferences and preferences.get(key) is not None:
            body[key] = preferences.get(key)
    body["theme"] = theme
    api("PUT", "/api/org/preferences", body)
    print(f"Grafana org theme set: {grafana_theme_display(theme)}")

def effective_dashboard_language():
    return "en" if settings["DASHBOARD_VARIANT"] == "orig" else settings["DASHBOARD_LANGUAGE"]


def get_source_subdir():
    language = effective_dashboard_language()
    if settings["DASHBOARD_VARIANT"] == "orig":
        return f"dashboards/original/{language}"
    return f"dashboards/translation/{language}"


def get_source_text(filename):
    if settings["DASHBOARD_SOURCE_MODE"] == "localdir":
        return (Path(settings["DASHBOARD_LOCAL_DIR"]) / filename).read_text(encoding="utf-8")
    return fetch_remote_text(f"{get_source_subdir()}/{filename}")

def replace_ds(node):
    if isinstance(node, str):
        return settings["GRAFANA_DS_VM_EVCC_UID"] if node == "${DS_VM-EVCC}" else node
    if isinstance(node, list):
        return [replace_ds(item) for item in node]
    if isinstance(node, dict):
        out = {k: replace_ds(v) for k, v in node.items()}
        if out.get("type") == "victoriametrics-metrics-datasource" and "uid" in out:
            out["uid"] = settings["GRAFANA_DS_VM_EVCC_UID"]
        return out
    return node

def is_v2_dashboard(raw):
    return isinstance(raw, dict) and raw.get("kind") == "Dashboard" and str(raw.get("apiVersion", "")).startswith("dashboard.grafana.app/v2")


def dashboard_title(raw):
    if is_v2_dashboard(raw):
        return ((raw.get("spec") or {}).get("title") or "")
    return raw.get("title") or ""


def dashboard_uid(raw):
    if is_v2_dashboard(raw):
        return ((raw.get("metadata") or {}).get("name") or "")
    return raw.get("uid") or ""


def dashboard_path(raw):
    uid = dashboard_uid(raw)
    if is_v2_dashboard(raw):
        return f"/apis/dashboard.grafana.app/v2/namespaces/default/dashboards/{urllib.parse.quote(uid)}"
    return f"/api/dashboards/uid/{urllib.parse.quote(uid)}"



def ensure_v2_folder_annotation(raw):
    if not is_v2_dashboard(raw):
        return raw
    metadata = raw.setdefault("metadata", {})
    annotations = metadata.setdefault("annotations", {})
    annotations["grafana.app/folder"] = settings["GRAFANA_FOLDER_UID"]
    return raw

def build_inputs(raw):
    if is_v2_dashboard(raw):
        return []
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

def build_dashboard_marker(settings):
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    if settings["DASHBOARD_SOURCE_MODE"] == "localdir":
        source = f"localdir:{settings['DASHBOARD_LOCAL_DIR']}"
        return f"deployed {timestamp} | {source}"
    if settings["DASHBOARD_SOURCE_MODE"] == "rawurl":
        source = f"rawurl:{settings['DASHBOARD_RAW_BASE_URL'].rstrip('/')}"
    else:
        source = f"github:{settings['GITHUB_REPO']}@{settings['GITHUB_REF']}"
    return f"deployed {timestamp} | {effective_dashboard_language()}/{settings['DASHBOARD_VARIANT']} | {source}"



def build_dashboard_overrides(settings):
    return {
        "peakPowerLimit": settings.get("DASHBOARD_FILTER_PEAK_POWER_LIMIT", ""),
        "energySampleInterval": settings.get("DASHBOARD_ENERGY_SAMPLE_INTERVAL", "") or settings.get("DASHBOARD_FILTER_ENERGY_SAMPLE_INTERVAL", ""),
        "tariffPriceInterval": settings.get("DASHBOARD_TARIFF_PRICE_INTERVAL", "") or settings.get("DASHBOARD_FILTER_TARIFF_PRICE_INTERVAL", ""),
        "installedWattPeak": settings.get("DASHBOARD_INSTALLED_WATT_PEAK", ""),
        "vehicleConsumption": settings.get("DASHBOARD_VEHICLE_CONSUMPTION_L_PER_100KM", "") or settings.get("DASHBOARD_ICE_CONSUMPTION_L_PER_100KM", ""),
        "fuelCost": settings.get("DASHBOARD_FUEL_COST_PER_L", "") or settings.get("DASHBOARD_FUEL_PRICE_PER_L", ""),
        "purchasePricePv": settings.get("DASHBOARD_PV_PURCHASE_PRICE", ""),
        "batteryPurchasePrice": settings.get("DASHBOARD_BATTERY_PURCHASE_PRICE", ""),
        "runningCosts": settings.get("DASHBOARD_RUNNING_COSTS_YEARLY", ""),
        "storageCapacity": settings.get("DASHBOARD_STORAGE_CAPACITY_WH", "") or settings.get("DASHBOARD_BATTERY_CAPACITY_WH", ""),
        "heatPumpLoadpointRegex": settings.get("DASHBOARD_HEAT_PUMP_LOADPOINT_REGEX", ""),
        "loadpointBlocklist": settings.get("DASHBOARD_FILTER_LOADPOINT_BLOCKLIST", ""),
        "extBlocklist": settings.get("DASHBOARD_FILTER_EXT_BLOCKLIST", ""),
        "auxBlocklist": settings.get("DASHBOARD_FILTER_AUX_BLOCKLIST", ""),
        "vehicleBlocklist": settings.get("DASHBOARD_FILTER_VEHICLE_BLOCKLIST", ""),
        "evccUrl": settings.get("DASHBOARD_EVCC_URL", ""),
        "inverterPortalTitle": settings.get("DASHBOARD_PORTAL_TITLE", ""),
        "inverterPortalUrl": settings.get("DASHBOARD_PORTAL_URL", ""),
    }

def apply_dashboard_build_description(raw, marker):
    if not marker:
        return raw
    if is_v2_dashboard(raw):
        for variable in (raw.get("spec") or {}).get("variables") or []:
            variable_spec = variable.get("spec") or {}
            if variable_spec.get("name") == "dashboardBuild":
                variable_spec["description"] = marker
                variable["spec"] = variable_spec
        return raw

    for variable in (raw.get("templating") or {}).get("list") or []:
        if variable.get("name") == "dashboardBuild":
            variable["description"] = marker
    return raw
def apply_dashboard_filter_overrides(raw, overrides):
    if not overrides:
        return raw
    if is_v2_dashboard(raw):
        for variable in (raw.get("spec") or {}).get("variables") or []:
            variable_spec = variable.get("spec") or {}
            name = variable_spec.get("name")
            value = str(overrides.get(name, "") or "").strip()
            if not value:
                continue
            if variable.get("kind") != "QueryVariable":
                variable_spec["query"] = value
            current = dict(variable_spec.get("current") or {})
            current["text"] = value
            current["value"] = value
            variable_spec["current"] = current
            if "options" in variable_spec:
                variable_spec["options"] = [{"selected": True, "text": value, "value": value}]
            variable["spec"] = variable_spec
        return raw

    templating = raw.get("templating") or {}
    variables = templating.get("list") or []
    for variable in variables:
        name = variable.get("name")
        value = str(overrides.get(name, "") or "").strip()
        if not value:
            continue
        variable["query"] = value
        current = dict(variable.get("current") or {})
        current["text"] = value
        current["value"] = value
        variable["current"] = current
        if "options" in variable:
            variable["options"] = [{"selected": True, "text": value, "value": value}]
    return raw


def confirm_apply(prompt):
    if settings.get("CLI_YES", "").lower() == "true":
        return True
    try:
        with open("/dev/tty", "r", encoding="utf-8", errors="replace") as tty:
            sys.stdout.write(prompt)
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


def update_library_panel(element, existing):
    uid = element.get("uid")
    if not uid:
        return
    body = {
        "name": element.get("name") or existing.get("name"),
        "kind": element.get("kind") or existing.get("kind") or 1,
        "model": replace_ds(element.get("model") or {}),
        "version": existing.get("version"),
    }
    folder_uid = existing.get("folderUid") or element.get("folderUid")
    if folder_uid:
        body["folderUid"] = folder_uid
    api("PATCH", f"/api/library-elements/{urllib.parse.quote(uid)}", body)
    print(f"Updated library panel: {body['name']} [{uid}]")

def create_library_panel(element):
    uid = element.get("uid")
    if not uid:
        return
    body = {
        "uid": uid,
        "name": element.get("name"),
        "kind": element.get("kind") or 1,
        "folderUid": settings["GRAFANA_FOLDER_UID"],
        "model": replace_ds(element.get("model") or {}),
    }
    api("POST", "/api/library-elements", body)
    print(f"Created library panel: {body['name']} [{uid}]")

def import_dashboard(dashboard):
    raw = dashboard["raw"]
    if is_v2_dashboard(raw):
        path = dashboard_path(raw)
        existing = api("GET", path, allow_404=True)
        if existing is not None:
            resource_version = (existing.get("metadata") or {}).get("resourceVersion")
            if resource_version:
                raw.setdefault("metadata", {})["resourceVersion"] = resource_version
                api("PUT", path, raw)
                return
        api("POST", "/apis/dashboard.grafana.app/v2/namespaces/default/dashboards", raw)
        return

    body = {
        "dashboard": raw,
        "folderUid": settings["GRAFANA_FOLDER_UID"],
        "overwrite": True,
        "message": "EVCC VM dashboard install",
        "inputs": dashboard["inputs"],
    }
    api("POST", "/api/dashboards/import", body)

DASHBOARD_FILES = load_dashboard_files()

dashboard_build_marker = build_dashboard_marker(settings)
dashboard_overrides = build_dashboard_overrides(settings)
purge_only = is_truthy(settings.get("PURGE_ONLY", "false"))
purge_enabled = is_truthy(settings.get("PURGE", "false")) or purge_only
grafana_theme = normalize_grafana_theme()

dashboards = []
library = {}
for filename in DASHBOARD_FILES:
    raw = json.loads(get_source_text(filename))
    raw = apply_dashboard_filter_overrides(raw, dashboard_overrides)
    raw = apply_dashboard_build_description(raw, dashboard_build_marker)
    raw = replace_ds(raw)
    raw = ensure_v2_folder_annotation(raw)
    dashboards.append({"raw": raw, "inputs": build_inputs(raw)})
    for uid, element in raw.get("__elements", {}).items():
        library[uid] = element

api("GET", "/api/search?limit=1")
print("Grafana check: OK")
print(f"URL: {settings['GRAFANA_URL']}")
print(f"Grafana version: {grafana_version()}")
print(f"Auth mode: {auth_mode()}")
print(f"Folder: {settings['GRAFANA_FOLDER_TITLE']} ({settings['GRAFANA_FOLDER_UID']})")
print(f"Datasource UID: {settings['GRAFANA_DS_VM_EVCC_UID']}")
if grafana_theme is not None:
    action = "not applied in purge-only mode" if purge_only else "will update org preference"
    print(f"Grafana theme: {grafana_theme_display(grafana_theme)} ({action})")
if settings["DASHBOARD_SOURCE_MODE"] == "localdir":
    print(f"Source: localdir / {settings['DASHBOARD_LOCAL_DIR']}")
else:
    if settings["DASHBOARD_SOURCE_MODE"] == "rawurl":
        print(f"Source: rawurl / {settings['DASHBOARD_RAW_BASE_URL'].rstrip('/')}")
    else:
        print(f"Source: github / {settings['GITHUB_REPO']} / {settings['GITHUB_REF']}")
    print(f"Language: {settings['DASHBOARD_LANGUAGE']}")
    print(f"Variant: {settings['DASHBOARD_VARIANT']}")
    if settings["DASHBOARD_VARIANT"] == "orig" and settings["DASHBOARD_LANGUAGE"] != "en":
        print("Effective source language: en (orig dashboards stay English)")
print(f"Build marker: {dashboard_build_marker}")
print(f"Purge: {settings['PURGE']}")
print(f"Purge only: {settings['PURGE_ONLY']}")
active_dashboard_overrides = {k: v for k, v in dashboard_overrides.items() if str(v).strip()}
if active_dashboard_overrides:
    print()
    print("Will apply dashboard overrides:")
    for key, value in active_dashboard_overrides.items():
        print(f"- {key} = {value}")
print()
if purge_only:
    print("Will inspect dashboards for purge-only deletion:")
else:
    print("Will import dashboards:")
for dashboard in dashboards:
    print(f"- {dashboard_title(dashboard['raw'])} [{dashboard_uid(dashboard['raw'])}]")
print()
if library:
    print("Dashboards embed these legacy library panels:")
    for element in library.values():
        print(f"- {element.get('name')} [{element.get('uid')}]")
else:
    print("Panel mode: inline dashboards (no Grafana library panels will be created or updated)")

existing_library = {}
for element in library.values():
    uid = element.get("uid")
    if not uid:
        continue
    existing = api("GET", f"/api/library-elements/{urllib.parse.quote(uid)}", allow_404=True)
    if existing is not None:
        existing_library[uid] = existing["result"]

if not purge_enabled and existing_library:
    print()
    print("Existing library panels already present and will be updated because purge=false:")
    for item in existing_library.values():
        print(f"- {item.get('name')} [{item.get('uid')}]")
    print("Dashboard import will use the updated embedded __elements definitions.")

if purge_enabled:
    existing_dashboards = []
    for dashboard in dashboards:
        uid = dashboard_uid(dashboard["raw"])
        if not uid:
            continue
        existing = api("GET", dashboard_path(dashboard["raw"]), allow_404=True)
        if existing is not None:
            existing_dashboards.append(existing.get("dashboard") or existing)

    print()
    if purge_only:
        print("Will delete existing dashboards without import:")
    else:
        print("Will delete existing dashboards before import:")
    if not existing_dashboards:
        print("- none")
    else:
        for item in existing_dashboards:
            print(f"- {dashboard_title(item)} [{dashboard_uid(item)}]")
    print()
    if library:
        if purge_only:
            print("Will delete referenced legacy library panels after dashboard deletion:")
            if not existing_library:
                print("- none")
            else:
                for item in existing_library.values():
                    print(f"- {item.get('name')} [{item.get('uid')}]")
        else:
            print("Will ensure referenced legacy library panels before import:")
            if not existing_library:
                print("- none found yet; missing panels will be created")
            else:
                for item in existing_library.values():
                    print(f"- {item.get('name')} [{item.get('uid')}]")
    else:
        print("Panel mode: inline dashboards; no library panel API calls are needed")

print()
confirm_prompt = "Proceed with purge-only deletion? [y/N] " if purge_only else "Proceed with dashboard deployment? [y/N] "
if not confirm_apply(confirm_prompt):
    print("Aborted. No changes applied.")
    raise SystemExit(0)

if grafana_theme is not None and not purge_only:
    apply_grafana_theme(grafana_theme)

if purge_enabled:
    for dashboard in dashboards:
        uid = dashboard_uid(dashboard["raw"])
        if uid:
            delete_and_report("dashboard", dashboard_title(dashboard["raw"]) or uid, uid, dashboard_path(dashboard["raw"]))
    if purge_only:
        for uid, element in sorted(library.items()):
            delete_and_report("library panel", element.get("name") or uid, uid, f"/api/library-elements/{urllib.parse.quote(uid)}")
        print()
        print("Purge-only finished. No dashboards imported.")
        raise SystemExit(0)

folder_uid = urllib.parse.quote(settings["GRAFANA_FOLDER_UID"])
if api("GET", f"/api/folders/{folder_uid}", allow_404=True) is None:
    api("POST", "/api/folders", {"uid": settings["GRAFANA_FOLDER_UID"], "title": settings["GRAFANA_FOLDER_TITLE"]})

for uid, element in sorted(library.items()):
    if uid in existing_library:
        update_library_panel(element, existing_library[uid])
        continue
    create_library_panel(element)

for dashboard in dashboards:
    print(f"Importing dashboard: {dashboard_title(dashboard['raw'])} [{dashboard_uid(dashboard['raw'])}]")
    import_dashboard(dashboard)
    print(f"Imported dashboard: {dashboard_title(dashboard['raw'])}")

print()
print("Install finished.")
print(f"Folder: {settings['GRAFANA_FOLDER_TITLE']} ({settings['GRAFANA_FOLDER_UID']})")
PY
