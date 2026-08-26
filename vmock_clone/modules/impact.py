"""
IMPACT  /40

Does each line answer the recruiter's "so what?". Scored from six
sub-parameters, of which the first four carry VMock's own names.

Per bullet, the engine computes the six parameters VMock's guides list --
action-oriented, active voice, specifics, over-usage, filler words, bullet
length -- and those roll up into the sub-scores. The verb repository is
weighted exactly as the patent describes: "strong action verbs have higher
weights".
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

from ..core import BulletFeedback, Config, Finding, ModuleScore, SubScore, clamp
from ..lexicons import (
    ARTICLES_AND_CONNECTORS,
    BE_VERBS,
    BUZZWORDS,
    COMPETENCY_LEXICON,
    FILLER_ADVERBS,
    IRREGULAR_PARTICIPLES,
    IRREGULAR_PAST,
    NON_VERB_OPENERS,
    NOUN_PHRASE_OPENERS,
    PRONOUNS,
    PRONOUN_PHRASES,
    STANDARD_VERBS,
    STRONG_VERBS,
    VAGUE_QUANTIFIERS,
    WEAK_VERBS,
    WEASEL_PHRASES,
)
from ..parser import Document
from ..sections import Structure

WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-/]*")
# Length counts numbers too: "Cut cost 14% and saved $2.1M across 1,400 shipments"
# is a nine-word bullet by WORD_RE and a fourteen-token one to a reader, so the
# most heavily quantified bullets were being flagged as too short.
LENGTH_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'\-/%$.,]*")
SEPARATOR_RE = re.compile(r"\s[\u2014\u2013|]\s|:\s")
TECH_TERMS = COMPETENCY_LEXICON["analytical"]["technical"]
ALL_VERBS = STRONG_VERBS | STANDARD_VERBS | WEAK_VERBS

# A number that carries information, not a calendar date.
NUMBER_RE = re.compile(
    r"""(
        \$\s?\d[\d,]*(\.\d+)?\s?[kKmMbB]?     # money
      | \d[\d,]*(\.\d+)?\s?%                  # percentage
      | \b\d[\d,]*(\.\d+)?\s?[kKmMbB]\b       # 12K, 2.4M
      | \b\d+\s?[xX]\b                        # 3x
      | \b\d[\d,]*(\.\d+)?\+?\b               # plain counts
    )""",
    re.X,
)
YEARISH_RE = re.compile(r"\b(19|20)\d{2}\b")
STOPWORDS = (
    PRONOUNS
    | ARTICLES_AND_CONNECTORS
    | {"of", "to", "in", "for", "on", "with", "by", "at", "from", "as", "and",
       "or", "into", "over", "across", "per", "via", "using", "used", "was",
       "were", "is", "are", "be", "been", "being", "have", "has", "had"}
)


# ---------------------------------------------------------------------------
def lemmas(token: str) -> set:
    t = token.lower().strip(".,;:()[]")
    out = {t}
    if t in IRREGULAR_PAST:
        out.add(IRREGULAR_PAST[t])
    if t.endswith("ied"):
        out.add(t[:-3] + "y")
    if t.endswith("ed"):
        out.update({t[:-2], t[:-1]})
    if t.endswith("ing"):
        out.update({t[:-3], t[:-3] + "e"})
    if t.endswith("ies") and len(t) > 4:
        out.add(t[:-3] + "y")
    if t.endswith("s") and not t.endswith("ss"):
        out.add(t[:-1])
    if len(t) > 4 and t[-3] == t[-4] and t.endswith(("ed", "ing")):
        out.add(t[:-3])          # planned -> plan, running -> run
    # co-authored -> author, re-designed -> design, cross-trained -> train
    for pref in ("co-", "co", "re-", "pre-", "cross-", "self-", "e-"):
        if t.startswith(pref) and len(t) > len(pref) + 2:
            for base in list(out):
                stripped = base[len(pref):]
                if len(stripped) > 2:
                    out.add(stripped)
            out.update(lemmas_base(t[len(pref):]))
    return {x for x in out if x}


def lemmas_base(t: str) -> set:
    out = {t}
    if t.endswith("ies") and len(t) > 4:
        out.add(t[:-3] + "y")
    if t.endswith("ied"):
        out.add(t[:-3] + "y")
    if t.endswith("ed"):
        out.update({t[:-2], t[:-1]})
    if t.endswith("ing"):
        out.update({t[:-3], t[:-3] + "e"})
    if t.endswith("s") and not t.endswith("ss"):
        out.add(t[:-1])
    return out


# A line that lists things rather than claiming an accomplishment. VMock does
# not score "Relevant Courses: Modern Control Theory, ..." for its opening verb,
# and neither should this: it is a coursework list that happens to carry a
# bullet glyph.
LIST_LABEL_RE = re.compile(
    r"""^\s*(relevant\s+|selected\s+|core\s+|key\s+|technical\s+)?
        (course\s?work|courses|classes|curriculum|skills|tools|technologies|
         technical\s+skills|programming(\s+languages)?|languages|frameworks|
         libraries|software|platforms|interests|hobbies|activities|
         certifications|awards|honou?rs|publications)
        \s*[:\u2013\u2014-]""",
    re.I | re.X,
)

# Publication / acceptance credit lines: "DAFx 2026 - Accepted Demo: ...",
# "NeurIPS 2025 Workshop - Poster". These are credentials, not accomplishment
# bullets, so scoring them for an opening action verb is a false negative.
CREDENTIAL_RE = re.compile(
    r"""^[^.]{0,70}?\b(19|20)\d{2}\b[^.]{0,30}?
        \b(accepted|published|presented|poster|proceedings|workshop|
           in\s+review|under\s+review|submitted|forthcoming|to\s+appear)\b""",
    re.I | re.X,
)
# Leading adverbs: "Independently constructed ..." opens with a verb as far as
# a reader is concerned. Real VMock does not fail these.
LEADING_ADVERB_RE = re.compile(r"^\s*([A-Za-z]+ly)\b")


def is_list_line(text: str) -> bool:
    return bool(LIST_LABEL_RE.match(text or ""))


def is_credential_line(text: str) -> bool:
    t = (text or "").strip()
    if not t or is_list_line(t):
        return False
    return bool(CREDENTIAL_RE.match(t))


def verb_tier(text: str) -> Tuple[str, str]:
    """Classify how a bullet opens. Returns (tier, matched_token)."""
    low = text.lower().lstrip()
    for phrase in NON_VERB_OPENERS:
        if low.startswith(phrase):
            return "none", phrase
    for phrase in NOUN_PHRASE_OPENERS:
        if low.startswith(phrase):
            return "none", phrase
    tokens = WORD_RE.findall(text)
    if not tokens:
        return "none", ""
    # Step past a leading adverb before looking for the verb.
    if len(tokens) > 1 and LEADING_ADVERB_RE.match(text) and _classify(tokens[1]) != "none":
        tokens = tokens[1:]
    first = tokens[0]
    tier = _classify(first)
    if tier != "none":
        return tier, first
    # "Election Forecasting with Post-Stratification (R) - Fit binary logistic
    # regression ..." is a titled bullet: the verb sits after the separator.
    m = SEPARATOR_RE.search(text[:90])
    if m:
        rest = WORD_RE.findall(text[m.end():])
        if rest:
            tier2 = _classify(rest[0])
            if tier2 != "none":
                return tier2, rest[0]
    if first.lower().endswith("ing"):
        return "weak", first          # gerund opener reads as a duty, not a result
    return "none", first


def _classify(token: str) -> str:
    cands = lemmas(token)
    if cands & STRONG_VERBS:
        return "strong"
    if cands & STANDARD_VERBS:
        return "standard"
    if cands & WEAK_VERBS:
        return "weak"
    return "none"


def is_passive(text: str) -> bool:
    toks = [t.lower() for t in WORD_RE.findall(text)]
    for i, t in enumerate(toks):
        if t in BE_VERBS:
            for nxt in toks[i + 1 : i + 3]:
                if nxt in IRREGULAR_PARTICIPLES:
                    return True
                if nxt.endswith("ed") and len(nxt) > 4 and nxt not in WEAK_VERBS:
                    return True
    return False


SPELLED_NUMBERS = {
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "fifteen", "twenty", "thirty", "forty", "fifty",
    "hundred", "thousand", "million", "billion", "dozen", "several-hundred",
    "first", "second", "third", "fourth", "fifth", "half", "double", "triple",
}
ROMAN_RE = re.compile(r"\b(?:I{1,3}|IV|VI{0,3}|IX|XI{0,2})\b(?:\s*[-\u2013]\s*(?:I{1,3}|IV|VI{0,3}|IX|XI{0,2})\b)?")
GPA_NUM_RE = re.compile(r"\b\d\.\d{1,2}\s*/\s*\d(?:\.\d+)?\b")


def find_numbers(text: str) -> List[str]:
    """Quantification, as VMock appears to count it.

    OBSERVED: on a real report the green "Specifics" highlights fell on
    `GPA 3.22/4.0`, `300/400-level`, `I-III`, `II`, and the word `five`. So GPA
    ratios, roman numerals and spelled-out numbers all count, while bare
    calendar years do not.
    """
    masked = YEARISH_RE.sub(" ", text)
    out = [m.group(0).strip() for m in NUMBER_RE.finditer(masked)]
    out += [m.group(0) for m in GPA_NUM_RE.finditer(masked)]
    out += [m.group(0) for m in ROMAN_RE.finditer(text)]
    for tok in WORD_RE.findall(text):
        if tok.lower() in SPELLED_NUMBERS:
            out.append(tok)
    return out


def find_tools(text: str) -> List[str]:
    low = text.lower()
    hits = []
    for term in TECH_TERMS:
        if " " in term:
            if term in low:
                hits.append(term)
        elif re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", low):
            hits.append(term)
    return sorted(set(hits))


def find_avoided(text: str, include_articles: bool) -> List[str]:
    low = " " + text.lower() + " "
    hits = []
    for phrase in WEASEL_PHRASES:
        if f" {phrase} " in low or low.strip().startswith(phrase):
            hits.append(phrase)
    for term in VAGUE_QUANTIFIERS:
        if " " in term:
            if f" {term} " in low:
                hits.append(term)
        elif re.search(rf"\b{re.escape(term)}\b", low):
            hits.append(term)
    for tok in WORD_RE.findall(text):
        t = tok.lower()
        if t in FILLER_ADVERBS or t in PRONOUNS or t in BUZZWORDS:
            hits.append(t)
        elif include_articles and t in ARTICLES_AND_CONNECTORS:
            hits.append(t)
    return hits


# ---------------------------------------------------------------------------
def analyse_bullets(st: Structure, cfg: Config) -> List[BulletFeedback]:
    include_articles = cfg.quirk("articles_are_filler")
    b = cfg.get("impact.bullets", {}) or {}
    ideal_lo = int(b.get("ideal_min_words", 10))
    ideal_hi = int(b.get("ideal_max_words", 26))
    hard_lo = int(b.get("min_words", 6))
    hard_hi = int(b.get("max_words", 32))

    skip = set(cfg.get("impact.bullets.skip_sections", []) or [])
    out: List[BulletFeedback] = []
    idx = 0
    for sec in st.sections:
        if sec.canonical in skip:
            continue          # skills and coursework lists are not accomplishments
        for entry in sec.entries:
            for line in entry.bullets:
                text = line.body_text
                # Course lists and publication credits carry bullet glyphs but
                # are not accomplishment statements; scoring them as such
                # punished resumes for content VMock treats as neutral.
                if is_list_line(text) or is_credential_line(text):
                    continue
                tier, tok = verb_tier(text)
                nums = find_numbers(text)
                tools = find_tools(text)
                avoided = find_avoided(text, include_articles)
                wc = len(LENGTH_TOKEN_RE.findall(text))
                fb = BulletFeedback(
                    index=idx,
                    text=text,
                    section=sec.raw_heading,
                    action_oriented=tier in ("strong", "standard"),
                    verb=tok,
                    verb_tier=tier,
                    active_voice=not is_passive(text),
                    specifics=bool(nums) or bool(tools),
                    quantifiers=nums,
                    tools=tools,
                    filler_words=sorted(set(avoided)),
                    word_count=wc,
                    length_ok=ideal_lo <= wc <= ideal_hi,
                    page=getattr(line, "page", 0),
                    top=round(getattr(line, "top", 0.0), 2),
                    bottom=round(getattr(line, "bottom", 0.0), 2),
                    x0=round(getattr(line, "x0", 0.0), 2),
                    x1=round(getattr(line, "x1", 0.0), 2),
                )
                if tier == "none":
                    fb.flags.append("no action verb")
                elif tier == "weak":
                    fb.flags.append(f"weak verb “{tok}”")
                if not fb.active_voice:
                    fb.flags.append("passive voice")
                if not nums:
                    fb.flags.append("no quantification")
                if not tools:
                    fb.flags.append("no tool or method named")
                if avoided:
                    fb.flags.append(f"filler: {', '.join(sorted(set(avoided))[:4])}")
                if wc < hard_lo:
                    fb.flags.append(f"too short ({wc} words)")
                elif wc > hard_hi:
                    fb.flags.append(f"too long ({wc} words)")
                elif not fb.length_ok:
                    fb.flags.append(f"length {wc} words (aim {ideal_lo}-{ideal_hi})")
                out.append(fb)
                idx += 1
    return out


# ---------------------------------------------------------------------------
def _action_oriented(fbs: List[BulletFeedback], cfg: Config) -> SubScore:
    mx = float(cfg.get("impact.action_oriented", 11))
    sub = SubScore("action_oriented", "Action Oriented", 0.0, mx)
    if not fbs:
        sub.findings.append(Finding("error", "No bullets to evaluate.", mx))
        return sub
    w = cfg.get("impact.verb_weights", {}) or {}
    weights = {
        "strong": float(w.get("strong", 1.0)),
        "standard": float(w.get("standard", 0.65)),
        "weak": float(w.get("weak", 0.2)),
        "none": float(w.get("none", 0.0)),
    }
    score = sum(weights[f.verb_tier] for f in fbs) / len(fbs)
    sub.points = clamp(mx * score, 0, mx)

    counts = Counter(f.verb_tier for f in fbs)
    for f in [x for x in fbs if x.verb_tier == "none"][:5]:
        sub.findings.append(
            Finding("error", f"Bullet {f.index + 1} does not start with an action verb.",
                    mx / max(1, len(fbs)), evidence=f.text[:100], line_index=f.index,
                    fix="Open with a past-tense verb describing what you did: Engineered, Negotiated, Automated.")
        )
    for f in [x for x in fbs if x.verb_tier == "weak"][:5]:
        sub.findings.append(
            Finding("warn", f"Bullet {f.index + 1} opens with the weak verb “{f.verb}”.",
                    mx * 0.5 / max(1, len(fbs)), evidence=f.text[:100], line_index=f.index,
                    fix="Swap for a verb that claims ownership: Led, Built, Delivered, Analyzed.")
        )
    passive = [x for x in fbs if not x.active_voice]
    for f in passive[:3]:
        sub.findings.append(
            Finding("warn", f"Bullet {f.index + 1} is in the passive voice.", 0.0,
                    evidence=f.text[:100], line_index=f.index,
                    fix="Rewrite so you are the subject: “Was awarded X” becomes “Earned X”.")
        )
    if counts["strong"] and not sub.findings:
        sub.findings.append(
            Finding("good", f"{counts['strong']} bullet(s) open with a strong action verb."))
    sub.detail = {"tiers": dict(counts), "mean_weight": round(score, 3)}
    return sub


def _specifics(fbs: List[BulletFeedback], cfg: Config) -> SubScore:
    mx = float(cfg.get("impact.specifics", 11))
    sub = SubScore("specifics", "Specifics", 0.0, mx)
    if not fbs:
        sub.findings.append(Finding("error", "No bullets to evaluate.", mx))
        return sub
    spec = cfg.get("impact.specifics_rules", {}) or {}
    q_target = float(spec.get("quantified_bullet_target", 0.6))
    t_target = float(spec.get("tools_named_target", 0.35))
    passive_pen = float(spec.get("passive_voice_penalty_per_bullet", 0.5))

    q_share = sum(1 for f in fbs if f.quantifiers) / len(fbs)
    t_share = sum(1 for f in fbs if f.tools) / len(fbs)
    q_component = min(1.0, q_share / q_target) if q_target else 1.0
    t_component = min(1.0, t_share / t_target) if t_target else 1.0
    q_weight = float(spec.get("quantification_weight", 0.7))
    raw = q_weight * q_component + (1.0 - q_weight) * t_component

    n_passive = sum(1 for f in fbs if not f.active_voice)
    penalty = min(0.25, (n_passive / len(fbs)) * passive_pen)
    sub.points = clamp(mx * (raw - penalty), 0, mx)

    # OBSERVED panel wording. VMock does not count bullets at you -- it names
    # the SECTIONS that need more numbers, as chips:
    #
    #   "Include more quantification of the impact and scope of your work in
    #    the following sections:"   -> projects
    #
    # On that resume Projects ran 3 of 13 bullets quantified and Experience 1
    # of 6, and only "projects" was named -- the section carrying the most
    # unquantified bullets, not the lowest share. Sections are therefore
    # ordered by how many unquantified bullets they hold. How many chips VMock
    # will show at once has not been observed.
    by_section = {}
    for f in fbs:
        by_section.setdefault(f.section or "", []).append(f)
    poor = []
    for name, group in by_section.items():
        missing = [x for x in group if not x.quantifiers]
        if group and (len(group) - len(missing)) / len(group) < q_target:
            poor.append((name, len(missing), len(group)))
    poor.sort(key=lambda r: (-r[1], r[0]))

    unquantified = [f for f in fbs if not f.quantifiers]
    if poor:
        first = next((x for x in unquantified if (x.section or "") == poor[0][0]),
                     unquantified[0] if unquantified else None)
        sub.findings.append(
            Finding("error" if q_share < 0.35 else "warn",
                    "Include more quantification of the impact and scope of your "
                    "work in the following sections:",
                    mx * (1 - q_component) * q_weight,
                    evidence="  ".join(name.lower() for name, _, _ in poor[:3]),
                    line_index=first.index if first else None,
                    fix="Add scale and frequency: how many, how often, how much, how much better.")
        )
    if t_share < t_target:
        sub.findings.append(
            Finding("warn", "Few bullets name the tool, method or system you used.",
                    mx * (1 - t_component) * (1.0 - q_weight),
                    fix="Name the stack: “in Python and SQL”, “using regression analysis”, “in Salesforce”.")
        )
    if q_share >= q_target and t_share >= t_target:
        sub.findings.append(Finding("good", "Bullets are concrete: numbers and named tools throughout."))
    sub.detail = {
        "quantified_share": round(q_share, 3),
        "tools_share": round(t_share, 3),
        "passive_bullets": n_passive,
    }
    return sub


def _text_units(st: Structure, cfg: Config, skip: set = frozenset()):
    """Every scannable text unit. VMock counts filler, pronouns and overused
    words across the whole document -- every pronoun it flagged sat inside the
    Personal Statement, a section this clone previously skipped entirely."""
    units = []
    for sec in st.sections:
        if sec.canonical in skip:
            continue
        for entry in sec.entries:
            for hl in entry.header_lines:
                units.append((hl.body_text, sec.raw_heading, "header"))
            for bl in entry.bullets:
                units.append((bl.body_text, sec.raw_heading, "bullet"))
        seen = {id(l) for e in sec.entries for l in (e.header_lines + e.bullets)}
        for line in sec.lines:
            if id(line) not in seen:
                units.append((line.body_text, sec.raw_heading, "line"))
    return units


def _overuse(st: Structure, fbs: List[BulletFeedback], cfg: Config) -> SubScore:
    """OBSERVED: 'You have overused a few words :  Analyzed 3  Provided/Providing 3'

    Two facts read off the real UI: the threshold fires AT 3 occurrences, and
    inflected forms are grouped into one item ("Provided/Providing"). The old
    implementation counted exact tokens at >3 and therefore never fired.
    """
    mx = float(cfg.get("impact.overuse", 8))
    sub = SubScore("overuse", "Overuse", mx, mx)
    r = cfg.get("impact.overuse_rules", {}) or {}
    threshold = int(r.get("flag_at_occurrences", 3))
    lemma_grouped = bool(r.get("lemma_grouped", True))
    verbs_only = bool(r.get("verbs_only", True))
    exclude_strong = bool(r.get("exclude_distinctive_verbs", True))
    require_vf = bool(r.get("require_verb_form", True))
    max_shown = int(r.get("max_reported", 2))
    common_only = bool(r.get("common_verbs_only", True))
    common_verbs = {w.lower() for w in (r.get("common_verbs") or [])}
    if common_only and not common_verbs:
        common_only = False

    skip = set(r.get("skip_sections", []) or [])
    # OBSERVED: on Masters_1 VMock counted "Provided/Providing 3", but only two
    # of those sit in bullets -- the third is in the Personal Statement. So
    # Overuse spans prose as well, while list sections (Skills, Coursework) are
    # excluded, which is why "Applied" and "Physics" were never flagged.
    texts = [t for t, _, _ in _text_units(st, cfg, skip)]
    if not texts:
        sub.points = 0.0
        sub.findings.append(Finding("error", "No content to assess for repetition.", mx))
        return sub

    # group by lemma, remembering the surface forms so the report can show
    # "Provided/Providing" the way VMock does
    groups: Dict[str, Counter] = defaultdict(Counter)
    for text in texts:
        for tok in WORD_RE.findall(text):
            low = tok.lower()
            if low in STOPWORDS or len(low) < 4:
                continue
            # OBSERVED: VMock flagged "Analyzed" and "Provided/Providing" -- both
            # verbs -- while "Physics" (6 occurrences) and "Analysis" (8) went
            # unflagged. Overuse is counted over verbs, not over all content words.
            if verbs_only:
                lem = lemmas(low)
                if not (lem & ALL_VERBS):
                    continue
                # OBSERVED: "Engineered" appears 3x on the 93 resume and is NOT
                # flagged, while "Developed", "Support/Supporting", "Analyzed"
                # and "Provided" are. VMock's own Community Insights names
                # DEVELOPED and ANALYSED as the community's most-used verbs, so
                # overuse targets common verbs, not distinctive ones.
                if exclude_strong and (lem & STRONG_VERBS):
                    continue
                # OBSERVED, and narrower than "not a strong verb": across the
                # two reports the ONLY words VMock flagged were analyzed,
                # provided/providing, developed and support/supporting, while
                # Applied (4x), Lead/Leading (3x), Engineered (3x),
                # benchmarking/benchmarks (3x) and model (7x) all cleared the
                # threshold and were left alone. VMock's own Community Insights
                # names DEVELOPED and ANALYSED as the community's most-used
                # action verbs, so Overuse fires on a short list of
                # community-common verbs rather than on any repeated verb.
                # This list holds exactly what has been seen flagged; it grows
                # only when another flag is read off the product.
                if common_only and not (lem & common_verbs):
                    continue
            key = _overuse_key(low) if lemma_grouped else low
            # VMock renders each surface form Title-cased and collapses case,
            # e.g. "Provided/Providing 3", "Support/Supporting 3".
            groups[key][tok.capitalize()] += 1

    flagged = []
    for key, forms in groups.items():
        total = sum(forms.values())
        if require_vf:
            # HEURISTIC (not an observed rule): a crude part-of-speech proxy.
            # "model/models" x7 was NOT flagged and is a noun throughout
            # ("model training", "model rollback"); "Support/Supporting" x3 WAS
            # flagged and is verbal throughout. Require the inflected -ed/-ing
            # forms to be at least half of all occurrences.
            infl = sum(n for f, n in forms.items()
                       if f.lower().endswith(("ed", "ing")))
            if infl * 2 < total:
                continue
        if total >= threshold:
            # OBSERVED ordering: "Provided/Providing", "Support/Supporting" --
            # alphabetical within the group, not by frequency.
            label = "/".join(sorted(forms))
            flagged.append((label, total))
    flagged.sort(key=lambda kv: (-kv[1], kv[0]))

    if not flagged:
        sub.findings.append(Finding("good", "No overused words detected."))
        sub.detail = {"threshold": threshold, "flagged": []}
        return sub

    # each flagged group costs a share; matches VMock showing this as a
    # graded sub-parameter rather than pass/fail
    # OBSERVED: two flagged words ("Analyzed 3", "Provided/Providing 3") still
    # rated "On Track!", so each flagged group costs a modest share.
    shown = flagged[:max_shown]
    # Calibrated: two flagged words rated "On Track!" on both observed reports.
    full_at = float(r.get("full_loss_at_groups", 4.5))
    sub.points = clamp(mx - mx * min(1.0, len(shown) / full_at), 0, mx)
    # OBSERVED panel: one heading, then a chip per word. VMock's wording,
    # spacing and all.
    sub.findings.append(
        Finding("warn", "You have overused a few words :",
                mx - sub.points,
                evidence="  ".join(f"{label} {n}" for label, n in shown),
                fix="Revise the resume content to minimize the use of overused "
                    "words as much as possible.")
    )
    sub.detail = {"threshold": threshold, "flagged": flagged[:20],
                  "reported": shown}
    return sub


def _overuse_key(word: str) -> str:
    """Collapse inflections so Provided/Providing/Provide count as one word."""
    for cand in sorted(lemmas(word), key=len):
        if len(cand) >= 4:
            return cand
    return word


def _avoided_words(st: Structure, fbs: List[BulletFeedback], cfg: Config) -> SubScore:
    """OBSERVED: VMock shows TWO lists under Avoided Words.

        "words which are usually considered as filler words"  -> That 1, Have 1, The 5
        "personal pronouns which should be avoided"           -> I 7, My 4, I am 3, ...

    Both were drawn from the Personal Statement, which this clone used to skip.
    Articles are counted -- "The 5" settles that question directly.
    """
    mx = float(cfg.get("impact.avoided_words", 8))
    sub = SubScore("avoided_words", "Avoided Words", mx, mx)
    r = cfg.get("impact.avoided_words_rules", {}) or {}
    scan_all = bool(r.get("scan_all_sections", True))
    w_fill = float(r.get("filler_weight", 0.5))
    w_pron = float(r.get("pronoun_weight", 0.5))
    include_articles = bool(r.get("include_articles", True))

    texts = ([t for t, _, _ in _text_units(st, cfg)] if scan_all
             else [f.text for f in fbs])
    if not texts:
        sub.points = 0.0
        sub.findings.append(Finding("error", "No content to assess for filler language.", mx))
        return sub

    filler = Counter()
    pronouns = Counter()
    total_words = 0
    for text in texts:
        toks = WORD_RE.findall(text)
        total_words += len(toks)
        low = " " + text.lower() + " "
        for phrase in PRONOUN_PHRASES:
            n = low.count(f" {phrase} ")
            if n:
                pronouns[phrase.title()] += n
        for i, tok in enumerate(toks):
            t = tok.lower()
            if t in PRONOUNS:
                # OBSERVED: VMock's Specifics panel green-highlights "I-III" and
                # "II" as quantification, so a bare capital I in a course code
                # ("Linear Algebra I-II", "Computer Science I.") is a roman
                # numeral to VMock, not a pronoun. Only count "I" when a
                # lowercase word follows it, which is how it reads in prose
                # ("I am", "I led").
                if tok == "I":
                    nxt = toks[i + 1] if i + 1 < len(toks) else ""
                    if not (nxt[:1].islower()):
                        continue
                pronouns[tok.title() if len(tok) > 1 else tok.upper()] += 1
            elif t in FILLER_ADVERBS or t in BUZZWORDS:
                # VAGUE_QUANTIFIERS is deliberately NOT counted. VMock's filler
                # list on Masters_1 showed three items at counts 1, 1 and 5 --
                # so nothing was truncated away -- and "Multiple", which occurs
                # once in that resume, was not among them.
                filler[tok.title()] += 1
            elif include_articles and t in ARTICLES_AND_CONNECTORS:
                filler[tok.title()] += 1
        for phrase in WEASEL_PHRASES:
            n = low.count(f" {phrase} ")
            if n:
                filler[phrase.title()] += n

    total_words = max(1, total_words)
    n_fill = sum(filler.values())
    n_pron = sum(pronouns.values())
    fill_rate = n_fill / total_words
    pron_rate = n_pron / total_words
    # VMock reports these as raw COUNTS ("The 5", "I 7"), never as a density,
    # and the two resumes that pin the scale differ far more in count than in
    # rate. The ramp is therefore over counts.
    f_full = float(r.get("filler_full_at", 16))
    p_full = float(r.get("pronoun_full_at", 8))
    lost = mx * min(1.0, w_fill * min(1.0, n_fill / f_full)
                        + w_pron * min(1.0, n_pron / p_full))
    sub.points = clamp(mx - lost, 0, mx)

    if filler:
        top = "  ".join(f"{w} {n}" for w, n in filler.most_common(6))
        sub.findings.append(
            Finding("warn",
                    "You have used some words which are usually considered as "
                    f"filler words: {top}", mx * 0.4,
                    fix="Revise the bullet content to minimize the use of filler "
                        "words as much as possible.")
        )
    if pronouns:
        top = "  ".join(f"{w} {n}" for w, n in pronouns.most_common(6))
        sub.findings.append(
            Finding("error",
                    "You have included personal pronouns which should be avoided: "
                    f"{top}", mx * 0.4,
                    fix="Rewrite in implied first person: drop \"I\", \"my\" and "
                        "\"I am\" entirely.")
        )
    if not filler and not pronouns:
        sub.findings.append(Finding("good", "No filler words or personal pronouns detected."))

    sub.detail = {
        "filler": filler.most_common(20),
        "pronouns": pronouns.most_common(20),
        "filler_rate": round(fill_rate, 4),
        "pronoun_rate": round(pron_rate, 4),
    }
    return sub


def _bullet_length(fbs: List[BulletFeedback], st: Structure, cfg: Config) -> SubScore:
    mx = float(cfg.get("impact.bullet_length", 4))
    sub = SubScore("bullet_length", "Bullet Length & Density", mx, mx)
    if not fbs:
        sub.points = 0.0
        sub.findings.append(Finding("error", "No bullets found.", mx))
        return sub
    b = cfg.get("impact.bullets", {}) or {}
    ideal_lo, ideal_hi = int(b.get("ideal_min_words", 10)), int(b.get("ideal_max_words", 26))
    min_per = int(b.get("min_bullets_per_entry", 2))

    short = [f for f in fbs if f.word_count < ideal_lo]
    long_ = [f for f in fbs if f.word_count > ideal_hi]
    # Being over-long is barely penalised: real VMock accepts 50-word bullets
    # and still asks for *more* detail. Being too thin is the real problem.
    lost = mx * min(0.55, (len(short) * 1.0 + len(long_) * 0.25) / len(fbs) * 0.8)
    off = short + long_
    for f in off[:4]:
        sub.findings.append(
            Finding("warn", f"Bullet {f.index + 1} is {f.word_count} words (aim {ideal_lo}-{ideal_hi}).",
                    mx * 0.15, evidence=f.text[:100], line_index=f.index,
                    fix="One clear accomplishment per bullet, on one or two printed lines.")
        )

    thin = [
        e for s in st.sections if s.canonical in ("experience", "leadership")
        for e in s.entries
        if e.header_lines and 0 < len(e.bullets) < min_per
    ]
    empty = [
        e for s in st.sections if s.canonical in ("experience", "leadership")
        for e in s.entries
        if e.header_lines and not e.bullets and len(e.header_lines) < 3
    ]
    if thin or empty:
        pen = mx * min(0.3, 0.12 * (len(thin) + len(empty)))
        lost += pen
        sub.findings.append(
            Finding("warn", f"{len(thin) + len(empty)} entry/entries have fewer than {min_per} bullets.",
                    pen, evidence=(thin or empty)[0].header_text[:70],
                    fix=f"Give every role at least {min_per} bullets, or drop the role.")
        )
    sub.points = clamp(mx - lost, 0, mx)
    if not sub.findings:
        sub.findings.append(Finding("good", "Bullet lengths are in the readable range."))
    sub.detail = {
        "mean_words": round(sum(f.word_count for f in fbs) / len(fbs), 1),
        "off_target": len(off),
        "total": len(fbs),
    }
    return sub


def _career_progression(st: Structure, cfg: Config) -> SubScore:
    mx = float(cfg.get("impact.career_progression", 4))
    sub = SubScore("career_progression", "Career Progression", mx, mx)
    cp = cfg.get("impact.career_progression_rules", {}) or {}
    gap_months = int(cp.get("penalise_gap_months", 6))

    entries = [
        e for s in st.sections
        if s.canonical in ("experience", "leadership", "research", "projects")
        for e in s.entries
        if e.dates and e.header_lines
    ]
    if len(entries) < 2:
        sub.points = mx * 0.6
        sub.findings.append(
            Finding("info", "Not enough dated roles to read a trajectory.", mx * 0.4,
                    fix="Two or more dated roles let a recruiter see direction.")
        )
        return sub

    timeline = []
    for e in entries:
        starts = [d.start_ord for d in e.dates if d.start_ord]
        ends = [d.end_ord for d in e.dates if d.end_ord]
        if starts:
            timeline.append((min(starts), max(ends) if ends else min(starts), e))
    timeline.sort(key=lambda t: t[0])

    lost = 0.0
    levels = [e.seniority for _, _, e in timeline if e.seniority]
    if len(levels) >= 3:
        # Compare first half to second half rather than adjacent pairs: a
        # student who takes a summer internship after a term-time leadership
        # role has not been demoted, and adjacent-pair comparison says they
        # have on almost every real resume.
        mid = len(levels) // 2
        early = sum(levels[:mid]) / max(1, mid)
        late = sum(levels[mid:]) / max(1, len(levels) - mid)
        ascending = sum(1 for a, b in zip(levels, levels[1:]) if b >= a)
        ratio = 1.0 if late >= early else ascending / (len(levels) - 1)
        if ratio < 0.4:
            lost += mx * 0.2
            sub.findings.append(
                Finding("warn", "Roles do not read as increasing in responsibility.", mx * 0.2,
                        fix="Order entries newest-first and make the senior title visible in the entry line.")
            )
        elif ratio == 1.0:
            sub.findings.append(Finding("good", "Clear upward progression across roles."))

    gaps = []
    for (s1, e1, en1), (s2, e2, en2) in zip(timeline, timeline[1:]):
        if e1 < 9999 * 12 and s2 - e1 > gap_months:
            gaps.append((en1, en2, s2 - e1))
    if gaps:
        pen = mx * min(0.35, 0.15 * len(gaps))
        lost += pen
        sub.findings.append(
            Finding("info", f"{len(gaps)} gap(s) longer than {gap_months} months between roles.", pen,
                    evidence=f"{gaps[0][0].header_text[:34]} -> {gaps[0][1].header_text[:34]}",
                    fix="Fill visible gaps with coursework, projects or volunteering if you have them.")
        )

    latest_end = max(t[1] for t in timeline)
    if latest_end < 9999 * 12:
        newest_year = latest_end // 12
        if newest_year and newest_year < 2000:
            pass
        else:
            sub.detail["most_recent_end_year"] = newest_year

    sub.points = clamp(mx - lost, 0, mx)
    if not sub.findings:
        sub.findings.append(Finding("good", "Timeline is continuous and reads in one direction."))
    sub.detail.update({"entries": len(timeline), "seniority_levels": levels})
    return sub


EXTRACURRICULAR_SECTIONS = ("leadership", "awards", "volunteer", "publications")


def _extracurriculars(st: Structure, cfg: Config) -> SubScore:
    """OBSERVED to exist on the "CMU Resumes" benchmark and to be absent on
    "CMU Masters - Technical". Its panel text has never been read, so the rule
    below is the narrowest one the arithmetic supports, not a guess at VMock's
    internals.

    What the arithmetic says. Brendan's 77 and 93 resumes score Impact 34/40.
    Every other Impact sub-parameter on them is clean -- every bullet opens with
    an action verb, 64% carry a number, nothing is overused, and after the 69 ->
    77 rewrite no filler word or pronoun remains. On the four-sub-parameter
    benchmark that profile scores 40/40, so the missing 6 points belong to the
    one sub-parameter those resumes cannot satisfy: they have no section outside
    Education, Work Experience, Projects and Skills.

    The section names come from VMock's own Essential Sections panel, which
    lists Leadership, Honors, Awards and Conferences/Publications as the
    optional groups a resume may add.
    """
    mx = float(cfg.get("impact.extracurriculars.points", 6))
    sub = SubScore("extracurriculars", "Extra-curriculars", 0.0, mx)
    present = [s_ for s_ in st.sections
               if s_.canonical in EXTRACURRICULAR_SECTIONS]
    if present:
        sub.points = mx
        sub.status = "Good Job!"
        sub.findings.append(
            Finding("good", "You have included extra-curricular involvement.",
                    0.0, evidence=", ".join(s_.raw_heading for s_ in present)))
    else:
        sub.points = 0.0
        sub.status = "Needs Work!"
        sub.findings.append(
            Finding("error",
                    "Your resume shows no extra-curricular involvement.", mx,
                    fix="Add a Leadership, Activities, Honors, Awards or "
                        "Volunteer section describing involvement outside your "
                        "coursework and jobs."))
    sub.detail = {"sections_found": [s_.raw_heading for s_ in present]}
    return sub


_IMPACT_BUILDERS = {
    "action_oriented": lambda st, fbs, cfg: _action_oriented(fbs, cfg),
    "specifics": lambda st, fbs, cfg: _specifics(fbs, cfg),
    "overuse": lambda st, fbs, cfg: _overuse(st, fbs, cfg),
    "avoided_words": lambda st, fbs, cfg: _avoided_words(st, fbs, cfg),
    "extracurriculars": lambda st, fbs, cfg: _extracurriculars(st, cfg),
}

_DEFAULT_IMPACT_SUBS = ["action_oriented", "specifics", "overuse", "avoided_words"]

GOOD_JOB_MESSAGE = {
    # OBSERVED verbatim on Masters_1's Action Oriented panel.
    "action_oriented": "You have done a good job of using action-oriented "
                       "language in your resume",
    # NOT observed -- no Good Job! panel has been read for these three. Own
    # wording, deliberately plain.
    "specifics": "Your bullets carry the numbers and named work they need.",
    "overuse": "No overused words detected.",
    "avoided_words": "No filler words or personal pronouns detected.",
    "extracurriculars": "You have included extra-curricular involvement.",
}


# ---------------------------------------------------------------------------
def score(doc: Document, st: Structure, cfg: Config) -> Tuple[ModuleScore, List[BulletFeedback]]:
    mx = float(cfg.get("modules.impact", 40))
    fbs = analyse_bullets(st, cfg)
    # OBSERVED: the sub-parameter set is benchmark-conditional. "CMU Masters -
    # Technical Resumes" shows 4; "CMU Resumes" shows 5, the extra one being
    # Extra-curriculars. Impact is 40 either way, so the shared four are
    # rescaled to make room for it -- which is exactly what the renormalisation
    # below does.
    profile = cfg.get("benchmark_profiles.default", "cmu_masters_technical")
    wanted = cfg.get(f"benchmark_profiles.{profile}.impact_subparameters") or _DEFAULT_IMPACT_SUBS
    keys = [k for k in wanted if k in _IMPACT_BUILDERS] or _DEFAULT_IMPACT_SUBS
    subs = [_IMPACT_BUILDERS[k](st, fbs, cfg) for k in keys]

    declared = sum(s.max_points for s in subs)
    total = sum(s.points for s in subs)
    if declared and abs(declared - mx) > 0.01:
        scale = mx / declared
        total *= scale
        for s_ in subs:
            s_.points *= scale
            s_.max_points *= scale

    # VMock puts a status chip on every sub-parameter. The three-way vocabulary
    # is its own -- "Good Job! / On Track! / Needs Work!" -- and the cut points
    # are the ones the Competencies module pins: Good Job at 5.0 of 6.0 and On
    # Track at 2.5 of 6.0, i.e. 83% and 42% of the sub-parameter's own maximum.
    good_at = float(cfg.get("impact.chip_good_job_ratio", 5.0 / 6.0))
    track_at = float(cfg.get("impact.chip_on_track_ratio", 2.5 / 6.0))
    for s_ in subs:
        if not s_.max_points:
            continue
        ratio = s_.points / s_.max_points
        s_.status = ("Good Job!" if ratio >= good_at
                     else "On Track!" if ratio >= track_at else "Needs Work!")
        # OBSERVED: at "Good Job!" the panel carries the praise line and nothing
        # else. Masters_1 has a bullet opening on a noun and another opening on
        # "Provided", and its Action Oriented panel still said only "You have
        # done a good job of using action-oriented language in your resume".
        if s_.status == "Good Job!":
            s_.findings = [f for f in s_.findings
                           if f.severity in ("good", "info")]
            if not s_.findings:
                s_.findings.append(Finding("good", GOOD_JOB_MESSAGE[s_.key]))

    mod = ModuleScore("impact", "Impact", clamp(total, 0, mx), mx, subs)
    return mod, fbs
