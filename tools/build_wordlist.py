"""
Expand a hunspell .aff/.dic pair into a flat wordlist.

Hunspell dictionaries are affix-compressed: the entry `search/AZGMDRS` encodes
search, searches, searching, searcher, researched, unsearchable and so on via
prefix/suffix rules in the .aff file. Reading the .dic alone therefore looks as
if very common words are "missing". This script applies the rules so the
spell checker has a real vocabulary, with no runtime dependency.

    python3 tools/build_wordlist.py \
        --aff /usr/share/hunspell/en_US.aff \
        --dic /usr/share/hunspell/en_US.dic \
        --out vmock_clone/data/en_us_words.txt
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict


class Rule:
    __slots__ = ("strip", "affix", "cond", "regex")

    def __init__(self, strip, affix, cond, kind):
        self.strip = "" if strip == "0" else strip
        self.affix = "" if affix == "0" else affix
        self.cond = cond
        if cond == ".":
            self.regex = None
        elif kind == "SFX":
            self.regex = re.compile(cond + "$")
        else:
            self.regex = re.compile("^" + cond)

    def applies(self, word: str) -> bool:
        if self.regex is None:
            return True
        return bool(self.regex.search(word) if self.regex.pattern.endswith("$")
                    else self.regex.match(word))


def parse_aff(path):
    prefixes, suffixes, cross = defaultdict(list), defaultdict(list), {}
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 4 or parts[0] not in ("PFX", "SFX"):
                continue
            kind, flag = parts[0], parts[1]
            if parts[2] in ("Y", "N") and len(parts) == 4 and parts[3].isdigit():
                cross[(kind, flag)] = parts[2] == "Y"
                continue
            strip, affix, cond = parts[2], parts[3], parts[4] if len(parts) > 4 else "."
            affix = affix.split("/")[0]           # affix may carry further flags
            rule = Rule(strip, affix, cond, kind)
            (prefixes if kind == "PFX" else suffixes)[flag].append(rule)
    return prefixes, suffixes, cross


def apply_sfx(word, rule):
    if rule.strip and not word.endswith(rule.strip):
        return None
    if not rule.applies(word):
        return None
    return word[: len(word) - len(rule.strip)] + rule.affix if rule.strip else word + rule.affix


def apply_pfx(word, rule):
    if rule.strip and not word.startswith(rule.strip):
        return None
    if not rule.applies(word):
        return None
    return rule.affix + word[len(rule.strip):]


def build(aff_path, dic_path, only_in_compound="c"):
    prefixes, suffixes, cross = parse_aff(aff_path)
    out = set()
    with open(dic_path, encoding="utf-8", errors="ignore") as f:
        next(f)                                    # first line is the entry count
        for line in f:
            entry = line.strip().split("\t")[0]
            if not entry:
                continue
            word, _, flags = entry.partition("/")
            word = word.strip()
            if not word or not word.replace("'", "").replace("-", "").replace(".", "").isalpha():
                continue
            if only_in_compound and only_in_compound in flags:
                continue
            low = word.lower()
            out.add(low)
            sfx_forms = set()
            for flag in flags:
                for rule in suffixes.get(flag, ()):
                    got = apply_sfx(low, rule)
                    if got:
                        sfx_forms.add(got)
                        out.add(got)
            for flag in flags:
                for rule in prefixes.get(flag, ()):
                    got = apply_pfx(low, rule)
                    if got:
                        out.add(got)
                    if cross.get(("PFX", flag), False):
                        for s in sfx_forms:
                            got2 = apply_pfx(s, rule)
                            if got2:
                                out.add(got2)
    return {w for w in out if w and w.isascii()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--aff", default="/usr/share/hunspell/en_US.aff")
    ap.add_argument("--dic", default="/usr/share/hunspell/en_US.dic")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    words = build(a.aff, a.dic)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(words)))
    print(f"{len(words)} words -> {a.out}")
