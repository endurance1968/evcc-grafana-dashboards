/**
 * Script: cross-platform-audit.mjs
 * Purpose: Guard npm, test entrypoints, and repo text artifacts against platform-specific path assumptions.
 * Version: 2026.04.22.3
 * Last modified: 2026-04-22
 */
import fs from "node:fs";
import path from "node:path";

const repoRoot = process.cwd();
const scriptName = "cross-platform-audit.mjs";
const version = "2026.04.22.3";
const lastModified = "2026-04-22";
const blockedNpmScriptPatterns = [
  /(^|\s)powershell(?:\.exe)?(\s|$)/i,
  /(^|\s)pwsh(?:\.exe)?(\s|$)/i,
  /(^|\s)cmd(?:\.exe)?(\s|$)/i,
  /(^|\s)bash(?:\.exe)?(\s|$)/i,
];
const blockedNodePatterns = [
  { pattern: /shell:\s*true/, reason: "using the child-process shell option hides platform-specific quoting and command lookup behavior" },
];
const textFileExtensions = new Set([
  ".cjs",
  ".csv",
  ".env",
  ".example",
  ".js",
  ".json",
  ".md",
  ".mjs",
  ".ps1",
  ".py",
  ".sh",
  ".toml",
  ".txt",
  ".yaml",
  ".yml",
]);
const repoPathPrefixes = ["dashboards", "data", "docs", "scripts", "tests"];
const selfRelativePath = "scripts/test/cross-platform-audit.mjs";
const skippedPathPrefixes = [
  ".git/",
  ".playwright/",
  "node_modules/",
  "tests/artifacts/",
  "tmp/",
  "data/energy-comparison/tibber/",
  "data/energy-comparison/vrm/",
];

function toPortablePath(filePath) {
  return String(filePath).replace(/\\/g, "/");
}

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
    const relative = toPortablePath(path.relative(repoRoot, file));
    if (relative === selfRelativePath) {
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

function isSkippedRepoPath(relativePath) {
  return skippedPathPrefixes.some((prefix) => relativePath === prefix.slice(0, -1) || relativePath.startsWith(prefix));
}

function isTextFile(relativePath) {
  const extension = path.posix.extname(relativePath).toLowerCase();
  if (textFileExtensions.has(extension)) {
    return true;
  }
  return relativePath.endsWith(".env.example");
}

function collectRepoTextFiles(dirPath = repoRoot) {
  const files = [];
  for (const entry of fs.readdirSync(dirPath, { withFileTypes: true })) {
    const fullPath = path.join(dirPath, entry.name);
    const relativePath = toPortablePath(path.relative(repoRoot, fullPath));
    if (isSkippedRepoPath(relativePath)) {
      continue;
    }
    if (entry.isDirectory()) {
      files.push(...collectRepoTextFiles(fullPath));
      continue;
    }
    if (entry.isFile() && isTextFile(relativePath)) {
      files.push(relativePath);
    }
  }
  return files.sort((a, b) => a.localeCompare(b));
}

function lineHasWindowsRepoPath(line) {
  return repoPathPrefixes.some((prefix) => {
    const escapedJsonPath = new RegExp(`(^|[^A-Za-z0-9_-])${prefix}\\\\\\\\[A-Za-z0-9_. -]`);
    const rawPath = new RegExp(`(^|[^A-Za-z0-9_-])${prefix}\\\\[A-Za-z0-9_. -]`);
    return escapedJsonPath.test(line) || rawPath.test(line);
  });
}

function assertPathPatternSelfTest() {
  const samples = [
    { line: '"sourceDir": "dashboards\\\\original\\\\en"', expected: true },
    { line: "sourceDir=dashboards\\original\\en", expected: true },
    { line: '"sourceDir": "dashboards/original/en"', expected: false },
  ];

  for (const sample of samples) {
    const actual = lineHasWindowsRepoPath(sample.line);
    if (actual !== sample.expected) {
      throw new Error(`path separator self-test failed for ${JSON.stringify(sample.line)}: expected ${sample.expected}, got ${actual}`);
    }
  }
}

function auditPortableRepoPaths() {
  const problems = [];
  for (const relativePath of collectRepoTextFiles()) {
    if (relativePath === selfRelativePath) {
      continue;
    }
    const absolutePath = path.join(repoRoot, ...relativePath.split("/"));
    const text = fs.readFileSync(absolutePath, "utf8");
    const lines = text.split(/\r?\n/);
    for (let index = 0; index < lines.length; index += 1) {
      if (lineHasWindowsRepoPath(lines[index])) {
        problems.push(`${relativePath}:${index + 1}: repo-relative paths in checked-in text files must use '/' separators`);
      }
    }
  }
  return problems;
}

function main() {
  console.log(`${scriptName} v${version} (last modified ${lastModified})`);
  assertPathPatternSelfTest();
  const problems = [...auditPackageScripts(), ...auditNodeScripts(), ...auditPortableRepoPaths()];
  if (problems.length > 0) {
    console.error("\nCross-platform audit failed:");
    for (const problem of problems) {
      console.error(`- ${problem}`);
    }
    process.exit(1);
  }
  console.log("Cross-platform audit passed: npm entrypoints are shell-neutral, Node scripts avoid shell:true, and repo text artifacts use portable separators.");
}

main();
