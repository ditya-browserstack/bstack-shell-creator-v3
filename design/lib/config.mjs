import { readFileSync } from 'node:fs';
import { join } from 'node:path';

// Minimal schema-aware validator — no external deps. Mirrors product-config.schema.json.
export function validateProductConfig(obj) {
  const errors = [];
  const req = ['product', 'designSystem', 'repoPath', 'chrome'];
  for (const k of req) if (obj?.[k] === undefined) errors.push(`missing required field: ${k}`);
  if (obj?.designSystem && !['designstack', 'custom'].includes(obj.designSystem))
    errors.push(`designSystem must be "designstack" or "custom", got "${obj.designSystem}"`);
  if (obj?.chrome && obj.chrome.activeNav === undefined)
    errors.push('missing required field: chrome.activeNav');
  if (obj?.designSystem === 'custom' && !obj?.customSource)
    errors.push('designSystem "custom" requires customSource (path to the product\'s own tier map)');
  return { ok: errors.length === 0, errors };
}

export function loadProductConfig(slug, { skillRoot }) {
  const path = join(skillRoot, 'products', slug, 'product.config.json');
  const obj = JSON.parse(readFileSync(path, 'utf8'));
  const { ok, errors } = validateProductConfig(obj);
  if (!ok) throw new Error(`Invalid ${path}:\n  - ${errors.join('\n  - ')}`);
  return { ...obj, _slug: slug };
}

export function resolveOutputPaths(slug, { skillRoot }) {
  const appShellDir = join(skillRoot, 'products', slug, 'app-shell');
  return {
    appShellDir,
    sheetHtml: join(appShellDir, 'component-sheet.html'),
    sheetCss: join(appShellDir, 'component-sheet.css'),
    brief: join(appShellDir, 'brief-contract.md'),
    manifest: join(appShellDir, 'sheet-manifest.json')
  };
}

export function resolveCoreSource(config, { skillRoot }) {
  if (config.designSystem === 'custom') {
    return { kind: 'custom', tierMapPath: config.customSource, storybookUrl: config.storybookUrl };
  }
  return {
    kind: 'designstack',
    tierMapPath: join(skillRoot, 'core', 'designstack-tier-map.json'),
    storybookUrl: config.storybookUrl || 'http://localhost:6006'
  };
}

// One call that turns a product slug into everything the capture script needs. This is the
// wiring that makes `--product <slug>` drive the pipeline instead of hand-passing paths.
export function resolveCaptureConfig(slug, { skillRoot }) {
  const cfg = loadProductConfig(slug, { skillRoot });
  const out = resolveOutputPaths(slug, { skillRoot });
  const core = resolveCoreSource(cfg, { skillRoot });
  return {
    slug,
    designSystem: cfg.designSystem,
    reusesCore: cfg.designSystem === 'designstack', // designstack products copy the core, not recapture
    coreSheet: join(skillRoot, 'core', 'designstack-sheet.html'),
    mapPath: core.tierMapPath,
    storybookUrl: core.storybookUrl,
    outHtml: out.sheetHtml,
    outCss: out.sheetHtml.replace(/\.html$/, '.css'),
    manifestPath: out.manifest,
    appShellDir: out.appShellDir,
    sheetTitle: (cfg.product || slug).toUpperCase()
  };
}
