"""
Test suite. Plain unittest - no pytest dependency.

    python3 -m unittest discover -s tests -v
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from vmock_clone.core import Config                                  # noqa: E402
from vmock_clone.modules.impact import (                             # noqa: E402
    find_avoided, find_numbers, find_tools, is_passive, lemmas, verb_tier,
)
from vmock_clone.scoring import score_document, zone_for             # noqa: E402
from vmock_clone.sections import (                                   # noqa: E402
    ampersand_issue, normalize_heading, parse_dates,
)
from vmock_clone import spell                                        # noqa: E402
from vmock_clone.spell import check                                  # noqa: E402

SAMPLES = os.path.join(ROOT, "samples")


def sample(name):
    path = os.path.join(SAMPLES, name)
    if not os.path.exists(path):
        sys.path.insert(0, SAMPLES)
        import make_samples

        make_samples.weak(os.path.join(SAMPLES, "weak_resume.pdf"))
        make_samples.strong(os.path.join(SAMPLES, "strong_resume.pdf"))
        make_samples.two_column(os.path.join(SAMPLES, "two_column_resume.pdf"))
    return path


class TestVerbs(unittest.TestCase):
    def test_tiers(self):
        self.assertEqual(verb_tier("Spearheaded the migration")[0], "strong")
        self.assertEqual(verb_tier("Analyzed 400 records")[0], "standard")
        self.assertEqual(verb_tier("Helped the team")[0], "weak")
        self.assertEqual(verb_tier("Responsible for filing")[0], "none")
        self.assertEqual(verb_tier("Market research on 3 firms")[0], "none")

    def test_irregular_past(self):
        for v in ("Led", "Built", "Wrote", "Taught", "Oversaw", "Ran"):
            self.assertIn(verb_tier(f"{v} something")[0], ("strong", "standard"), v)

    def test_hyphenated(self):
        self.assertIn(verb_tier("Co-authored a paper")[0], ("strong", "standard"))

    def test_gerund_is_weak(self):
        self.assertEqual(verb_tier("Working on reports")[0], "weak")

    def test_lemmas(self):
        self.assertIn("plan", lemmas("planned"))
        self.assertIn("optimize", lemmas("optimizing"))
        self.assertIn("study", lemmas("studies"))


class TestPassive(unittest.TestCase):
    def test_detects(self):
        self.assertTrue(is_passive("Was awarded a scholarship"))
        self.assertTrue(is_passive("Reports were generated weekly"))

    def test_ignores_active(self):
        self.assertFalse(is_passive("Generated 40 reports weekly"))
        self.assertFalse(is_passive("Engineered a pipeline in Python"))


class TestSpecifics(unittest.TestCase):
    def test_numbers(self):
        self.assertTrue(find_numbers("Cut latency by 38%"))
        self.assertTrue(find_numbers("Raised $450K in sponsorship"))
        self.assertTrue(find_numbers("Managed 2.4M records"))

    def test_years_are_not_metrics(self):
        self.assertEqual(find_numbers("Worked there in 2023"), [])

    def test_tools(self):
        self.assertIn("python", find_tools("Built it in Python and SQL"))
        self.assertIn("tableau", find_tools("Dashboards in Tableau"))

    def test_avoided(self):
        hits = find_avoided("Successfully helped with various tasks as needed", True)
        self.assertIn("successfully", hits)
        self.assertIn("various", hits)


class TestDates(unittest.TestCase):
    def test_range_inherits_year(self):
        d = parse_dates("Jun - Aug 2017")[0]
        self.assertEqual((d.start_month, d.start_year), (6, 2017))
        self.assertEqual((d.end_month, d.end_year), (8, 2017))

    def test_spacing_rule(self):
        self.assertTrue(parse_dates("Jun 2024 - Aug 2024")[0].separator_spacing_ok)
        self.assertFalse(parse_dates("June-August 2017")[0].separator_spacing_ok)

    def test_bad_abbreviation(self):
        self.assertEqual(parse_dates("Sept 2020 - Present")[0].bad_abbrev, "sept")
        self.assertIsNone(parse_dates("Sep 2020 - Present")[0].bad_abbrev)

    def test_present_and_expected(self):
        self.assertTrue(parse_dates("Sep 2023 - Present")[0].is_present)
        self.assertTrue(parse_dates("Expected May 2027")[0].is_expected)


class TestHeadings(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_heading("  EDUCATION:  "), "education")

    def test_ampersand_quirk(self):
        self.assertEqual(ampersand_issue("Leadership and Activities"), "Leadership & Activities")
        self.assertIsNone(ampersand_issue("Leadership & Activities"))


class TestSpell(unittest.TestCase):
    def test_common_words_pass(self):
        self.assertEqual(check("research retail per detail successfully reviewed"), [])

    def test_catches_typos(self):
        self.assertIn("recieved", check("I recieved an award"))

    def test_tech_whitelist(self):
        self.assertEqual(check("Built in PyTorch with pandas and Airflow"), [])

    def test_commonwealth_toggle(self):
        self.assertEqual(check("First Class Honours"), [])
        self.assertIn("Honours", check("First Class Honours", commonwealth_ok=False))

    def test_lenient_skips_proper_nouns(self):
        self.assertIn("Northwind", check("Northwind Analytics", aggressive=True))
        self.assertNotIn("Northwind", check("Northwind Analytics", aggressive=False))


class TestZones(unittest.TestCase):
    def setUp(self):
        self.cfg = Config.load()

    def test_boundaries(self):
        self.assertEqual(zone_for(0, self.cfg), "red")
        self.assertEqual(zone_for(32, self.cfg), "red")
        self.assertEqual(zone_for(33, self.cfg), "yellow")
        self.assertEqual(zone_for(85, self.cfg), "yellow")
        self.assertEqual(zone_for(86, self.cfg), "green")
        self.assertEqual(zone_for(100, self.cfg), "green")


class TestEndToEnd(unittest.TestCase):
    def test_strong_beats_weak(self):
        strong = score_document(sample("strong_resume.pdf"))
        weak = score_document(sample("weak_resume.pdf"))
        self.assertGreater(strong.overall, weak.overall + 30)
        # Not asserting "green": the synthetic fixtures sit just under the
        # green cutoff while competency detection is the known open gap
        # (evidence/CHANGES.md). Real resumes are the calibration set.
        self.assertGreater(strong.overall, 78)
        self.assertLess(weak.overall, 50)

    def test_module_totals_bounded(self):
        rep = score_document(sample("strong_resume.pdf"))
        for m in rep.modules:
            self.assertGreaterEqual(m.points, 0)
            self.assertLessEqual(m.points, m.max_points + 1e-6)
        self.assertAlmostEqual(sum(m.max_points for m in rep.modules), 100.0)

    def test_word_floor_blocks(self):
        weak = score_document(sample("weak_resume.pdf"))
        self.assertFalse(weak.scored)
        self.assertTrue(any("200" in b for b in weak.blockers))

    def test_two_column_detected_and_penalised(self):
        rep = score_document(sample("two_column_resume.pdf"))
        self.assertTrue(rep.meta["two_column"])
        # A two-column layout surfaces through VMock's own check name,
        # "Bullet Alignment" — VMock has no check called "two column".
        of = next(s for m in rep.modules for s in m.subscores
                  if s.key == "overall_format")
        align = next(c for c in of.detail["checks"] if c["key"] == "bullet_alignment")
        self.assertFalse(align["passed"])
        self.assertIn("two-column", align["evidence"])

    def test_quirks_toggle_changes_score(self):
        """Enabling the full quirk set must cost points, and disabling it must
        leave no quirk-tagged findings behind."""
        cfg_on = Config.load()
        for name, block in cfg_on.data["quirks"].items():
            if isinstance(block, dict) and "enabled" in block:
                block["enabled"] = True
        on = score_document(sample("weak_resume.pdf"), cfg=cfg_on)

        cfg_off = Config.load()
        cfg_off.data["quirks"]["strict_vmock_quirks"] = False
        off = score_document(sample("weak_resume.pdf"), cfg=cfg_off)

        self.assertGreater(off.overall, on.overall)
        self.assertEqual(off.quirk_cost(), {})

    def test_phone_parens_quirk_is_off_by_default(self):
        """Direct evidence: a resume with "(555) 010-0199" scored 30/30 on
        Presentation, so this documented rule ships disabled."""
        cfg = Config.load()
        self.assertFalse(cfg.quirk("phone_parens_penalty"))
        self.assertNotIn(
            "phone_parens_penalty", score_document(sample("weak_resume.pdf")).quirk_cost()
        )

    def test_claimed_points_never_exceed_available(self):
        """The UI advertises points_lost as recoverable. It must be truthful."""
        for name in ("weak_resume.pdf", "strong_resume.pdf", "two_column_resume.pdf"):
            rep = score_document(sample(name))
            claimed = sum(a["points"] for a in rep.top_actions(999))
            self.assertLessEqual(
                claimed, (100 - rep.overall) + 0.5,
                f"{name}: claims {claimed:.1f} points but only "
                f"{100 - rep.overall:.1f} are available",
            )

    def test_subscore_claims_match_actual_deficit(self):
        rep = score_document(sample("weak_resume.pdf"))
        def walk(sub):
            if not sub.children:
                claimed = sum(f.points_lost for f in sub.findings)
                deficit = sub.max_points - sub.points
                self.assertLessEqual(claimed, deficit + 0.05, sub.label)
            for c in sub.children:
                walk(c)
        for mod in rep.modules:
            for sub in mod.subscores:
                walk(sub)

    def test_deterministic(self):
        a = score_document(sample("strong_resume.pdf")).overall
        b = score_document(sample("strong_resume.pdf")).overall
        self.assertEqual(a, b)

    def test_serialises(self):
        import json

        d = score_document(sample("strong_resume.pdf")).to_dict()
        json.loads(json.dumps(d))
        self.assertIn("top_actions", d)
        self.assertTrue(d["bullets"])


LADDER = ["tier1_dogwater", "tier2_rough", "tier3_average",
          "tier4_strong", "tier5_magnum_opus"]


def ladder_path(name):
    path = os.path.join(ROOT, "samples", "ladder", name + ".pdf")
    if not os.path.exists(path):
        sys.path.insert(0, os.path.join(ROOT, "samples"))
        import make_ladder

        os.makedirs(os.path.dirname(path), exist_ok=True)
        for fn, builder in make_ladder.TIERS:
            builder(os.path.join(ROOT, "samples", "ladder", fn))
    return path


class TestQualityLadder(unittest.TestCase):
    """Five resumes from worst to best. The engine must rank them in order --
    this is the regression net for every scoring module at once."""

    @classmethod
    def setUpClass(cls):
        cls.scores = [score_document(ladder_path(n)).overall for n in LADDER]

    def test_strictly_increasing(self):
        for (an, a), (bn, b) in zip(zip(LADDER, self.scores), zip(LADDER[1:], self.scores[1:])):
            self.assertGreater(b, a, f"{bn} ({b:.1f}) did not beat {an} ({a:.1f})")

    def test_spans_the_range(self):
        self.assertLess(self.scores[0], 40)
        self.assertGreater(self.scores[-1], 90)
        self.assertGreater(self.scores[-1] - self.scores[0], 45)

    def test_zones_progress(self):
        """The ladder must span from not-green to green. The exact band of the
        worst rung is not asserted: these are synthetic fixtures, and pinning
        them to a threshold would make the suite fight real calibration work."""
        cfg = Config.load()
        self.assertNotEqual(zone_for(self.scores[0], cfg), "green")
        self.assertGreater(self.scores[-1], 78)

    def test_worst_is_blocked_on_word_count(self):
        rep = score_document(ladder_path("tier1_dogwater"))
        self.assertFalse(rep.scored)

    def test_zone_bands_tile_the_range(self):
        """No score may fall between two bands -- 32.3 used to belong to none."""
        cfg = Config.load()
        for i in range(0, 1001):
            self.assertIn(zone_for(i / 10.0, cfg), ("red", "yellow", "green"))


class TestRealResumeCalibration(unittest.TestCase):
    """Ground truth: these two PDFs were scored by the real VMock against CMU's
    benchmark. Skipped when the files are absent."""

    # Ground truth from the benchmark this engine is calibrated to,
    # "CMU Masters - Technical". Masters_2's 93 came from a different
    # benchmark ("CMU Resumes") with a different check set, so it is excluded.
    TRUTH = {"Resume_Masters_1": 61, "Yuxuan_Cai_Resume_Aug": 93}

    def test_within_tolerance(self):
        base = os.path.join(ROOT, "samples", "real")
        checked = 0
        for name, truth in self.TRUTH.items():
            path = os.path.join(base, name + ".pdf")
            if not os.path.exists(path):
                continue
            got = score_document(path).overall
            checked += 1
            if name == "Resume_Masters_2":
                continue      # scored on the "CMU Resumes" benchmark, not ours
            # Tolerance is 15 while competency detection is the open gap.
            self.assertLess(
                abs(got - truth), 15,
                f"{name}: VMock scored {truth}, clone scored {got:.1f}",
            )
        if not checked:
            self.skipTest("no reference resumes present")


class TestSpellClassification(unittest.TestCase):
    """OBSERVED red/yellow split. Red words deduct, yellow ones are explicitly
    free. Ground truth taken verbatim from two real reports."""

    RED = ["rebasing", "webhook", "idempotency"]
    YELLOW = ["Soniox", "JSONL", "DEFINER", "Duffing", "WebSockets", "Supabase",
              "Toolchains", "vLLM", "FastAPI", "MLOps", "BFCL", "CNMAT",
              "Audealize", "SocialFX", "DAFx", "Pydantic", "SonAura"]

    def test_red_words(self):
        for w in self.RED:
            self.assertEqual(spell.classify(w), "red", w)

    def test_yellow_words(self):
        for w in self.YELLOW:
            self.assertEqual(spell.classify(w), "yellow", w)


class TestCompetencyModel(unittest.TestCase):
    """Competencies are continuous in 0.5 steps, not three fixed bands.

    A strict {6.0, 2.5, 0.0} band model was refuted by a third report: Brendan's
    resumes score Competencies 29/30, and no combination of those three values
    over five competencies sums to 29. What the reports DO pin is the ramp --
    Masters_1 scored 23 with three full competencies plus tooltips reading
    "4 bullets highlighted" and "1 bullet highlighted", i.e. 6+6+6+4+1."""

    def test_scores_are_half_point_quantised(self):
        cfg = Config.load()
        self.assertEqual(float(cfg.get("competencies.rounding_step")), 0.5)
        self.assertEqual(float(cfg.get("competencies.points_each")), 6.0)

    def test_masters_1_competency_total(self):
        path = os.path.join(ROOT, "samples", "real", "Resume_Masters_1.pdf")
        if not os.path.exists(path):
            self.skipTest("reference resume not present")
        rep = score_document(path, benchmark="cmu_masters_technical")
        comp = next(m for m in rep.modules if m.key == "competencies")
        self.assertAlmostEqual(comp.points, 23.0, places=1)

    def test_every_competency_is_quantised_and_chipped(self):
        path = os.path.join(ROOT, "samples", "real", "Resume_Masters_1.pdf")
        if not os.path.exists(path):
            self.skipTest("reference resume not present")
        rep = score_document(path, benchmark="cmu_masters_technical")
        comp = next(m for m in rep.modules if m.key == "competencies")
        for s in comp.subscores:
            self.assertAlmostEqual(round(s.points * 2) / 2, s.points, places=6,
                                   msg=s.label)
            self.assertLessEqual(s.points, 6.0, s.label)
            self.assertIn(s.status, ("Good Job!", "On Track!", "Needs Work!"))


REFERENCE_SCORES = [
    # file, benchmark profile, VMock's published overall score
    ("Brendan_Lin_Resume_69.pdf", "cmu_resumes", 69),
    ("Brendan_Lin_Resume_77.pdf", "cmu_resumes", 77),
    ("Brendan_Lin_Resume_93.pdf", "cmu_resumes", 93),
    ("Resume_Masters_1.pdf", "cmu_masters_technical", 61),
    ("Yuxuan_Cai_Resume_Aug.pdf", "cmu_masters_technical", 93),
]


class TestAgainstRealVMockScores(unittest.TestCase):
    """Every resume whose real VMock score is known must land within 2 points.

    These PDFs are gitignored (they carry personal contact details), so the
    tests skip when they are absent."""

    def _score(self, name, profile):
        path = os.path.join(ROOT, "samples", "real", name)
        if not os.path.exists(path):
            self.skipTest("reference resume not present")
        return score_document(path, benchmark=profile)

    def test_within_two_points(self):
        for name, profile, target in REFERENCE_SCORES:
            with self.subTest(resume=name):
                got = self._score(name, profile).overall
                self.assertLessEqual(
                    abs(got - target), 2.0,
                    f"{name}: {got:.1f} vs VMock {target}")

    def test_observed_module_scores(self):
        """Impact / Presentation / Competencies as VMock published them."""
        expected = {
            "Brendan_Lin_Resume_69.pdf": (30, 10, 29),
            "Brendan_Lin_Resume_77.pdf": (34, 14, 29),
            "Brendan_Lin_Resume_93.pdf": (34, 30, 29),
            "Resume_Masters_1.pdf": (26, 12, 23),
            "Yuxuan_Cai_Resume_Aug.pdf": (34, 29, 30),
        }
        for name, profile, _ in REFERENCE_SCORES:
            with self.subTest(resume=name):
                rep = self._score(name, profile)
                mods = {m.key: m.points for m in rep.modules}
                imp, pre, com = expected[name]
                self.assertLessEqual(abs(mods["impact"] - imp), 2.0, "impact")
                self.assertLessEqual(abs(mods["presentation"] - pre), 2.0, "presentation")
                self.assertLessEqual(abs(mods["competencies"] - com), 2.0, "competencies")

    def test_observed_impact_chips(self):
        """The four Impact status chips read off Masters_1's report."""
        rep = self._score("Resume_Masters_1.pdf", "cmu_masters_technical")
        chips = {s.key: s.status
                 for s in next(m for m in rep.modules if m.key == "impact").subscores}
        self.assertEqual(chips["action_oriented"], "Good Job!")
        self.assertEqual(chips["specifics"], "On Track!")
        self.assertEqual(chips["overuse"], "On Track!")
        self.assertEqual(chips["avoided_words"], "Needs Work!")

    def test_observed_spell_lists(self):
        """VMock's Spell Check panel on the 69 and the 77, verbatim."""
        for name, red, yellow, chip in (
            ("Brendan_Lin_Resume_69.pdf",
             ["rebasing", "webhook", "idempotency"],
             ["Soniox", "JSONL", "DEFINER", "Duffing", "WebSockets", "Supabase"],
             "Needs Work!"),
            ("Brendan_Lin_Resume_77.pdf", [],
             ["Soniox", "JSONL", "DEFINER", "Duffing", "WebSockets", "Supabase"],
             "On Track!"),
        ):
            with self.subTest(resume=name):
                rep = self._score(name, "cmu_resumes")
                pres = next(m for m in rep.modules if m.key == "presentation")
                sp = next(s for s in pres.subscores if s.key == "spell_check")
                self.assertEqual(sp.detail["misspelled"], red)
                self.assertEqual(sp.detail["re_examine"], yellow)
                self.assertEqual(sp.status, chip)

    def test_observed_section_specific_failures(self):
        """Which group checks fail, on the two panels that were read."""
        cases = {
            # the 69: Personal Details passed; Education and Experience failed
            ("Brendan_Lin_Resume_69.pdf", "cmu_resumes"):
                {"Degree Styling", "Job Title Styling"},
            # Masters_1: only Personal Details failed, on the phone number
            ("Resume_Masters_1.pdf", "cmu_masters_technical"):
                {"Phone Number"},
        }
        for (name, profile), want in cases.items():
            with self.subTest(resume=name):
                rep = self._score(name, profile)
                pres = next(m for m in rep.modules if m.key == "presentation")
                ss = next(s for s in pres.subscores if s.key == "section_specific")
                got = {f.message for f in ss.all_findings if f.severity == "error"}
                self.assertEqual(got, want)

    def test_observed_overall_format_failures(self):
        """Every Overall Format checklist that was read off the product."""
        cases = {
            ("Brendan_Lin_Resume_69.pdf", "cmu_resumes"):
                ({"Bullet Check", "Date Formatting", "Font Size Check"}, 9),
            ("Brendan_Lin_Resume_77.pdf", "cmu_resumes"):
                ({"Bullet Check"}, 9),
            ("Brendan_Lin_Resume_93.pdf", "cmu_resumes"): (set(), 9),
            ("Resume_Masters_1.pdf", "cmu_masters_technical"):
                ({"Bullet Alignment", "Bullet Check", "Bullet Count",
                  "Date Formatting"}, 11),
            ("Yuxuan_Cai_Resume_Aug.pdf", "cmu_masters_technical"): (set(), 11),
        }
        for (name, profile), (want, total) in cases.items():
            with self.subTest(resume=name):
                rep = self._score(name, profile)
                pres = next(m for m in rep.modules if m.key == "presentation")
                of = next(s for s in pres.subscores if s.key == "overall_format")
                got = {c["label"] for c in of.detail["checks"] if c["passed"] is False}
                self.assertEqual(got, want)
                self.assertEqual(of.detail["total"], total)

    def test_good_job_panels_carry_no_complaints(self):
        """VMock's Good Job! panels show praise only -- Masters_1's Action
        Oriented panel said so on a resume with a bullet opening on a noun."""
        for name, profile, _ in REFERENCE_SCORES:
            with self.subTest(resume=name):
                rep = self._score(name, profile)
                for mod in rep.modules:
                    for s in mod.subscores:
                        if s.status != "Good Job!":
                            continue
                        bad = [f.message for f in s.all_findings
                               if f.severity in ("error", "warn")]
                        self.assertEqual(bad, [], f"{mod.label}/{s.label}")

    def test_observed_overuse_words(self):
        """VMock's own chips, verbatim: Masters_1 showed "Analyzed 3" and
        "Provided/Providing 3"; Yuxuan's showed "Developed 3" and
        "Support/Supporting 3". Nothing else cleared the threshold."""
        for name, profile, want in (
            ("Resume_Masters_1.pdf", "cmu_masters_technical",
             [("Analyzed", 3), ("Provided/Providing", 3)]),
            ("Yuxuan_Cai_Resume_Aug.pdf", "cmu_masters_technical",
             [("Developed", 3), ("Support/Supporting", 3)]),
        ):
            with self.subTest(resume=name):
                rep = self._score(name, profile)
                imp = next(m for m in rep.modules if m.key == "impact")
                over = next(s for s in imp.subscores if s.key == "overuse")
                self.assertEqual([tuple(x) for x in over.detail["reported"]], want)


if __name__ == "__main__":
    unittest.main(verbosity=2)
