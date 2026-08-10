import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { resolveCaptureOptions } from './options.mjs';

const base = { skillRoot: '/S', cwd: '/cwd' };

test('--core selects the shared DesignStack tier map and core outputs', () => {
  const o = resolveCaptureOptions(['--core'], base);
  assert.equal(o.mapPath, '/S/core/designstack-tier-map.json');
  assert.equal(o.outHtml, '/S/core/designstack-sheet.html');
  assert.equal(o.outCss, '/S/core/designstack-sheet.css');
  assert.equal(o.manifestPath, '/S/core/core-manifest.json');
  assert.equal(o.sheetTitle, 'DESIGNSTACK');
});

test('--dry-run sets dry and defaults to core when nothing else given', () => {
  const o = resolveCaptureOptions(['--dry-run', '--core'], base);
  assert.equal(o.dry, true);
});

test('--tier N is parsed to a number', () => {
  const o = resolveCaptureOptions(['--core', '--tier', '2'], base);
  assert.equal(o.onlyTier, 2);
});

test('explicit overrides win over defaults', () => {
  const o = resolveCaptureOptions(
    ['--core', '--url', 'http://localhost:7000', '--out', '/tmp/x.html', '--map', '/tmp/m.json'],
    base
  );
  assert.equal(o.base, 'http://localhost:7000');
  assert.equal(o.outHtml, '/tmp/x.html');
  assert.equal(o.outCss, '/tmp/x.css');
  assert.equal(o.mapPath, '/tmp/m.json');
});

test('trailing slash is stripped from the base url', () => {
  const o = resolveCaptureOptions(['--core', '--url', 'http://localhost:6006/'], base);
  assert.equal(o.base, 'http://localhost:6006');
});

test('--product for a designstack product resolves reusesCore + config paths', () => {
  const root = mkdtempSync(join(tmpdir(), 'skill-'));
  mkdirSync(join(root, 'products', 'appauto'), { recursive: true });
  writeFileSync(join(root, 'products', 'appauto', 'product.config.json'), JSON.stringify({
    product: 'App Automate', designSystem: 'designstack', repoPath: '~/x',
    storybookUrl: 'http://localhost:6006', chrome: { activeNav: 'Automate' }
  }));
  const o = resolveCaptureOptions(['--product', 'appauto'], { skillRoot: root });
  assert.equal(o.reusesCore, true);
  assert.equal(o.productSlug, 'appauto');
  assert.equal(o.outHtml, join(root, 'products', 'appauto', 'app-shell', 'component-sheet.html'));
  rmSync(root, { recursive: true, force: true });
});

test('--product for a custom product points at its own source + storybook', () => {
  const root = mkdtempSync(join(tmpdir(), 'skill-'));
  mkdirSync(join(root, 'products', 'cust'), { recursive: true });
  writeFileSync(join(root, 'products', 'cust', 'product.config.json'), JSON.stringify({
    product: 'Cust', designSystem: 'custom', customSource: '/repo/sb.json', repoPath: '~/x',
    storybookUrl: 'http://localhost:7007', chrome: { activeNav: 'Home' }
  }));
  const o = resolveCaptureOptions(['--product', 'cust'], { skillRoot: root });
  assert.equal(o.reusesCore, false);
  assert.equal(o.mapPath, '/repo/sb.json');
  assert.equal(o.base, 'http://localhost:7007');
  rmSync(root, { recursive: true, force: true });
});
