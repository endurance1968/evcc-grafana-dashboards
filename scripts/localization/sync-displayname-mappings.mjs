import fs from "node:fs";
import path from "node:path";

const repoRoot = process.cwd();
const localizationDir = path.join(repoRoot, "dashboards", "localization");
const originalDir = path.join(repoRoot, "dashboards", "original");
const translationDir = path.join(repoRoot, "dashboards", "translation");
const configPath = path.join(localizationDir, "languages.json");

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function writeJson(filePath, data) {
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2) + "\n", "utf8");
}

function readLanguagesConfig() {
  const parsed = readJson(configPath);
  const sourceLanguage = String(parsed.sourceLanguage || "de").trim();
  const targetLanguages = Array.isArray(parsed.targetLanguages)
    ? parsed.targetLanguages.map((x) => String(x).trim()).filter(Boolean)
    : [];
  return { sourceLanguage, targetLanguages };
}

function collectJsonFiles(dirPath) {
  const entries = fs.readdirSync(dirPath, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const fullPath = path.join(dirPath, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectJsonFiles(fullPath));
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.json')) {
      files.push(fullPath);
    }
  }
  return files;
}

function collectDisplayNamePairs(sourceNode, targetNode, pairs) {
  if (Array.isArray(sourceNode) && Array.isArray(targetNode)) {
    const len = Math.min(sourceNode.length, targetNode.length);
    for (let i = 0; i < len; i += 1) {
      collectDisplayNamePairs(sourceNode[i], targetNode[i], pairs);
    }
    return;
  }

  if (!sourceNode || !targetNode || typeof sourceNode !== 'object' || typeof targetNode !== 'object') {
    return;
  }

  if (
    typeof sourceNode.id === 'string' &&
    typeof targetNode.id === 'string' &&
    sourceNode.id === targetNode.id &&
    (sourceNode.id === 'displayName' || sourceNode.id === 'displayNameFromDS') &&
    typeof sourceNode.value === 'string' &&
    typeof targetNode.value === 'string' &&
    sourceNode.value !== targetNode.value
  ) {
    pairs.set(sourceNode.value, targetNode.value);
  }

  const keys = new Set([...Object.keys(sourceNode), ...Object.keys(targetNode)]);
  for (const key of keys) {
    if (!(key in sourceNode) || !(key in targetNode)) {
      continue;
    }
    collectDisplayNamePairs(sourceNode[key], targetNode[key], pairs);
  }
}

function updateMapping(sourceLanguage, targetLanguage) {
  const sourceLangDir = path.join(originalDir, sourceLanguage);
  const targetLangDir = path.join(translationDir, targetLanguage);
  const mappingPath = path.join(localizationDir, `${sourceLanguage}_to_${targetLanguage}.json`);

  if (!fs.existsSync(targetLangDir) || !fs.existsSync(mappingPath)) {
    return { targetLanguage, added: 0, totalPairs: 0 };
  }

  const mapping = readJson(mappingPath);
  mapping.exact = mapping.exact || {};
  mapping.contains = Array.isArray(mapping.contains) ? mapping.contains : [];

  const files = collectJsonFiles(sourceLangDir);
  const pairs = new Map();

  for (const sourceFile of files) {
    const relative = path.relative(sourceLangDir, sourceFile);
    const targetFile = path.join(targetLangDir, relative);
    if (!fs.existsSync(targetFile)) {
      continue;
    }

    const sourceJson = readJson(sourceFile);
    const targetJson = readJson(targetFile);
    collectDisplayNamePairs(sourceJson, targetJson, pairs);
  }

  let added = 0;
  for (const [sourceValue, targetValue] of pairs.entries()) {
    if (!Object.hasOwn(mapping.exact, sourceValue)) {
      mapping.exact[sourceValue] = targetValue;
      added += 1;
    }
  }

  if (added > 0) {
    const sortedExact = Object.fromEntries(Object.entries(mapping.exact).sort(([a], [b]) => a.localeCompare(b, 'de')));
    mapping.exact = sortedExact;
    writeJson(mappingPath, mapping);
  }

  return { targetLanguage, added, totalPairs: pairs.size };
}

function main() {
  const { sourceLanguage, targetLanguages } = readLanguagesConfig();
  for (const targetLanguage of targetLanguages) {
    if (targetLanguage === sourceLanguage) {
      continue;
    }
    const result = updateMapping(sourceLanguage, targetLanguage);
    console.log(`${result.targetLanguage}: added ${result.added} displayName mappings from ${result.totalPairs} discovered pairs.`);
  }
}

main();
