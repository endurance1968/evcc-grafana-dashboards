/**
 * Script: cross-platform-audit.mjs
 * Purpose: Guard npm and test entrypoints against Windows-only shell assumptions.
 * Version: 2026.04.16.3
 * Last modified: 2026-04-16
 */
import fs from "node:fs";
import path from "node:path";

const repoRoot = process.cwd();
const scriptName = "cross-platform-audit.mjs";
const version = "2026.04.16.3";
const lastModified = "2026-04-16";
const blockedNpmScriptPatterns = [
  /(^|\s)powershell(?:\.exe)?(\s|$)/i,
  /(^|\s)pwsh(?:\.exe)?(\s|$)/i,
  /(^|\s)cmd(?:\.exe)?(\s|$)/i,
  /(^|\s)bash(?:\.exe)?(\s|$)/i,
];
const blockedNodePatterns = [
  { pattern: /shell:\s*true/, reason: "using the child-process shell option hides platform-specific quoting and command lookup behavior" },
];

function collectFiles(dir, predicate) {
  const out = [];
  if (!fs.existsSync(dir)) {
    return out;
  }
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...collectFiles(fullPath, predicate));
    } else if (entry.isFile() && predicate(fullPath)) {
      out.push(fullPath);
    }
  }
  return out.sort((a, b) => a.localeCompare(b));
}

function auditPackageScripts() {
  const packageJson = JSON.parse(fs.readFileSync(path.join(repoRoot, "package.json"), "utf8"));
  const scripts = packageJson.scripts || {};
  const problems = [];
  for (const [name, command] of Object.entries(scripts)) {
    for (const pattern of blockedNpmScriptPatterns) {
      if (pattern.test(command)) {
        problems.push(`package.json script '${name}' uses a shell-specific command: ${command}`);
        break;
      }
    }
  }
  return problems;
}

function auditNodeScripts() {
  const files = collectFiles(path.join(repoRoot, "scripts"), (file) => file.endsWith(".mjs"));
  const problems = [];
  for (const file of files) {
    const relative = path.relative(repoRoot, file).replace(/\\/g, "/");
    if (relative === "scripts/test/cross-platform-audit.mjs") {
      continue;
    }
    const text = fs.readFileSync(file, "utf8");
    for (const { pattern, reason } of blockedNodePatterns) {
      if (pattern.test(text)) {
        problems.push(`${relative}: ${reason}`);
      }
    }
  }
  return problems;
}

function main() {
  console.log(`${scriptName} v${version} (last modified ${lastModified})`);
  const problems = [...auditPackageScripts(), ...auditNodeScripts()];
  if (problems.length > 0) {
    console.error("\nCross-platform audit failed:");
    for (const problem of problems) {
      console.error(`- ${problem}`);
    }
    process.exit(1);
  }
  console.log("Cross-platform audit passed: npm entrypoints are shell-neutral and Node scripts avoid shell:true.");
}

main();
