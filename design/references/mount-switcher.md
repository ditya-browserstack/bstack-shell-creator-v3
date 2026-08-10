# Mounting explorations in the real shell (one tab + variation switcher)

USE mode produces **one `explorations.html`** — the product's real app shell (`app-shell/shell-scaffold.html`) with the variations mounted as **panels** and a **floating bottom-right toggle** to switch between them. Not N separate files. This is the reviewer-facing deliverable.

Why this shape:
- **One shell, panels swap.** The chrome (nav · sidebar · page/recorder row) is identical across variations, so it stays fixed; only the `<main>` slot changes. Reviewers compare without losing context or juggling tabs.
- **Isolated iframe per panel.** The panel loads in an iframe so its DesignStack CSS can't fight the shell's compiled CSS (that collision is what produced duplicate-nav / sidebar-overlap when panels were injected natively). Chrome stays pristine.
- **Auto-height, not fixed height.** The panel reports its height to the shell so the iframe grows with content and live-resizes when a warning/modal appears. A fixed height crops on large screens and leaves dead space.
- **Recorder-width container.** The iframe sits in the *same* max-width container the product's content uses (LCA: `max-width:1424px; margin:0 auto`), so the panel aligns with the surface above it at every width. (Wide side-margins on large screens are correct — the real app centers content too.)

## Files USE writes
```
<feature>/design/
├── explorations.html        # the shell + switcher (below)
├── panel-1.html …panel-N.html  # one per variation: the SOLUTION BODY only, links component-sheet.css, + resize snippet
```

## Panel file (`panel-N.html`)
The variation's content **only** (no chrome — the shell provides it). It links the product's component sheet and ends with this resize reporter so the shell can auto-fit it:

```html
<script>new ResizeObserver(()=>{try{parent.postMessage({__ph:document.documentElement.scrollHeight},'*')}catch(e){}}).observe(document.documentElement);</script>
```
Set the panel's content wrapper to the surface width (LCA: `max-width:1424px;margin:0 auto;padding:24px`) so it fills the shell container.

## Shell slot (replace the `<main class="lca-main-slot">…</main>` in `shell-scaffold.html`)
```html
<main class="lca-main-slot" style="padding:8px 0 64px">
  <div style="max-width:1424px;margin:0 auto;padding:0 24px">
    <iframe id="flagsFrame" src="./panel-1.html" style="width:100%;border:0;display:block;min-height:520px"></iframe>
  </div>
  <div id="varSwitch" style="position:fixed;right:20px;bottom:20px;z-index:2147483647;display:flex;align-items:center;gap:8px;background:#fff;border:1px solid #d1d5db;border-radius:9999px;box-shadow:0 6px 24px rgba(15,23,42,.18);padding:6px;font:600 12px/1 system-ui,sans-serif">
    <span style="padding:0 6px 0 10px;color:#6b7280;text-transform:uppercase;letter-spacing:.04em;font-size:10px">Variation</span>
    <button data-p="./panel-1.html" style="border:0;cursor:pointer;padding:8px 12px;border-radius:9999px;background:#2563eb;color:#fff">1 · <name></button>
    <button data-p="./panel-2.html" style="border:0;cursor:pointer;padding:8px 12px;border-radius:9999px;background:transparent;color:#374151">2 · <name></button>
    <!-- one button per variation -->
  </div>
  <script>
    var __f=document.getElementById('flagsFrame');
    window.addEventListener('message',function(e){if(e.data&&e.data.__ph){__f.style.height=e.data.__ph+'px';}});
    __f.addEventListener('load',function(){try{__f.style.height=__f.contentDocument.documentElement.scrollHeight+'px';}catch(x){}});
    var sw=document.getElementById('varSwitch');
    sw.addEventListener('click',function(e){var b=e.target.closest('button[data-p]');if(!b)return;
      __f.style.minHeight='520px';__f.src=b.getAttribute('data-p');
      [].forEach.call(sw.querySelectorAll('button'),function(x){x.style.background='transparent';x.style.color='#374151';});
      b.style.background='#2563eb';b.style.color='#fff';});
  </script>
</main>
```

The switcher is **review furniture**, not a product component — hand-styled neutrals are fine, and it must never be copied into a shipped design. Everything inside the panels stays real DesignStack.

## Verify before handing over
Render `explorations.html` at a **large width (2560)** and a normal one (1440): the panel must align under the surface with **no crop and no dead grey band**, and each toggle must swap the panel (check the iframe `src` changes and the active button highlights). If a panel has a modal, confirm it centres over the panel area.
