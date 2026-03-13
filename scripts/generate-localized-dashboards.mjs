import fs from "node:fs";
import path from "node:path";

const repoRoot = process.cwd();
const sourceDir = path.join(repoRoot, "dashboards", "src", "de");
const outDeDir = path.join(repoRoot, "dashboards", "de");
const outEnDir = path.join(repoRoot, "dashboards", "en");
const mappingFile = path.join(repoRoot, "dashboards", "localization", "de_to_en.json");

const translatableKeys = new Set([
    "title",
    "description",
    "label",
    "name",
    "text",
    "content",
    "displayName",
    "legendFormat",
    "emptyMessage",
]);

function ensureDir(dirPath) {
    fs.mkdirSync(dirPath, { recursive: true });
}

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

function readMapping() {
    if (!fs.existsSync(mappingFile)) {
        return { exact: {}, contains: [] };
    }

    const raw = fs.readFileSync(mappingFile, "utf8");
    const parsed = JSON.parse(raw);
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

function translateJsonNode(node, mapping) {
    if (Array.isArray(node)) {
        return node.map((item) => translateJsonNode(item, mapping));
    }

    if (node && typeof node === "object") {
        const result = {};
        for (const [key, value] of Object.entries(node)) {
            const isSafeName =
                key !== "name" || (typeof value === "string" && value.startsWith("EVCC:"));
            if (typeof value === "string" && translatableKeys.has(key) && isSafeName) {
                result[key] = translateString(value, mapping);
            } else {
                result[key] = translateJsonNode(value, mapping);
            }
        }
        return result;
    }

    return node;
}

function writeJson(filePath, jsonData) {
    const content = `${JSON.stringify(jsonData, null, 2)}\n`;
    fs.writeFileSync(filePath, content, "utf8");
}

function main() {
    if (!fs.existsSync(sourceDir)) {
        throw new Error(`Source directory does not exist: ${sourceDir}`);
    }

    ensureDir(outDeDir);
    ensureDir(outEnDir);

    const mapping = readMapping();
    const files = collectJsonFiles(sourceDir);

    let count = 0;
    for (const sourceFile of files) {
        const relative = path.relative(sourceDir, sourceFile);
        const targetDe = path.join(outDeDir, relative);
        const targetEn = path.join(outEnDir, relative);

        ensureDir(path.dirname(targetDe));
        ensureDir(path.dirname(targetEn));

        const deJson = JSON.parse(fs.readFileSync(sourceFile, "utf8"));
        const enJson = translateJsonNode(deJson, mapping);

        writeJson(targetDe, deJson);
        writeJson(targetEn, enJson);
        count += 1;
    }

    console.log(`Generated ${count} dashboard files.`);
    console.log(`DE output: ${path.relative(repoRoot, outDeDir)}`);
    console.log(`EN output: ${path.relative(repoRoot, outEnDir)}`);
}

main();
