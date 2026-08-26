"""Score every resume whose real VMock result we know, and print the error.

    python3 tools/anchors.py            # the working tree
    python3 tools/anchors.py /some/copy # an experiment

Each resume is scored under the SAME benchmark profile VMock rated it on;
scoring them all under the default profile silently misreports two of them.

KNOWN REMAINING GAP: Ziqi's Impact reads ~6 points below VMock's 34. That is
not a weighting problem -- it is provably unfittable. Brendan_77 and Ziqi both
score Impact 34 at VMock, but Ziqi is strictly worse than Brendan_77 on three
of our sub-parameters and equal on the other two, so no non-negative weighting
can put them level. Subtracting the two constraints leaves
    0.071*action + 0.442*specifics + 0.167*overuse = 0
which forces all three weights to zero. Our Specifics measure (share of
bullets carrying a number: Ziqi 0.10, Brendan_93 0.64) is therefore not what
VMock's Specifics measures -- VMock called Ziqi's "On Track!". Closing this
needs a different Specifics definition, not a re-fit.
"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 else "/Users/brendanlin04/Desktop/VMOCK Clone/bmock"
sys.path.insert(0, ROOT); os.chdir(ROOT)
from vmock_clone.core import Config
from vmock_clone.scoring import score_document

# Ziqi is on cmu_resumes, not masters-technical: her VMock panel shows the
# Extra-curriculars sub-parameter, which rules.yaml records as present on
# "CMU Resumes" and absent on "CMU Masters - Technical".
ANCHORS = [
    ("samples/real/Brendan_Lin_Resume_69.pdf", "cmu_resumes",           69, 30, 10, 29),
    ("samples/real/Brendan_Lin_Resume_77.pdf", "cmu_resumes",           77, 34, 14, 29),
    ("samples/real/Brendan_Lin_Resume_93.pdf", "cmu_resumes",           93, 34, 30, 29),
    ("samples/real/Resume_Masters_1.pdf",      "cmu_masters_technical", 61, 26, 12, 23),
    ("samples/real/Yuxuan_Cai_Resume_Aug.pdf", "cmu_masters_technical", 93, 34, 29, 30),
    ("samples/real/Ziqi_Geng_Resume_66.pdf",   "cmu_resumes",           66, 34, 11, 21),
    ("/Users/brendanlin04/Downloads/resumes/Ryan_Cho_Resume.pdf", "cmu_resumes", 88, None, None, None),
]

print(f"{'resume':<28} {'profile':<22} {'overall':>14} {'Impact':>13} {'Present.':>13} {'Compet.':>13}")
print("-" * 106)
errs = []
for path, profile, o, i, p, c in ANCHORS:
    if not os.path.exists(path):
        print(f"{os.path.basename(path):<28}  MISSING"); continue
    r = score_document(path, cfg=Config.load(None), benchmark=profile)
    got = {m.key: m.points for m in r.modules}
    def cell(a, t):
        if t is None: return f"{a:>6.1f}       "
        errs.append(abs(a - t)); return f"{a:>6.1f} ({a-t:+5.1f})"
    print(f"{os.path.basename(path):<28} {profile:<22} {cell(r.overall,o):>14} "
          f"{cell(got.get('impact',0),i):>13} {cell(got.get('presentation',0),p):>13} {cell(got.get('competencies',0),c):>13}")
print("-" * 106)
print(f"  mean abs error {sum(errs)/len(errs):.2f}   worst {max(errs):.1f}   ({len(errs)} measured values)")
