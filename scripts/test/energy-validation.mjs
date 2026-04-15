/**
 * Script: energy-validation.mjs
 * Purpose: Run the external energy comparison validator with a portable Python interpreter lookup.
 * Version: 2026.04.15.1
 * Last modified: 2026-04-15
 */
import path from "node:path";
import { spawnSync } from "node:child_process";

const repoRoot = process.cwd();

function commandExists(command, args = ["--version"]) {
  const result = spawnSync(command, args, { encoding: "utf8", stdio: "pipe" });
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
    if (commandExists(candidate)) {
      return candidate;
    }
  }
  throw new Error("No working Python interpreter found. Set PYTHON to the intended interpreter.");
}

function main() {
  const python = findPython();
  const args = ["scripts/helper/validate_energy_comparison.py", ...process.argv.slice(2)];
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
