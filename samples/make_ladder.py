"""
Five resumes spanning the full quality range, for validating the score ladder.

    python3 samples/make_ladder.py

Each tier is a deliberate, specific set of defects (or their absence) so a
regression in any one scoring module shows up as a broken rung.

  1 dogwater   two pages, no dates, "Responsible for", zero numbers, four
               bullet glyphs, typos, Objective + References, 3 fonts
  2 rough      structure exists, weak verbs, almost no quantification
  3 average    reasonable one-pager, some numbers, thin competency spread
  4 strong     quantified, strong verbs, clean format, minor gaps
  5 magnum     every competency facet, heavy quantification, flawless format
"""
import os
import sys

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = LETTER


class Sheet:
    def __init__(self, path, margin=54, body=10.0, leading=12.0, name_size=16):
        self.c = canvas.Canvas(path, pagesize=LETTER)
        self.m, self.body, self.leading, self.name_size = margin, body, leading, name_size
        self.y = H - margin

    def nl(self, n=None):
        self.y -= self.leading if n is None else n

    def name(self, text, size=None, center=True):
        size = size or self.name_size
        self.c.setFont("Helvetica-Bold", size)
        (self.c.drawCentredString(W / 2, self.y, text) if center
         else self.c.drawString(self.m, self.y, text))
        self.nl(size + 6)

    def contact(self, text, size=9.0, center=True):
        self.c.setFont("Helvetica", size)
        (self.c.drawCentredString(W / 2, self.y, text) if center
         else self.c.drawString(self.m, self.y, text))
        self.nl(size + 7)

    def heading(self, text, gap=9, rule=True, size=11, caps=True):
        self.nl(gap)
        self.c.setFont("Helvetica-Bold", size)
        self.c.drawString(self.m, self.y, text.upper() if caps else text)
        if rule:
            self.c.setLineWidth(0.6)
            self.c.line(self.m, self.y - 3, W - self.m, self.y - 3)
        self.nl(size + 5)

    def entry(self, left, right=None, size=None, bold=True):
        size = size or self.body
        self.c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        self.c.drawString(self.m, self.y, left)
        if right:
            self.c.setFont("Helvetica", size)
            self.c.drawRightString(W - self.m, self.y, right)
        self.nl(size + 3)

    def sub(self, left, right=None, size=None):
        size = size or self.body
        self.c.setFont("Helvetica-Oblique", size)
        self.c.drawString(self.m, self.y, left)
        if right:
            self.c.setFont("Helvetica", size)
            self.c.drawRightString(W - self.m, self.y, right)
        self.nl(size + 3)

    def bullet(self, text, glyph="•", indent=12, size=None, font="Helvetica"):
        size = size or self.body
        self.c.setFont(font, size)
        maxw = W - 2 * self.m - indent
        line, first = "", True
        for w in text.split():
            trial = (line + " " + w).strip()
            if self.c.stringWidth(trial, font, size) > maxw and line:
                self._draw(line, glyph if first else None, indent, size, font)
                first, line = False, w
            else:
                line = trial
        if line:
            self._draw(line, glyph if first else None, indent, size, font)

    def _draw(self, text, glyph, indent, size, font):
        self.c.setFont(font, size)
        if glyph:
            self.c.drawString(self.m + 3, self.y, glyph)
        self.c.drawString(self.m + indent, self.y, text)
        self.nl(size + 2.5)

    def plain(self, text, size=None, font="Helvetica"):
        size = size or self.body
        self.c.setFont(font, size)
        self.c.drawString(self.m, self.y, text)
        self.nl(size + 3)

    def page_break(self):
        self.c.showPage()
        self.y = H - self.m

    def save(self):
        self.c.save()


# ---------------------------------------------------------------- tier 1
def tier1(path):
    s = Sheet(path, margin=20, body=12.5, leading=15)
    s.name("jordan  b.", size=13, center=False)
    s.contact("(555) 867-5309 / JORDAN.B.THE.GOAT@Example.COM", size=11, center=False)
    s.heading("Objective", rule=False, size=13)
    s.plain("Motivated hard-working team player seeking a opportunity to leverage my skills "
            "and grow.", size=12.5)
    s.heading("Work Stuff", rule=False, size=13)
    s.entry("burger place", bold=False, size=12.5)
    s.bullet("Responsible for the register and various other duties as needed.", glyph="-")
    s.bullet("Worked with the team on a daily basis to make sure things got done.", glyph="*")
    s.bullet("Helped out.", glyph=">")
    s.bullet("Was responsible for cleaning that was required at closing time.", glyph="•")
    s.entry("lawn mowing", bold=False, size=12.5)
    s.bullet("Did lawns for the neighbourhood, and also some other tasks.", glyph="-")
    s.bullet("Recieved good feedback from the customers that I had.", glyph="*")
    s.heading("Skills", rule=False, size=13)
    s.plain("Microsoft Word, hard worker, team player, fast learner, Pnotoshop", size=12.5)
    s.page_break()
    s.plain("References available upon request", size=12.5)
    s.save()


