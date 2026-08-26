"""Generate test resumes with reportlab so the engine can be exercised end-to-end.

  python3 samples/make_samples.py
"""
import os
import sys

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = LETTER


class Sheet:
    def __init__(self, path, margin=72, body=10.5, leading=13.0):
        self.c = canvas.Canvas(path, pagesize=LETTER)
        self.m = margin
        self.body = body
        self.leading = leading
        self.y = H - margin

    def _nl(self, amount=None):
        self.y -= amount if amount is not None else self.leading

    def name(self, text, size=18):
        self.c.setFont("Helvetica-Bold", size)
        self.c.drawCentredString(W / 2, self.y, text)
        self._nl(size + 6)

    def contact(self, text, size=9.5):
        self.c.setFont("Helvetica", size)
        self.c.drawCentredString(W / 2, self.y, text)
        self._nl(size + 6)

    def heading(self, text, gap_before=10, rule=True, size=11):
        self._nl(gap_before)
        self.c.setFont("Helvetica-Bold", size)
        self.c.drawString(self.m, self.y, text.upper())
        if rule:
            self.c.setLineWidth(0.6)
            self.c.line(self.m, self.y - 3, W - self.m, self.y - 3)
        self._nl(size + 5)

    def entry(self, left, right=None, bold_left=True, size=None):
        size = size or self.body
        self.c.setFont("Helvetica-Bold" if bold_left else "Helvetica", size)
        self.c.drawString(self.m, self.y, left)
        if right:
            self.c.setFont("Helvetica", size)
            self.c.drawRightString(W - self.m, self.y, right)
        self._nl(size + 3)

    def sub(self, left, right=None, size=None):
        size = size or self.body
        self.c.setFont("Helvetica-Oblique", size)
        self.c.drawString(self.m, self.y, left)
        if right:
            self.c.setFont("Helvetica", size)
            self.c.drawRightString(W - self.m, self.y, right)
        self._nl(size + 3)

    def bullet(self, text, glyph="•", indent=12, size=None):
        size = size or self.body
        self.c.setFont("Helvetica", size)
        maxw = W - 2 * self.m - indent
        words, line = text.split(), ""
        first = True
        for w in words:
            trial = (line + " " + w).strip()
            if self.c.stringWidth(trial, "Helvetica", size) > maxw and line:
                self._draw_bullet_line(line, glyph if first else None, indent, size)
                first, line = False, w
            else:
                line = trial
        if line:
            self._draw_bullet_line(line, glyph if first else None, indent, size)

    def _draw_bullet_line(self, text, glyph, indent, size):
        x = self.m + indent
        if glyph:
            self.c.drawString(self.m + 4, self.y, glyph)
        self.c.drawString(x, self.y, text)
        self._nl(size + 2.5)

    def plain(self, text, size=None):
        size = size or self.body
        self.c.setFont("Helvetica", size)
        self.c.drawString(self.m, self.y, text)
        self._nl(size + 3)

    def page_break(self):
        self.c.showPage()
        self.y = H - self.m

    def save(self):
        self.c.save()


def weak(path):
    s = Sheet(path, margin=72, body=10.5)
    s.name("Jordan Avery")
    s.contact("(415) 555-0182  |  Jordan.Avery@Example.COM  |  San Francisco")
    s.heading("Objective")
    s.plain("A motivated and detail-oriented self-starter seeking to leverage my skills.")
    s.heading("Education")
    s.entry("State University", "Sept 2021-May 2025")
    s.sub("Bachelor of Science, Business Administration")
    s.heading("Work Experience")
    s.entry("Retail Corp", "June-August 2023")
    s.sub("Sales Associate Intern")
    s.bullet("Responsible for helping customers with various questions on a daily basis.")
    s.bullet("Worked with the team to make sure that the store was organized.")
    s.bullet("Helped to successfully complete several different tasks as needed.")
    s.bullet("Was able to assist with inventory that was received from the warehouse.")
    s.bullet("Participated in meetings where I provided some feedback to my manager.")
    s.bullet("Used the register.", glyph="-")
    s.entry("Campus Cafe", "2022")
    s.sub("Barista")
    s.bullet("Worked as a barista and helped to serve many customers each shift.")
    s.bullet("Assisted with various duties including cleaning and restocking supplies.")
    s.heading("Leadership and Activities")
    s.entry("Business Club", "2022-2024")
    s.bullet("Member of the club and attended the meetings that were held weekly.")
    s.heading("Skills")
    s.plain("Microsoft Word, Excel, Powerpoint, teamwork, communication, hardworking")
    s.page_break()
    s.plain("References available upon request.")
    s.save()


