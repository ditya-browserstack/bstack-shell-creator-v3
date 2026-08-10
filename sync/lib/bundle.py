#!/usr/bin/env python3
"""Unpack and pack Claude Design bundled HTML exports.

A bundled export embeds the whole app as a JSON-encoded string inside a
<script type="__bundler/template"> element. Inside that JSON every closing-tag
slash is unicode-escaped so the host <script> is not terminated early.

Two rules are load-bearing and were both verified empirically against the real
a Claude Design shell:
  1. json.dumps must use ensure_ascii=False. The default escapes the em dash in
     the shell's CSS header and breaks byte identity.
  2. Only closing-tag slashes are escaped. The shell's CSS comments contain bare
     slashes that must stay bare.
"""
import json
import re
import sys
from pathlib import Path

# Built programmatically on purpose. Never write this escape literally: editors,
# heredocs and doc tooling interpret it and silently emit a bare slash, which
# terminates the host <script> and blanks the packed page.
SLASH_ESC = chr(92) + "u002F"

SENTINEL = "__DC_TEMPLATE_JSON__"

TEMPLATE_RE = re.compile(
    r'(<script type="__bundler/template">)(\s*)(.*?)(\s*)(</script>)', re.S
)

HOST_NAME = "host.html"
TEMPLATE_NAME = "template.html"


class BundleError(Exception):
    """Raised when the input is not a well-formed bundled export."""


def unpack(html):
    """Split bundled HTML into (host, template).

    host keeps the manifest byte-for-byte, with the template JSON replaced by
    SENTINEL. template is the decoded app source.
    """
    if SENTINEL in html:
        raise BundleError("input already contains sentinel %s" % SENTINEL)
    found = TEMPLATE_RE.findall(html)
    if len(found) != 1:
        raise BundleError(
            "expected exactly 1 __bundler/template script, found %d" % len(found)
        )
    match = TEMPLATE_RE.search(html)
    open_tag, lead, core, trail, close_tag = match.groups()
    try:
        template = json.loads(core)
    except ValueError as exc:
        raise BundleError("template region is not valid JSON: %s" % exc)
    if not isinstance(template, str):
        raise BundleError("template JSON decoded to %s, expected str" % type(template))
    host = (
        html[: match.start()]
        + open_tag
        + lead
        + SENTINEL
        + trail
        + close_tag
        + html[match.end():]
    )
    return host, template


def pack(host, template):
    """Reassemble a single-file HTML from host + template source."""
    if SENTINEL not in host:
        raise BundleError("host is missing sentinel %s" % SENTINEL)
    encoded = json.dumps(template, ensure_ascii=False).replace("</", "<" + SLASH_ESC)
    return host.replace(SENTINEL, encoded)


def _cmd_unpack(in_html, shell_dir):
    src = Path(in_html).read_text(encoding="utf-8")
    host, template = unpack(src)
    out = Path(shell_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / HOST_NAME).write_text(host, encoding="utf-8")
    (out / TEMPLATE_NAME).write_text(template, encoding="utf-8")
    # Fail loudly here rather than at feature-coding time.
    if pack(host, template) != src:
        raise BundleError("identity round-trip failed for %s" % in_html)
    print("unpacked %s -> %s (host %.1f MB, template %.1f KB), identity verified"
          % (in_html, shell_dir, len(host) / 1e6, len(template) / 1e3))


def _cmd_pack(shell_dir, out_html):
    src = Path(shell_dir)
    host = (src / HOST_NAME).read_text(encoding="utf-8")
    template = (src / TEMPLATE_NAME).read_text(encoding="utf-8")
    Path(out_html).write_text(pack(host, template), encoding="utf-8")
    print("packed %s -> %s" % (shell_dir, out_html))


def main(argv):
    if len(argv) != 4 or argv[1] not in ("unpack", "pack"):
        print("usage: bundle.py unpack <in.html> <shell_dir>", file=sys.stderr)
        print("       bundle.py pack <shell_dir> <out.html>", file=sys.stderr)
        return 2
    try:
        if argv[1] == "unpack":
            _cmd_unpack(argv[2], argv[3])
        else:
            _cmd_pack(argv[2], argv[3])
    except BundleError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