# ---------------------------------------------------------------- tier 2
def tier2(path):
    s = Sheet(path, margin=58, body=10.5)
    s.name("Alex Rivera")
    s.contact("alex.rivera@example.com | 614-555-0142 | Columbus, OH")
    s.heading("Education")
    s.entry("Ohio State University", "2021 - 2025")
    s.sub("Bachelor of Arts, Communications")
    s.heading("Experience")
    s.entry("Campus Bookstore", "2023")
    s.sub("Student Assistant")
    s.bullet("Assisted customers with finding textbooks and answering their questions.")
    s.bullet("Worked with other staff members to keep the shelves organized and tidy.")
    s.bullet("Helped process returns during the busy period at the start of term.")
    s.entry("Local Newspaper", "2022")
    s.sub("Editorial Intern")
    s.bullet("Wrote articles for the student section on a weekly basis.")
    s.bullet("Attended editorial meetings and provided input on story ideas.")
    s.heading("Leadership and Activities")
    s.entry("Debate Club", "2022 - 2024")
    s.bullet("Participated in debates and helped organize practice sessions.")
    s.heading("Skills")
    s.plain("Microsoft Office, Google Workspace, writing, communication, teamwork")
    s.save()


# ---------------------------------------------------------------- tier 3
def tier3(path):
    s = Sheet(path, margin=54, body=10.0)
    s.name("Morgan Patel")
    s.contact("morgan.patel@example.com | 512-555-0188 | Austin, TX | linkedin.com/in/morganpatel")
    s.heading("Education")
    s.entry("University of Texas at Austin", "Aug 2021 - May 2025")
    s.sub("B.B.A. in Marketing; GPA: 3.5/4.0")
    s.plain("Relevant Coursework: Marketing Analytics, Consumer Behavior, Business Statistics")
    s.heading("Experience")
    s.entry("Brightpath Agency", "Jun 2024 - Aug 2024")
    s.sub("Marketing Intern", "Austin, TX")
    s.bullet("Managed client social accounts and helped grow the combined following over the summer")
    s.bullet("Built weekly performance reports in Excel and shared findings with the account team")
    s.bullet("Coordinated a product launch email sequence sent to 4,000 subscribers")
    s.entry("Campus Recreation Center", "Sep 2022 - May 2024")
    s.sub("Front Desk Supervisor", "Austin, TX")
    s.bullet("Supervised student staff and handled the weekend shift schedule")
    s.bullet("Resolved member issues at a busy front desk during peak hours")
    s.heading("Leadership & Activities")
    s.entry("American Marketing Association", "Sep 2023 - May 2025")
    s.sub("Events Chair")
    s.bullet("Organized speaker events and worked on increasing student attendance")
    s.heading("Skills")
    s.plain("Tools: Excel, Tableau, Google Analytics, HubSpot, Canva")
    s.save()


# ---------------------------------------------------------------- tier 4
def tier4(path):
    s = Sheet(path, margin=50, body=10.0)
    s.name("Priya Raman", size=15)
    s.contact("priya.raman@example.com | 206-555-0164 | Seattle, WA | linkedin.com/in/priyaraman")
    s.heading("Education")
    s.entry("University of Washington", "Sep 2021 - Jun 2025")
    s.sub("B.S. in Informatics, Data Science track; GPA: 3.8/4.0")
    s.plain("Relevant Coursework: Machine Learning, Databases, Statistical Inference, Algorithms")
    s.heading("Experience")
    s.entry("Cascade Analytics", "Jun 2024 - Sep 2024")
    s.sub("Data Analyst Intern", "Seattle, WA")
    s.bullet("Automated a manual reporting workflow in Python and SQL, cutting turnaround from 6 hours to 20 minutes across 12 weekly reports")
    s.bullet("Analyzed 340,000 support tickets to identify 3 drivers of churn, informing a retention plan adopted by the customer success team")
    s.bullet("Presented findings to stakeholders and supported analysts on the new Tableau dashboard")
    s.entry("UW Information School", "Jan 2024 - Jun 2024")
    s.sub("Undergraduate Research Assistant", "Seattle, WA")
    s.bullet("Designed and ran 4 user studies with 60 participants, improving task completion rates by 22%")
    s.bullet("Co-authored a workshop paper and mentored first-year students through their first analysis.")
    s.heading("Leadership & Activities")
    s.entry("Women in Informatics", "September 2023 - June 2025")
    s.sub("Vice President")
    s.bullet("Led a team of 9 officers and grew membership from 120 to 275 across two academic years")
    s.bullet("Negotiated 3 corporate sponsorships totaling $12,000 to fund a 150-person career night")
    s.heading("Skills")
    s.plain("Languages: Python, SQL, R | Tools: Tableau, Airflow, Git, AWS, Excel")
    s.save()


