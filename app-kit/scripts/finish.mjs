// After the two `vite build`s (kit and studio):
// - kit (v2): copy the catalog next to the bundle and check that every global the kit
//   exposes is documented in it (the prompt reads catalog.md, so they must not drift).
// - studio (v3): the same check for studio.md, which gets the icon names appended; then
//   copy Tailwind's browser build and the embedded fonts (with their licences), which the
//   shell inlines into v3 apps.
import { copyFileSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";

const out = "../backend/app/agent/kit";

function globalsOf(file, marker) {
  const src = readFileSync(file, "utf8");
  const start = src.indexOf(marker);
  const block = src.slice(start, src.indexOf("};", start));
  return [...block.matchAll(/^\s+([A-Za-z]+)[,:]/gm)].map((m) => m[1]).filter((n) => n !== "React");
}

function checkDocumented(doc, names, label) {
  const text = readFileSync(doc, "utf8");
  const missing = names.filter((n) => !new RegExp(`\\b${n}\\b`).test(text));
  if (missing.length) {
    console.error(`${label} does not document: ${missing.join(", ")}`);
    process.exit(1);
  }
}

// kit
copyFileSync("src/catalog.md", `${out}/catalog.md`);
checkDocumented("src/catalog.md", globalsOf("src/index.tsx", "export const KIT = {"), "catalog.md");

// studio
checkDocumented("src/studio.md", globalsOf("src/studio.tsx", "export const STUDIO = {"), "studio.md");
const studio = readFileSync("src/studio.tsx", "utf8");
const iconBlock = studio.slice(studio.indexOf("// ICONS-START"), studio.indexOf("// ICONS-END"));
const kebab = (n) =>
  n.replace(/([a-z])([A-Z0-9])/g, "$1-$2").replace(/([0-9])([A-Z])/g, "$1-$2").toLowerCase();
const icons = [...iconBlock.slice(iconBlock.indexOf("{")).matchAll(/\b([A-Z][A-Za-z0-9]*)\b/g)]
  .map((m) => kebab(m[1]))
  .sort();
writeFileSync(
  `${out}/studio.md`,
  `${readFileSync("src/studio.md", "utf8").trimEnd()}\n\n## Icon names\n\n${icons.join(", ")}\n`,
);

copyFileSync("node_modules/@tailwindcss/browser/dist/index.global.js", `${out}/tailwind.js`);

const fonts = [
  ["@fontsource-variable/inter", "inter-latin-wght-normal.woff2", "inter.woff2"],
  ["@fontsource-variable/space-grotesk", "space-grotesk-latin-wght-normal.woff2", "space-grotesk.woff2"],
  ["@fontsource-variable/fraunces", "fraunces-latin-wght-normal.woff2", "fraunces.woff2"],
  ["@fontsource-variable/jetbrains-mono", "jetbrains-mono-latin-wght-normal.woff2", "jetbrains-mono.woff2"],
  ["@fontsource/instrument-serif", "instrument-serif-latin-400-normal.woff2", "instrument-serif.woff2"],
  ["@fontsource/instrument-serif", "instrument-serif-latin-400-italic.woff2", "instrument-serif-italic.woff2"],
];
mkdirSync(`${out}/fonts`, { recursive: true });
for (const [pkg, file, name] of fonts) {
  copyFileSync(`node_modules/${pkg}/files/${file}`, `${out}/fonts/${name}`);
  copyFileSync(`node_modules/${pkg}/LICENSE`, `${out}/fonts/${pkg.split("/")[1]}.LICENSE`);
}

for (const f of ["kit.js", "kit.css", "catalog.md", "studio.js", "studio.md", "tailwind.js"]) {
  console.log(`${f.padEnd(11)} ${(statSync(`${out}/${f}`).size / 1024).toFixed(0)} KB`);
}
