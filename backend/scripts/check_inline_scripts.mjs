#!/usr/bin/env node
/** Compile every inline browser script so generated tenant pages cannot ship syntax errors. */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const roots = [
  path.join(projectRoot, 'super-admin.html'),
  path.join(projectRoot, 'tenant-template'),
  path.join(projectRoot, 'tenants'),
  path.join(projectRoot, 'legacy-root'),
  path.join(projectRoot, 'backend', 'frontend'),
];

function htmlFiles(target) {
  if (!fs.existsSync(target)) return [];
  const stat = fs.statSync(target);
  if (stat.isFile()) return target.endsWith('.html') ? [target] : [];
  return fs.readdirSync(target, { withFileTypes: true }).flatMap((entry) =>
    htmlFiles(path.join(target, entry.name))
  );
}

const failures = [];
for (const file of roots.flatMap(htmlFiles)) {
  const source = fs.readFileSync(file, 'utf8');
  const scriptPattern = /<script\b([^>]*)>([\s\S]*?)<\/script>/gi;
  let match;
  let index = 0;
  while ((match = scriptPattern.exec(source)) !== null) {
    index += 1;
    const attrs = match[1] || '';
    const code = match[2] || '';
    if (/\bsrc\s*=/.test(attrs) || /type\s*=\s*["'](?:application\/(?:json|ld\+json)|importmap)["']/.test(attrs) || !code.trim()) continue;
    try {
      const compilable = code
        .replaceAll('{{TENANT_NAME_JSON}}', '"Demo Studio"')
        .replaceAll('{{TENANT_SLUG}}', 'demo-studio')
        .replaceAll('{{TENANT_NAME}}', 'Demo Studio');
      new Function(compilable);
    } catch (error) {
      failures.push(`${path.relative(projectRoot, file)} inline script ${index}: ${error.message}`);
    }
  }
}

if (failures.length) {
  console.error('Inline script syntax failures:');
  failures.forEach((failure) => console.error(`  ${failure}`));
  process.exit(1);
}
console.log('inline-script check: OK');