# ---------------------------------------------------------------- tier 5
def tier5(path):
    s = Sheet(path, margin=48, body=9.8)
    s.name("Dana Okonkwo", size=15)
    s.contact("dana.okonkwo@example.com | 617-555-0119 | Boston, MA | linkedin.com/in/danaokonkwo | github.com/danaok")
    s.heading("Education")
    s.entry("Massachusetts Institute of Technology", "Sep 2023 - Jun 2025")
    s.sub("M.Eng. in Operations Research; GPA: 4.0/4.0")
    s.plain("Relevant Coursework: Optimization, Machine Learning, Statistical Inference, Databases, Econometrics")
    s.entry("Boston University", "Sep 2019 - May 2023")
    s.sub("B.S. in Industrial Engineering, summa cum laude; GPA: 3.9/4.0")
    s.heading("Experience")
    s.entry("Meridian Logistics", "Jun 2024 - Aug 2024")
    s.sub("Operations Research Intern", "Boston, MA")
    s.bullet("Engineered a mixed-integer routing optimizer in Python and Gurobi across 1,400 daily shipments, cutting fuel cost 14% and saving $2.1M annualized")
    s.bullet("Automated the nightly forecasting pipeline with Airflow and dbt, reducing analyst effort 31 hours per week and eliminating 4 recurring data-quality incidents")
    s.bullet("Negotiated scope with 3 regional directors and presented the rollout plan to the COO, securing approval for a 9-site pilot")
    s.entry("Harborline Health", "Jan 2024 - May 2024")
    s.sub("Data Science Consultant", "Cambridge, MA")
    s.bullet("Built a readmission-risk model in scikit-learn on 210,000 records, lifting AUC from 0.68 to 0.84 and flagging 1,900 high-risk patients per quarter")
    s.bullet("Coached 5 clinical staff through the dashboard rollout and authored the 24-page handover documentation still in use")
    s.bullet("Partnered with 3 nursing units and the IT service desk to resolve 40 escalated data requests, cutting average response time from 5 days to 8 hours")
    s.entry("Boston University Department of Statistics", "Sep 2022 - May 2023")
    s.sub("Head Teaching Assistant", "Boston, MA")
    s.bullet("Led a team of 7 teaching assistants and redesigned the grading rubric, cutting marking time per assignment from 85 to 30 minutes")
    s.bullet("Taught 4 weekly lab sections of 45 students and raised median exam scores 11 points year over year")
    s.heading("Leadership & Activities")
    s.entry("MIT Operations Research Society", "Sep 2023 - Jun 2025")
    s.sub("President")
    s.bullet("Founded a mentorship program pairing 60 undergraduates with 40 industry mentors across 2 cohorts")
    s.bullet("Orchestrated a 300-attendee conference and raised $47,000 from 6 corporate sponsors, a 92% increase over the prior year")
    s.bullet("Planned the two-year strategic roadmap with 4 faculty advisors and coordinated logistics across 12 collaborating student societies")
    s.heading("Skills")
    s.plain("Languages: Python, R, SQL, Julia | Tools: Gurobi, PyTorch, Airflow, dbt, Tableau, Docker, AWS")
    s.save()


TIERS = [
    ("tier1_dogwater.pdf", tier1),
    ("tier2_rough.pdf", tier2),
    ("tier3_average.pdf", tier3),
    ("tier4_strong.pdf", tier4),
    ("tier5_magnum_opus.pdf", tier5),
]

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "ladder")
    os.makedirs(out, exist_ok=True)
    for fn, builder in TIERS:
        builder(os.path.join(out, fn))
        print("  wrote", fn)
