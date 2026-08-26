"""
Dictionary spell check with no third-party dependency.

The wordlist in data/en_us_words.txt is derived from the hunspell en_US
dictionary with regular inflections expanded. Loaded once and cached.

Real VMock flags any token missing from its dictionary and -- per repeated
student reports -- will not reliably learn correctly spelled product names.
Reproducing that is what quirks.aggressive_spellcheck controls: with it on,
"PyTorch" and "scikit-learn" get flagged the way they really do; with it off,
tokens that look like proper nouns or technical identifiers are skipped.
"""

from __future__ import annotations

import functools
import os
import re
from typing import List, Set, Tuple

from .lexicons import COMMONWEALTH_OK, MONTH_TOKENS, TECH_WHITELIST

# Words VMock surfaced for re-examination that a hunspell dictionary accepts.
FORCE_UNKNOWN = {"definer", "duffing"}

# Mirror of FORCE_UNKNOWN: ordinary business-English closed compounds that
# VMock's own dictionary evidently carries.  OBSERVED on Ziqi's resume --
# "lifecycle" appears in a bullet and VMock listed it in NEITHER the red
# ("misspelled") nor the yellow ("re-examine") bucket, while flagging the two
# real typos on the same page.  Only words VMock has been seen NOT to flag
# belong here.
FORCE_KNOWN = {"lifecycle", "lifecycles"}

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "en_us_words.txt")

# Unicode letters, so an accented proper noun stays one token. Matching only
# [A-Za-z] split "Poincaré" into "Poincar" and reported that stump as an
# unknown word -- something VMock never did.
TOKEN_RE = re.compile(r"[^\W\d_][\w'\-]*[^\W\d_]|[^\W\d_]", re.UNICODE)
SKIP_RE = re.compile(
    r"""(
        \b[\w.+-]+@[\w.-]+\b            # emails
      | \bhttps?://\S+                  # urls
      | \bwww\.\S+                      # bare urls
      | \b[\w-]+\.(com|org|net|edu|io|ai|co|gov|ca|uk|dev|me)(/[^\s|,;]*)?
    )""",
    re.I | re.X,
)


@functools.lru_cache(maxsize=1)
def dictionary() -> Set[str]:
    try:
        with open(DATA, encoding="utf-8") as f:
            return set(f.read().split("\n"))
    except OSError:
        return set()


def _looks_technical(token: str) -> bool:
    """Identifier-ish: internal capitals, digits, or an acronym compound."""
    if any(c.isdigit() for c in token):
        return True
    # Any capital after the first letter: camelCase, PyTorch, MLOps, DAFx,
    # DSP-feature, PID-based, Kinesin-Powered. Flagging these was the single
    # most common false positive against real resumes.
    if re.search(r"[A-Z]", token[1:]):
        return True
    if token.isupper() and len(token) <= 6:      # SQL, ETL, AWS
        return True
    return False


# Productive suffixes: if stripping one leaves a dictionary word, the token is
# a regular inflection the bundled wordlist simply does not enumerate
# ("schemas", "checkpointing", "manufacturability").
_SUFFIXES = (
    "ability", "ibility", "ization", "isation", "ations", "ation", "ments",
    "ment", "ness", "ings", "ing", "ers", "er", "ors", "or", "ies", "es",
    "ed", "s", "al", "ly", "able", "ible", "ised", "ized", "ising", "izing",
)
# Prefixes that attach freely to ordinary words in technical writing.
_PREFIXES = (
    "micro", "macro", "multi", "non", "pre", "post", "re", "sub", "super",
    "inter", "intra", "over", "under", "auto", "co", "semi", "anti", "cross",
    "mid", "meta", "mini", "hyper", "ultra", "de", "un", "bi", "tri",
)


def _in_dict(word: str, words: Set[str]) -> bool:
    return word in words or word in TECH_WHITELIST


def _derives_from_word(low: str, words: Set[str]) -> bool:
    """True when `low` is a regular derivation or compound of known words."""
    if len(low) < 5:
        return False
    for suf in _SUFFIXES:
        if not low.endswith(suf) or len(low) - len(suf) < 4:
            continue
        stem = low[: -len(suf)]
        cands = [stem]
        # English drops a silent -e only before a vowel-initial suffix, so
        # "manufactur|ability" -> manufacture is regular while "manag|ment"
        # -> manage is not: that one is the real typo it looks like.
        if suf[0] in "aeiouy":
            cands += [stem + "e", stem + "y", stem[:-1]]
        for cand in cands:
            if len(cand) >= 4 and _in_dict(cand, words):
                return True
    for pre in _PREFIXES:
        if low.startswith(pre) and len(low) - len(pre) >= 4:
            if _in_dict(low[len(pre):], words):
                return True
    # Closed compounds: backend, realtime, microscale, dataflow, toolchain.
    # The head must be a full word of its own, or "honours" splits as
    # "hon" + "ours" and every Commonwealth spelling walks through.
    for i in range(4, len(low) - 2):
        if _in_dict(low[:i], words) and _in_dict(low[i:], words):
            return True
    return False


