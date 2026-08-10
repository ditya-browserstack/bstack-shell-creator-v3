#!/usr/bin/env python3
"""Build a searchable feature index from the shell's template source.

The shell is a Claude Design page written in the x-dc DSL, not React. Its
product surface is largely data: catalog() returns command groups, and the
`screen` state key enumerates the screens. Indexing that text is a
deterministic way to answer "does the shell already have this feature?".
"""
import json
import re
import sys
from pathlib import Path

CATALOG_GROUP_RE = re.compile(r"\{\s*name:\s*'([^']+)'\s*,\s*items:")
LABEL_RE = re.compile(r"\blabel:\s*'((?:[^'\\]|\\.)*)'")
SCREEN_RE = re.compile(r"screen\s*===?\s*'([^']+)'")
STATE_START_RE = re.compile(r"\bstate\s*=\s*\{")
SETSTATE_KEY_RE = re.compile(r"setState\(\s*\{\s*([A-Za-z_]\w*)\s*:")
TOP_KEY_RE = re.compile(r"([A-Za-z_]\w*)\s*:")
METHOD_RE = re.compile(r"^\s{2}([A-Za-z_]\w*)\s*\([^)]*\)\s*\{", re.M)
MARKUP_TEXT_RE = re.compile(r">([^<>{}]+)<")

# The logic script is full of comparison operators, so scanning it for ">text<"
# harvests JavaScript fragments as if they were UI labels. Strip script blocks
# before extracting markup text. State and method extraction still read the full
# template, since that is where the logic lives.
SCRIPT_BLOCK_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.S)

# Icon glyph names are text nodes too, but they are not feature labels: the shell
# renders them as <span class="icon">close</span>. Left in, they make a feature
# called "add" or "home" look like it already exists.
#
# Collected and filtered by exact match rather than substituted out. Substituting
# breaks text adjacency: an icon immediately before a label, as in
# <span class="icon">check</span>Complete test, loses the label entirely.
ICON_TEXT_RE = re.compile(r'<span[^>]*class="icon"[^>]*>([^<]*)</span>')
PUNCT_RE = re.compile(r"[^\w\s]")
SPACE_RE = re.compile(r"\s+")

MIN_LABEL_LEN = 2


def normalize(text):
    """Lowercase, strip punctuation, collapse whitespace."""
    return SPACE_RE.sub(" ", PUNCT_RE.sub("", text)).strip().lower()


def _dedupe(items):
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _state_block(template):
    """Return the source of the `state = { ... }` initializer, or "".

    Brace-balanced rather than regex-delimited, because shells write this both
    as a multi-line block and as a single line:
        state = { hover: null, px: 300, screen: 'home' };
    A regex anchored on a closing "\\n  };" silently returns nothing for the
    single-line form, which then yields an empty state_keys list.
    """
    match = STATE_START_RE.search(template)
    if not match:
        return ""
    start = match.end()  # just past the opening brace
    depth = 1
    quote = None
    index_ = start
    while index_ < len(template) and depth > 0:
        char = template[index_]
        if quote:
            if char == "\\":
                index_ += 2
                continue
            if char == quote:
                quote = None
        elif char in "\"'`":
            quote = char
        elif char in "{[(":
            depth += 1
        elif char in "}])":
            depth -= 1
        index_ += 1
    return template[start:index_ - 1]


def _top_level_keys(block):
    """Keys at nesting depth 0 of an object-literal body."""
    keys = []
    depth = 0
    quote = None
    segment_start = 0
    for position, char in enumerate(block):
        if quote:
            if char == "\\":
                continue
            if char == quote:
                quote = None
            continue
        if char in "\"'`":
            quote = char
        elif char in "{[(":
            depth += 1
        elif char in "}])":
            depth -= 1
        elif char == "," and depth == 0:
            found = TOP_KEY_RE.match(block[segment_start:position].strip())
            if found:
                keys.append(found.group(1))
            segment_start = position + 1
    found = TOP_KEY_RE.match(block[segment_start:].strip())
    if found:
        keys.append(found.group(1))
    return keys


def build(template):
    """Parse template source into a feature index.

    Shells differ in shape. The Prototype-style export puts its product surface in
    a catalog() array of labelled commands; the fuller session shell has no catalog
    at all and expresses everything as markup text. Every extractor below therefore
    degrades to an empty list rather than failing, and callers should expect
    markup_labels to be the primary signal when catalog_labels is empty.
    """
    # Initial state plus anything introduced later via setState.
    state_keys = _top_level_keys(_state_block(template))
    state_keys += SETSTATE_KEY_RE.findall(template)

    markup = SCRIPT_BLOCK_RE.sub("", template)
    icon_names = set(name.strip() for name in ICON_TEXT_RE.findall(markup))

    markup_labels = []
    for chunk in MARKUP_TEXT_RE.findall(markup):
        text = chunk.strip()
        if len(text) < MIN_LABEL_LEN or text.startswith("{{"):
            continue
        if text in icon_names:
            continue
        markup_labels.append(text)

    return {
        "catalog_groups": _dedupe(CATALOG_GROUP_RE.findall(template)),
        "catalog_labels": _dedupe(LABEL_RE.findall(template)),
        "screens": _dedupe(SCREEN_RE.findall(template)),
        "state_keys": _dedupe(state_keys),
        "methods": _dedupe(METHOD_RE.findall(template)),
        "markup_labels": _dedupe(markup_labels),
    }


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import paths

    template = (paths.SHELL_DIR / "template.html").read_text(encoding="utf-8")
    print(json.dumps(build(template), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
