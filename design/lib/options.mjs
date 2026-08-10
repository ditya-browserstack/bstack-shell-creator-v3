import { join } from 'node:path';
import { resolveCaptureConfig } from './config.mjs';

const flag = (argv, n) => argv.includes(n);
const opt = (argv, n, d) => {
  const i = argv.indexOf(n);
  return i !== -1 && argv[i + 1] ? argv[i + 1] : d;
};

// Resolve everything the capture script needs.
//   --core            → build/refresh the shared DesignStack core.
//   --product <slug>  → drive from products/<slug>/product.config.json (custom design systems).
//   --map/--out/...   → explicit overrides (still win over both).
export function resolveCaptureOptions(argv, { skillRoot }) {
  const core = flag(argv, '--core');
  const productSlug = opt(argv, '--product');

  // config-driven defaults for a product (custom design system capture)
  let cfg = null;
  if (productSlug) cfg = resolveCaptureConfig(productSlug, { skillRoot });

  const mapDefault = core
    ? join(skillRoot, 'core', 'designstack-tier-map.json')
    : cfg
    ? cfg.mapPath
    : undefined;
  const outDefault = core
    ? join(skillRoot, 'core', 'designstack-sheet.html')
    : cfg
    ? cfg.outHtml
    : undefined;
  const manDefault = core
    ? join(skillRoot, 'core', 'core-manifest.json')
    : cfg
    ? cfg.manifestPath
    : undefined;

  const outHtml = opt(argv, '--out', outDefault);
  const mapPath = opt(argv, '--map', mapDefault);
  const base = (opt(argv, '--url', cfg ? cfg.storybookUrl : '') || '').replace(/\/$/, '');
  const tierArg = opt(argv, '--tier');

  return {
    dry: flag(argv, '--dry-run'),
    onlyTier: tierArg ? Number(tierArg) : null,
    mapPath,
    base,
    outHtml,
    outCss: outHtml ? outHtml.replace(/\.html$/, '.css') : undefined,
    manifestPath: opt(argv, '--manifest', manDefault),
    dsPkgPath: opt(argv, '--ds-pkg'),
    sheetTitle: opt(argv, '--title', core ? 'DESIGNSTACK' : cfg ? cfg.sheetTitle : 'COMPONENT'),
    // set when --product points at a designstack product: it should reuse the core, not recapture
    reusesCore: cfg ? cfg.reusesCore : false,
    productSlug: productSlug || null,
    coreSheet: cfg ? cfg.coreSheet : join(skillRoot, 'core', 'designstack-sheet.html'),
    tierNames: {
      1: 'CHROME AND LAYOUT', 2: 'THE TABLE STACK', 3: 'CONTROLS',
      4: 'SURFACES', 5: 'STATES', 6: 'PRODUCT COMPOSITES'
    }
  };
}
