/**
 * Script: energy-validation.mjs
 * Purpose: Run the external energy comparison validator with a portable Python interpreter lookup.
 * Version: 2026.07.28.1
 * Last modified: 2026-07-28
 */
import path from "node:path";
import { spawnSync } from "node:child_process";

const repoRoot = process.cwd();

function commandExists(command, args = ["--version"]) {
  const result = spawnSync(command, args, { encoding: "utf8", stdio: "pipe" });
  return result.status === 0;
}

function pythonMeetsMinimumVersion(command) {
  const result = spawnSync(
    command,
    ["-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"],
    { encoding: "utf8", stdio: "pipe" },
  );
  return result.status === 0;
}

function findPython() {
  const candidates = [
    process.env.PYTHON,
    process.platform === "win32" ? path.join(process.env.LOCALAPPDATA || "", "Python", "bin", "python.exe") : "",
    process.platform === "win32" ? path.join(process.env.USERPROFILE || "", "AppData", "Local", "Python", "bin", "python.exe") : "",
    "python3",
    "python",
  ].filter(Boolean);

  for (const candidate of candidates) {
    if (commandExists(candidate) && pythonMeetsMinimumVersion(candidate)) {
      return candidate;
    }
  }
  throw new Error("No Python >= 3.12 interpreter found. Set PYTHON to the intended interpreter.");
}

function main() {
  const python = findPython();
  const cliArgs = process.argv.slice(2);
  const vrmImport = cliArgs.includes("--vrm-import");
  const script = vrmImport ? "scripts/helper/validate-vrm-import.py" : "scripts/helper/validate_energy_comparison.py";
  const args = [script, ...cliArgs.filter((arg) => arg !== "--vrm-import")];
  console.log(`$ ${[python, ...args].join(" ")}`);
  const result = spawnSync(python, args, { cwd: repoRoot, stdio: "inherit" });
  if (result.error) {
    throw result.error;
  }
  process.exit(result.status ?? 1);
}

try {
  main();
} catch (error) {
  console.error(error.message || error);
  process.exit(2);
}
