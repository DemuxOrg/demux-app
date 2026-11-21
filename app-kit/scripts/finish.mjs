// After `vite build`: copy the catalog next to the bundle and check that every global the
// kit exposes is documented in it (the prompt reads catalog.md, so they must not drift).
import { copyFileSync, readFileSync, statSync } from "node:fs";

const out = "../backend/app/agent/kit";
copyFileSync("src/catalog.md", `${out}/catalog.md`);

const catalog = readFileSync("src/catalog.md", "utf8");
const index = readFileSync("src/index.tsx", "utf8");
const block = index.slice(index.indexOf("export const KIT = {"), index.indexOf("};", index.indexOf("export const KIT = {")));
const names = [...block.matchAll(/^\s+([A-Za-z]+)[,:]/gm)].map((m) => m[1]).filter((n) => n !== "React");
const missing = names.filter((n) => !new RegExp(`\\b${n}\\b`).test(catalog));
if (missing.length) {
  console.error(`catalog.md does not document: ${missing.join(", ")}`);
  process.exit(1);
}
for (const f of ["kit.js", "kit.css", "catalog.md"]) {
  console.log(`${f.padEnd(11)} ${(statSync(`${out}/${f}`).size / 1024).toFixed(0)} KB`);
}
