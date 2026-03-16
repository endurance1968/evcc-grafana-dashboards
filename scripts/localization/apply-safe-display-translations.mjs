import fs from "node:fs";
import path from "node:path";

const repoRoot = process.cwd();
const localizationDir = path.join(repoRoot, "dashboards", "localization");
const configFile = path.join(localizationDir, "languages.json");

const safeStringKeys = new Set([
  "title",
  "description",
  "label",
  "text",
  "content",
  "displayName",
  "emptyMessage",
]);

const safePropertyIds = new Set([
  "displayName",
  "displayNameFromDS",
]);

const aliasRiskyKeys = new Set([
  "refId",
  "expression",
  "query",
  "rawSql",
  "sql",
  "regex",
  "pattern",
  "matcher",
  "options",
  "transformations",
]);

function collectJsonFiles(dirPath) {
  const entries = fs.readdirSync(dirPath, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const fullPath = path.join(dirPath, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectJsonFiles(fullPath));
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith(".json")) {
      files.push(fullPath);
    }
  }
  return files;
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function writeJson(filePath, jsonData) {
  fs.writeFileSync(filePath, `${JSON.stringify(jsonData, null, 2)}\n`, "utf8");
}

function readLanguagesConfig() {
  if (!fs.existsSync(configFile)) {
    return { sourceLanguage: "de", targetLanguages: ["de", "en"] };
  }

  const parsed = readJson(configFile);
  const sourceLanguage = String(parsed.sourceLanguage || "de").trim();
  const configuredTargets = Array.isArray(parsed.targetLanguages)
    ? parsed.targetLanguages.map((x) => String(x).trim()).filter(Boolean)
    : [];

  const targetLanguages = [...new Set(configuredTargets.length ? configuredTargets : [sourceLanguage])];
  if (!targetLanguages.includes(sourceLanguage)) {
    targetLanguages.unshift(sourceLanguage);
  }

  return { sourceLanguage, targetLanguages };
}

function mappingPath(sourceLanguage, targetLanguage) {
  return path.join(localizationDir, `${sourceLanguage}_to_${targetLanguage}.json`);
}

function readMapping(sourceLanguage, targetLanguage) {
  const filePath = mappingPath(sourceLanguage, targetLanguage);
  if (!fs.existsSync(filePath)) {
    return { exact: {}, contains: [] };
  }

  const parsed = readJson(filePath);
  return {
    exact: parsed.exact ?? {},
    contains: Array.isArray(parsed.contains) ? parsed.contains : [],
  };
}

function translateString(input, mapping) {
  if (Object.hasOwn(mapping.exact, input)) {
    return mapping.exact[input];
  }

  let output = input;
  for (const pair of mapping.contains) {
    if (!pair || typeof pair.from !== "string" || typeof pair.to !== "string") {
      continue;
    }
    output = output.split(pair.from).join(pair.to);
  }
  return output;
}

function isSamePath(pathA, pathB) {
  if (pathA.length !== pathB.length) {
    return false;
  }

  for (let i = 0; i < pathA.length; i += 1) {
    if (pathA[i] !== pathB[i]) {
      return false;
    }
  }

  return true;
}

function stringMentionsAlias(value, alias) {
  if (value === alias) {
    return true;
  }

  if (value.includes(`$${alias}`)) {
    return true;
  }

  if (alias.length >= 4 && value.includes(alias)) {
    return true;
  }

  return false;
}

function valueMentionsAlias(value, alias) {
  if (typeof value === "string") {
    return stringMentionsAlias(value, alias);
  }

  if (Array.isArray(value)) {
    return value.some((item) => valueMentionsAlias(item, alias));
  }

  if (value && typeof value === "object") {
    return Object.values(value).some((item) => valueMentionsAlias(item, alias));
  }

  return false;
}

function hasUnsafeAliasReference(node, alias, skipPath, currentPath = []) {
  if (Array.isArray(node)) {
    for (let i = 0; i < node.length; i += 1) {
      if (hasUnsafeAliasReference(node[i], alias, skipPath, [...currentPath, i])) {
        return true;
      }
    }
    return false;
  }

  if (!node || typeof node !== "object") {
    return false;
  }

  for (const [key, value] of Object.entries(node)) {
    const childPath = [...currentPath, key];
    if (isSamePath(childPath, skipPath)) {
      continue;
    }

    if (aliasRiskyKeys.has(key) && valueMentionsAlias(value, alias)) {
      return true;
    }

    if (hasUnsafeAliasReference(value, alias, skipPath, childPath)) {
      return true;
    }
  }

  return false;
}

function canTranslateAlias(panelNode, targetIndex, alias) {
  const aliasPath = ["targets", targetIndex, "alias"];
  return !hasUnsafeAliasReference(panelNode, alias, aliasPath);
}

function translateSafeNode(node, mapping) {
  if (Array.isArray(node)) {
    return node.map((item) => translateSafeNode(item, mapping));
  }

  if (!node || typeof node !== "object") {
    return node;
  }

  const result = {};
  for (const [childKey, childValue] of Object.entries(node)) {
    if (typeof childValue === "string" && safeStringKeys.has(childKey)) {
      result[childKey] = translateString(childValue, mapping);
      continue;
    }

    if (
      childKey === "value" &&
      typeof childValue === "string" &&
      typeof node.id === "string" &&
      safePropertyIds.has(node.id)
    ) {
      result[childKey] = translateString(childValue, mapping);
      continue;
    }

    if (childKey === "targets" && Array.isArray(childValue)) {
      result[childKey] = childValue.map((target, targetIndex) => {
        const translatedTarget = translateSafeNode(target, mapping);
        if (!target || typeof target !== "object" || typeof target.alias !== "string") {
          return translatedTarget;
        }

        const translatedAlias = translateString(target.alias, mapping);
        if (translatedAlias === target.alias) {
          return translatedTarget;
        }

        if (!canTranslateAlias(node, targetIndex, target.alias)) {
          return translatedTarget;
        }

        return {
          ...translatedTarget,
          alias: translatedAlias,
        };
      });
      continue;
    }

    result[childKey] = translateSafeNode(childValue, mapping);
  }
  return result;
}

function main() {
  const { sourceLanguage, targetLanguages } = readLanguagesConfig();
  let totalFiles = 0;

  for (const targetLanguage of targetLanguages) {
    if (targetLanguage === sourceLanguage) {
      continue;
    }

    const targetDir = path.join(repoRoot, "dashboards", "translation", targetLanguage);
    if (!fs.existsSync(targetDir)) {
      console.warn(`Skipping missing translation directory: ${path.relative(repoRoot, targetDir)}`);
      continue;
    }

    const mapping = readMapping(sourceLanguage, targetLanguage);
    const files = collectJsonFiles(targetDir);

    for (const filePath of files) {
      const sourceJson = readJson(filePath);
      const translatedJson = translateSafeNode(sourceJson, mapping);
      writeJson(filePath, translatedJson);
      totalFiles += 1;
    }

    console.log(`Applied safe display-only translations to ${files.length} dashboard files for '${targetLanguage}'.`);
  }

  console.log(`Processed ${totalFiles} generated dashboard files in total.`);
}

main();