def check(
    text: str,
    aggressive: bool = True,
    extra_ok: Set[str] = frozenset(),
    commonwealth_ok: bool = True,
) -> List[str]:
    """Return the misspelled tokens found in `text`, in order, deduplicated."""
    words = dictionary()
    if not words:
        return []
    cleaned = SKIP_RE.sub(" ", text)
    seen: Set[str] = set()
    bad: List[str] = []
    for raw in TOKEN_RE.findall(cleaned):
        low = raw.lower().strip("-'")
        if not low or len(low) < 3:
            continue
        if "_" in low:
            # snake_case is code, not prose. The 69 resume names solve_ivp in a
            # parenthetical and VMock's red list was exactly {rebasing, webhook,
            # idempotency} -- it never called an identifier a misspelling.
            continue
        if low in seen:
            continue
        if low in FORCE_UNKNOWN:
            # OBSERVED: VMock flagged "DEFINER" and "Duffing" for re-examination
            # even though hunspell's affix rules derive "definer" from define
            # and "duffing" from duff. VMock's dictionary evidently does not
            # carry those rare derived forms. Only words VMock has actually
            # been seen to flag belong here.
            bad.append(raw)
            seen.add(low)
            continue
        if (low in words or low in TECH_WHITELIST or low in MONTH_TOKENS
                or low in extra_ok or low in FORCE_KNOWN):
            continue
        if commonwealth_ok and low in COMMONWEALTH_OK:
            continue
        # hyphenated or slashed compounds pass if every part is a word
        parts = [p for p in re.split(r"[-'/]", low) if p]
        if len(parts) > 1 and all(
            # A productive prefix or suffix is a legitimate half of a
            # hyphenated compound even though it is not a headword itself.
            # OBSERVED: "pre-launch" sits in Ziqi's resume and VMock flagged
            # neither it nor any other "pre-"/"-based" form, red or yellow.
            p in words or p in TECH_WHITELIST or len(p) < 3
            or p in _PREFIXES or p in _SUFFIXES
            or (not aggressive and _derives_from_word(p, words))
            for p in parts
        ):
            continue
        if not aggressive:
            if _looks_technical(raw):
                continue
            if raw[:1].isupper() and raw[1:].islower():   # probable proper noun
                continue
            # Regular derivations and compounds of dictionary words. Only in
            # lenient mode: aggressive mode exists precisely to reproduce
            # VMock flagging anything its own wordlist does not carry.
            if _derives_from_word(low, words):
                continue
        seen.add(low)
        bad.append(raw)
    return bad


def classify(token: str) -> str:
    """OBSERVED: VMock splits unknown words into two classes.

        red    -> "The words highlighted in Red are misspelled"  (deducts)
        yellow -> "Re-examine the spellings"                     (no deduction)

    On a real report the red set was {rebasing, webhook, idempotency} and the
    yellow set {Soniox, JSONL, DEFINER, Duffing, WebSockets, Supabase}. Every
    red word is entirely lowercase; every yellow word carries a capital. The
    same split holds on a second resume (Toolchains, vLLM, FastAPI, MLOps,
    BFCL, CNMAT, Audealize, SocialFX, DAFx, Pydantic, SonAura, Qwen-7B-Chat --
    all capitalised, all free).
    """
    if any(c.isupper() for c in token):
        return "yellow"
    # Every red word VMock actually reported was long (rebasing, webhook,
    # idempotency). Short lowercase fragments are almost always PDF extraction
    # artifacts -- a Times-Roman ligature on one resume produced a phantom
    # "vfi" that VMock never saw -- so they are not treated as misspellings.
    return "red" if len(token.strip("-'")) >= 4 else "yellow"


def check_with_context(
    lines,
    aggressive: bool = True,
    extra_ok: Set[str] = frozenset(),
    commonwealth_ok: bool = True,
) -> List[Tuple[str, str]]:
    """Return (token, containing line text) pairs for UI display."""
    out = []
    seen = set()
    for line in lines:
        for tok in check(
            line.text, aggressive=aggressive, extra_ok=extra_ok,
            commonwealth_ok=commonwealth_ok,
        ):
            if tok.lower() in seen:
                continue
            seen.add(tok.lower())
            out.append((tok, line.text))
    # OBSERVED: the 69 resume writes both "WebSocket" and "WebSockets" and
    # VMock listed one entry, the plural. A word and its plural are one item.
    by_stem = {}
    for tok, ctx in out:
        stem = tok.lower().rstrip("s")
        keep = by_stem.get(stem)
        if keep is None or len(tok) > len(keep[0]):
            by_stem[stem] = (tok, ctx)
    kept = {id(v) for v in by_stem.values()}
    return [pair for pair in out if id(by_stem.get(pair[0].lower().rstrip("s"))) in kept
            and by_stem.get(pair[0].lower().rstrip("s"))[0] == pair[0]]
