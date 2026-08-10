#!/usr/bin/env python3
"""Decide whether a shipped feature already exists in the shell.

Structural matching against the shell's own text, not a screenshot diff: a
vision diff between a lo-fi shell and the real product flags everything as
different and cannot answer presence reliably.

UNCERTAIN is a deliberate third outcome. Genuine near-misses go to the agent for
adjudication rather than being guessed at by a similarity threshold.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import index  # noqa: E402

PRESENT = "PRESENT"
MISSING = "MISSING"
UNCERTAIN = "UNCERTAIN"

SEARCH_KEYS = ("catalog_labels", "markup_labels", "catalog_groups", "screens")

# A feature name often arrives with its ticket id still attached ("LCAM-2580
# Service accounts"). Left in place it fails every exact match, so it is stripped
# before comparing. Which prefix to strip is per-product, so this is built from
# config rather than fixed -- a hardcoded prefix would simply stop stripping for
# the next product, and the symptom would be a gap report full of false MISSING.
#
# \d{1,5}, not \d{2,5}: real ids start in the low hundreds, and a stricter bound
# silently leaves the prefix in place.
def ticket_prefix_re(prefix):
    if not prefix:
        # Nothing to strip is a valid state -- match nothing rather than everything.
        return re.compile(r"(?!)")
    return re.compile(r"^\s*%s[\s_-]*\d{1,5}[:\s]*" % re.escape(prefix), re.I)


def _configured_prefix_re():
    """The stripper for the active profile, resolved once per process."""
    global _PREFIX_RE
    if _PREFIX_RE is None:
        import paths

        try:
            prefix = paths.load_config().get("ticket_prefix") or ""
        except (OSError, ValueError):
            prefix = ""
        _PREFIX_RE = ticket_prefix_re(prefix)
    return _PREFIX_RE


_PREFIX_RE = None

# Tuned so "Swipe up on element" vs "Swipe up" lands in UNCERTAIN while
# "Service accounts" vs everything in the shell stays MISSING.
UNCERTAIN_MIN_OVERLAP = 0.5

STOPWORDS = frozenset(["a", "an", "the", "on", "in", "to", "of", "for", "and"])


def _singular(word):
    """Crude plural folding so "accounts" and "account" compare equal."""
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _tokens(text):
    return [
        _singular(word)
        for word in index.normalize(text).split()
        if word not in STOPWORDS
    ]


def _overlap(left, right):
    """Jaccard similarity: intersection over union.

    Deliberately NOT intersection over min(). With min() in the denominator, a
    one-token index entry such as "Create" scores a perfect 1.0 against any
    feature name containing "create" -- and the session shell has 375 labels,
    many of them single words, so that produced UNCERTAIN for 10 of 17 real
    candidates. Union in the denominator makes a match earn its score against
    the length of both strings.
    """
    left_set, right_set = set(left), set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / float(len(left_set | right_set))


def _contained(feature_tokens, entry_tokens):
    """Whether a shell label sits wholly inside a feature name, or vice versa.

    Jaccard alone under-scores a correct match when the feature is named more
    verbosely than the label it refers to. Against the real shell:

        "Ran with"                    -> PRESENT   (exact)
        "Ran with column"             -> UNCERTAIN (0.67)
        "Builds list Ran with column" -> MISSING   (0.40) -- but the evidence line
                                                   itself named RAN WITH

    That last one is the dangerous direction: MISSING goes straight into the gap
    report as work to do, while UNCERTAIN forces adjudication. Containment catches
    it.

    The two-token floor matters. Without it a one-word label such as "Create"
    sits inside almost every feature name and escalates everything -- which is
    the same flood of false UNCERTAINs that switching to Jaccard-over-union fixed
    in the first place.
    """
    small, large = sorted((set(feature_tokens), set(entry_tokens)), key=len)
    return len(small) >= 2 and small.issubset(large)


def classify(feature_name, idx, prefix_re=None):
    """Return {"verdict", "evidence", "score"} for one feature name."""
    cleaned = (prefix_re or _configured_prefix_re()).sub("", feature_name or "")
    normalized = index.normalize(cleaned)
    if not normalized:
        return {"verdict": UNCERTAIN, "evidence": "empty feature name", "score": 0.0}

    feature_tokens = _tokens(cleaned)
    best_entry = None
    best_score = 0.0
    contained_entry = None
    for key in SEARCH_KEYS:
        for entry in idx.get(key, []):
            if index.normalize(entry) == normalized:
                return {
                    "verdict": PRESENT,
                    "evidence": "exact match on %s: %s" % (key, entry),
                    "score": 1.0,
                }
            entry_tokens = _tokens(entry)
            score = _overlap(feature_tokens, entry_tokens)
            if score > best_score:
                best_score = score
                best_entry = "%s: %s" % (key, entry)
            if contained_entry is None and _contained(feature_tokens, entry_tokens):
                contained_entry = "%s: %s" % (key, entry)

    if best_score >= UNCERTAIN_MIN_OVERLAP:
        return {
            "verdict": UNCERTAIN,
            "evidence": "partial match on %s" % best_entry,
            "score": round(best_score, 2),
        }
    if contained_entry:
        return {
            "verdict": UNCERTAIN,
            "evidence": "label contained in feature name: %s" % contained_entry,
            "score": round(best_score, 2),
        }
    return {
        "verdict": MISSING,
        "evidence": "no match; closest was %s" % (best_entry or "nothing"),
        "score": round(best_score, 2),
    }


def classify_all(candidates, idx, prefix_re=None):
    prefix_re = prefix_re or _configured_prefix_re()
    results = []
    for candidate in candidates:
        verdict = classify(candidate.get("name", ""), idx, prefix_re)
        merged = dict(candidate)
        merged.update(verdict)
        results.append(merged)
    return results


def main(argv):
    if len(argv) != 2:
        print("usage: match.py <candidates.json>", file=sys.stderr)
        return 2
    import paths

    payload = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    template = (paths.SHELL_DIR / "template.html").read_text(encoding="utf-8")
    idx = index.build(template)
    results = classify_all(payload.get("candidates", []), idx)
    print(json.dumps({"verdicts": results}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
