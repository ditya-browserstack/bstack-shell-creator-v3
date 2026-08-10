import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { validateProductConfig, loadProductConfig, resolveOutputPaths, resolveCoreSource, resolveCaptureConfig } from './config.mjs';

const GOOD = {
  product: 'App Automate',
  designSystem: 'designstack',
  repoPath: '~/projects/app-automate',
  storybookUrl: 'http://localhost:6006',
  liveUrl: 'https://app-automate.browserstack.com/dashboard',
  chrome: { topbar: '.topbar', sidebar: '.sidebar', activeNav: 'Automate' },
  vocabulary: ['build', 'session']
};

test('validateProductConfig accepts a well-formed config', () => {
  const { ok, errors } = validateProductConfig(GOOD);
  assert.equal(ok, true, errors.join('; '));
});

test('validateProductConfig rejects missing required fields', () => {
  const { ok, errors } = validateProductConfig({ product: 'X' });
  assert.equal(ok, false);
  assert.ok(errors.some((e) => /designSystem/.test(e)));
  assert.ok(errors.some((e) => /repoPath/.test(e)));
});

test('validateProductConfig rejects an unknown designSystem', () => {
  const { ok, errors } = validateProductConfig({ ...GOOD, designSystem: 'material' });
  assert.equal(ok, false);
  assert.ok(errors.some((e) => /designSystem/.test(e)));
});

test('loadProductConfig reads and validates from products/<slug>', () => {
  const root = mkdtempSync(join(tmpdir(), 'skill-'));
  mkdirSync(join(root, 'products', 'appauto'), { recursive: true });
  writeFileSync(join(root, 'products', 'appauto', 'product.config.json'), JSON.stringify(GOOD));
  const cfg = loadProductConfig('appauto', { skillRoot: root });
  assert.equal(cfg.product, 'App Automate');
  assert.equal(cfg._slug, 'appauto');
  rmSync(root, { recursive: true, force: true });
});

test('loadProductConfig throws a clear error on invalid config', () => {
  const root = mkdtempSync(join(tmpdir(), 'skill-'));
  mkdirSync(join(root, 'products', 'bad'), { recursive: true });
  writeFileSync(join(root, 'products', 'bad', 'product.config.json'), JSON.stringify({ product: 'B' }));
  assert.throws(() => loadProductConfig('bad', { skillRoot: root }), /designSystem/);
  rmSync(root, { recursive: true, force: true });
});

test('resolveOutputPaths points into products/<slug>/app-shell', () => {
  const p = resolveOutputPaths('appauto', { skillRoot: '/S' });
  assert.equal(p.appShellDir, '/S/products/appauto/app-shell');
  assert.equal(p.sheetHtml, '/S/products/appauto/app-shell/component-sheet.html');
  assert.equal(p.sheetCss, '/S/products/appauto/app-shell/component-sheet.css');
  assert.equal(p.brief, '/S/products/appauto/app-shell/brief-contract.md');
  assert.equal(p.manifest, '/S/products/appauto/app-shell/sheet-manifest.json');
});

test('resolveCoreSource uses shared core for designstack', () => {
  const s = resolveCoreSource(GOOD, { skillRoot: '/S' });
  assert.equal(s.kind, 'designstack');
  assert.equal(s.tierMapPath, '/S/core/designstack-tier-map.json');
  assert.equal(s.storybookUrl, 'http://localhost:6006');
});

test('resolveCoreSource uses the product customSource for custom systems', () => {
  const cfg = { ...GOOD, designSystem: 'custom', customSource: '/repo/storybook', storybookUrl: 'http://localhost:7007' };
  const s = resolveCoreSource(cfg, { skillRoot: '/S' });
  assert.equal(s.kind, 'custom');
  assert.equal(s.tierMapPath, '/repo/storybook');
  assert.equal(s.storybookUrl, 'http://localhost:7007');
});

function writeCfg(obj) {
  const root = mkdtempSync(join(tmpdir(), 'skill-'));
  mkdirSync(join(root, 'products', 'p'), { recursive: true });
  writeFileSync(join(root, 'products', 'p', 'product.config.json'), JSON.stringify(obj));
  return root;
}

test('resolveCaptureConfig marks designstack products as reusesCore + core paths', () => {
  const root = writeCfg(GOOD);
  const c = resolveCaptureConfig('p', { skillRoot: root });
  assert.equal(c.reusesCore, true);
  assert.equal(c.mapPath, join(root, 'core', 'designstack-tier-map.json'));
  assert.equal(c.outHtml, join(root, 'products', 'p', 'app-shell', 'component-sheet.html'));
  assert.equal(c.sheetTitle, 'APP AUTOMATE');
  rmSync(root, { recursive: true, force: true });
});

test('resolveCaptureConfig points custom products at their own source', () => {
  const root = writeCfg({ ...GOOD, designSystem: 'custom', customSource: '/repo/sb.json', storybookUrl: 'http://localhost:7007' });
  const c = resolveCaptureConfig('p', { skillRoot: root });
  assert.equal(c.reusesCore, false);
  assert.equal(c.mapPath, '/repo/sb.json');
  assert.equal(c.storybookUrl, 'http://localhost:7007');
  rmSync(root, { recursive: true, force: true });
});