def strong(path):
    s = Sheet(path, margin=54, body=10)
    s.name("Riley Chen", size=16)
    s.contact("riley.chen@example.com | 415-555-0182 | San Francisco, CA | linkedin.com/in/rileychen")
    s.heading("Education", gap_before=6)
    s.entry("Carnegie Mellon University", "Expected May 2027")
    s.sub("M.S. in Data Science; GPA: 3.9/4.0")
    s.plain("Relevant Coursework: Machine Learning, Statistical Inference, Optimization, Databases")
    s.entry("University of British Columbia", "Sep 2019 - May 2023")
    s.sub("B.Sc. in Statistics, First Class Honours; GPA: 3.8/4.0")
    s.heading("Experience")
    s.entry("Northwind Analytics", "May 2024 - Aug 2024")
    s.sub("Data Science Intern", "Toronto, ON")
    s.bullet("Engineered a churn-prediction pipeline in Python and SQL across 2.4M customer records, lifting AUC from 0.71 to 0.86.")
    s.bullet("Automated 14 weekly reporting workflows with Airflow, cutting analyst effort by 22 hours per week.")
    s.bullet("Presented model findings to 3 executive stakeholders, securing approval for a $450K retention pilot.")
    s.entry("Vector Labs", "Sep 2023 - Apr 2024")
    s.sub("Research Assistant", "Vancouver, BC")
    s.bullet("Designed 6 controlled experiments evaluating transformer compression, reducing inference latency 38%.")
    s.bullet("Co-authored a paper accepted at a peer-reviewed workshop and mentored 2 junior researchers.")
    s.heading("Leadership & Activities")
    s.entry("Data Science Society", "Sep 2022 - May 2023")
    s.sub("President")
    s.bullet("Led a team of 12 organizers and grew active membership from 80 to 310 within two semesters.")
    s.bullet("Negotiated 4 corporate sponsorships totaling $18K to fund a 200-attendee analytics conference.")
    s.entry("Department of Statistics", "Jan 2023 - Apr 2023")
    s.sub("Teaching Assistant", "Vancouver, BC")
    s.bullet("Taught 3 weekly lab sections of 40 students and raised median assignment scores by 11 points.")
    s.bullet("Rebuilt the grading rubric in R, cutting marking time per assignment from 90 to 35 minutes.")
    s.heading("Skills")
    s.plain("Languages: Python, R, SQL, Scala | Tools: PyTorch, Spark, Airflow, dbt, Tableau, Docker, AWS")
    s.plain("Certifications: AWS Certified Data Analytics | Interests: competitive rowing, open-source contribution")
    s.save()


def two_column(path):
    c = canvas.Canvas(path, pagesize=LETTER)
    m = 54
    gut = W * 0.38
    y = H - m
    c.setFont("Helvetica-Bold", 16)
    c.drawString(m, y, "Sam Rivera")
    y -= 24
    left_y = right_y = y
    c.setFont("Helvetica-Bold", 10)
    c.drawString(m, left_y, "CONTACT")
    left_y -= 14
    c.setFont("Helvetica", 9)
    for t in ["sam@example.com", "555-0100", "Boston, MA", "linkedin.com/in/sam"]:
        c.drawString(m, left_y, t)
        left_y -= 12
    left_y -= 10
    c.setFont("Helvetica-Bold", 10)
    c.drawString(m, left_y, "SKILLS")
    left_y -= 14
    c.setFont("Helvetica", 9)
    for t in ["Python", "SQL", "Tableau", "Excel", "Communication"]:
        c.drawString(m, left_y, t)
        left_y -= 12
    c.setFont("Helvetica-Bold", 10)
    c.drawString(gut + 20, right_y, "EXPERIENCE")
    right_y -= 14
    c.setFont("Helvetica", 9)
    for t in [
        "Analyst, Acme Corp, 2023 - Present",
        "Built dashboards used by 40 staff.",
        "Analyzed 12K rows of sales data weekly.",
        "Intern, Beta LLC, Jun 2022 - Aug 2022",
        "Supported the finance team with reports.",
        "Created 5 monthly summaries for leadership.",
    ]:
        c.drawString(gut + 20, right_y, t)
        right_y -= 12
    right_y -= 10
    c.setFont("Helvetica-Bold", 10)
    c.drawString(gut + 20, right_y, "EDUCATION")
    right_y -= 14
    c.setFont("Helvetica", 9)
    c.drawString(gut + 20, right_y, "B.A. Economics, 2023")
    c.save()


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else HERE
    weak(os.path.join(out, "weak_resume.pdf"))
    strong(os.path.join(out, "strong_resume.pdf"))
    two_column(os.path.join(out, "two_column_resume.pdf"))
    print("wrote weak_resume.pdf, strong_resume.pdf, two_column_resume.pdf ->", out)
