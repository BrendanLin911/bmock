"""
Hand-built lexicons. This file is the knowledge base of the scoring engine.

Nothing here is learned or generated. Every list was compiled from published
VMock rule documentation (Boston University College of Engineering's "How to
Improve Your VMock Score", the University of Windsor tip sheet, VMock's own
SMART Editor guides and blog) plus standard NACE competency taxonomy.

VMock's patent describes exactly this structure: "a weighted action verb
repository", "over 10,000 skills with corresponding keywords, phrases,
patterns" mapped to competencies, and job-role to function mappings.
"""

# ---------------------------------------------------------------------------
# ACTION VERBS - weighted repository
# ---------------------------------------------------------------------------
# VMock: "strong action verbs have higher weights". Stored as base forms; the
# matcher also accepts -ed / -d / -ing inflections.

STRONG_VERBS = {
    "accelerate", "architect", "automate", "champion", "consolidate", "convert",
    "cut", "decrease", "deliver", "double", "drive", "eliminate", "engineer",
    "expand", "expedite", "generate", "grow", "increase", "initiate", "innovate",
    "institute", "launch", "maximize", "minimize", "modernize", "negotiate",
    "optimize", "orchestrate", "outperform", "overhaul", "pioneer", "quantify",
    "rearchitect", "rebuild", "redesign", "reduce", "reengineer", "restructure",
    "revamp", "save", "scale", "secure", "shape", "slash", "spearhead",
    "standardize", "streamline", "strengthen", "surpass", "transform", "triple",
    "unify", "win", "accelerated", "capture", "close", "found", "merge",
    "prototype", "resolve", "salvage", "turnaround", "validate", "yield",
    # added after benchmarking against real VMock output, which recognises a
    # far wider verb repository than the published guides list
    "own", "owned", "rank", "replace", "rearchitected", "eliminate", "halve",
    "quadruple", "outpace", "unblock", "de-risk", "harden", "instrument",
    "productionize", "operationalize", "monetize", "commercialize", "land",
    "ship", "deliver", "exceed", "beat", "rescue", "recover", "reclaim",
    "unify", "consolidate", "decouple", "parallelize", "vectorize", "cache",
    "index", "compress", "amplify", "boost", "elevate", "propel", "spark",
    "seed", "bootstrap", "found", "cofound", "co-found", "incubate",
    "arbitrate", "broker", "underwrite", "syndicate", "raise", "fund",
    # found missing while diffing against real VMock output
    "achieve", "attain", "realize", "surpass", "exceed", "outperform",
    "secure", "clinch", "earn", "deliver", "drive", "propel", "unlock",
}

STANDARD_VERBS = {
    "administer", "advise", "analyze", "apply", "arrange", "assemble", "assess",
    "audit", "author", "benchmark", "budget", "build", "calculate", "chart",
    "clarify", "classify", "coach", "code", "collaborate", "compile", "complete",
    "compose", "compute", "conduct", "configure", "construct", "consult",
    "coordinate", "craft", "create", "debug", "define", "delegate", "deploy",
    "design", "detect", "determine", "develop", "devise", "diagnose", "direct",
    "document", "draft", "edit", "educate", "employ", "enable", "encourage",
    "enforce", "enhance", "establish", "estimate", "evaluate", "examine",
    "execute", "exercise", "extract", "facilitate", "forecast", "formulate",
    "gather", "guide", "identify", "illustrate", "implement", "improve",
    "influence", "inform", "inspect", "install", "instruct", "integrate",
    "interpret", "interview", "introduce", "investigate", "lead", "lecture",
    "leverage", "maintain", "manage", "map", "market", "measure", "mediate",
    "mentor", "migrate", "model", "modify", "monitor", "motivate", "operate",
    "organize", "outline", "oversee", "partner", "perform", "persuade", "pilot",
    "plan", "predict", "prepare", "present", "prioritize", "process", "produce",
    "program", "promote", "propose", "publish", "recommend", "reconcile",
    "record", "recruit", "refine", "regulate", "reinforce", "report", "run",
    "represent", "research", "review", "revise", "schedule", "select",
    "simplify", "simulate", "solve", "specify", "structure", "study",
    "summarize", "supervise", "support", "survey", "synthesize", "teach",
    "test", "track", "train", "translate", "troubleshoot", "tutor", "update",
    "upgrade", "verify", "visualize", "write",
    # second pass: verbs that appear constantly on real resumes and were
    # missing, each one costing a bullet its entire Action Oriented score
    "set", "setup", "walk", "guide", "run", "ran", "handle", "own", "lead",
    "manage", "support", "maintain", "staff", "cover", "host", "moderate",
    "chair", "convene", "coach", "advise", "counsel", "mentor", "onboard",
    "orient", "brief", "debrief", "escalate", "triage", "resolve", "close",
    "reconcile", "balance", "post", "file", "submit", "process", "fulfil",
    "fulfill", "dispatch", "ship", "receive", "stock", "restock", "inventory",
    "merchandise", "upsell", "cross-sell", "quote", "invoice", "bill",
    "collect", "disburse", "allocate", "budget", "forecast", "project",
    "model", "simulate", "backtest", "validate", "calibrate", "tune",
    "refactor", "rewrite", "port", "migrate", "deploy", "release", "roll",
    "monitor", "alert", "log", "trace", "profile", "benchmark", "optimize",
    "scale", "provision", "configure", "administer", "patch", "upgrade",
    "secure", "audit", "review", "inspect", "verify", "certify", "comply",
    "draft", "revise", "proofread", "edit", "publish", "post", "curate",
    "catalog", "catalogue", "archive", "digitize", "transcribe", "annotate",
    "label", "clean", "wrangle", "merge", "join", "aggregate", "summarize",
    "segment", "cluster", "classify", "rank", "score", "predict", "infer",
    "estimate", "quantify", "measure", "sample", "survey", "poll",
    "interview", "observe", "record", "chart", "plot", "graph", "map",
    "present", "pitch", "demo", "demonstrate", "showcase", "exhibit",
    "negotiate", "liaise", "coordinate", "schedule", "book", "arrange",
    "organize", "organise", "plan", "prepare", "prep", "stage", "execute",
    "run", "operate", "oversee", "supervise", "delegate", "assign",
    "recruit", "hire", "interview", "evaluate", "appraise", "promote",
    "teach", "instruct", "lecture", "tutor", "facilitate", "lead",
    "translate", "interpret", "localize", "adapt", "customize", "tailor",
    "replace", "retire", "deprecate", "sunset", "archive", "consolidate",
    # third pass: openers that scored 0 on real resumes VMock rated
    # "Action Oriented - Good Job!", so VMock plainly recognises them
    "fit", "derive", "prove", "compare", "harmonize", "harmonise",
    "characterize", "characterise", "formulate", "parameterize",
}

WEAK_VERBS = {
    "aid", "assist", "attend", "attempt", "contribute", "cover", "deal",
    "engage", "experience", "familiarize", "follow", "get", "give", "go",
    "handle", "help", "involve", "join", "keep", "learn", "look", "make",
    "observe", "participate", "provide", "put", "receive", "serve", "shadow",
    "showcase", "take", "try", "use", "utilize", "volunteer", "work",
}

# Irregular past tenses. Without this, "Led", "Built", "Wrote" and "Taught"
# all fail to match their base forms and get scored as non-verbs.
IRREGULAR_PAST = {
    "led": "lead", "built": "build", "wrote": "write", "written": "write",
    "taught": "teach", "grew": "grow", "grown": "grow", "won": "win",
    "drove": "drive", "driven": "drive", "sold": "sell", "spoke": "speak",
    "chose": "choose", "held": "hold", "kept": "keep", "sent": "send",
    "brought": "bring", "bought": "buy", "caught": "catch", "cut": "cut",
    "set": "set", "put": "put", "made": "make", "met": "meet", "paid": "pay",
    "saw": "see", "took": "take", "gave": "give", "found": "find",
    "began": "begin", "begun": "begin", "rose": "rise", "fell": "fall",
    "spent": "spend", "left": "leave", "told": "tell", "ran": "run",
    "oversaw": "oversee", "overseen": "oversee", "rewrote": "rewrite",
    "outgrew": "outgrow", "rebuilt": "rebuild", "redid": "redo",
    "undertook": "undertake", "withdrew": "withdraw", "shrank": "shrink",
    "struck": "strike", "swept": "sweep", "taught_": "teach", "thought": "think",
    "understood": "understand", "upheld": "uphold", "dealt": "deal",
    "drew": "draw", "flew": "fly", "forecast": "forecast", "got": "get",
    "gotten": "get", "knew": "know", "known": "know", "shown": "show",
    "showed": "show", "spread": "spread", "stood": "stand", "won_": "win",
}

# Noun compounds that begin with something the verb list also contains.
# BU's guide calls these out by name: a bullet must not open with a noun phrase
# like "Market research on three firms" or "Poster presentation at ...".
NOUN_PHRASE_OPENERS = (
    "market research", "data analysis", "data entry", "poster presentation",
    "customer service", "team member", "project management", "quality assurance",
    "process improvement", "financial analysis", "business development",
    "social media", "event planning", "research assistant", "office administration",
    "sales support", "inventory management", "risk assessment", "content creation",
    "product management", "supply chain", "front desk", "help desk",
    "lab work", "field work", "case study", "cost analysis", "report writing",
    "code review", "software development", "web development", "machine learning",
    "guest lecture", "study group", "peer tutoring", "community outreach",
)

# Openers that score zero: not verbs at all.
NON_VERB_OPENERS = (
    "responsible for", "responsibilities included", "duties included",
    "duties involved", "tasked with", "in charge of", "was responsible",
    "worked as", "role involved", "job involved", "position involved",
    "helped to", "assisted with", "part of a team", "member of a team",
    "my role", "this role", "successfully completed",
)

# ---------------------------------------------------------------------------
# AVOIDED / FILLER WORDS
# ---------------------------------------------------------------------------
# BU's guide plus VMock's own blog. Tiered by how defensible the rule is.

FILLER_ADVERBS = {
    "successfully", "effectively", "efficiently", "actively", "independently",
    "significantly", "substantially", "greatly", "highly", "very", "really",
    "extremely", "quite", "truly", "basically", "essentially", "literally",
    "definitely", "certainly", "simply", "just", "also", "additionally",
    "furthermore", "moreover", "consistently", "constantly", "continuously",
    "proactively", "diligently", "carefully", "closely", "properly",
}

VAGUE_QUANTIFIERS = {
    "various", "several", "numerous", "many", "multiple", "some", "few",
    "different", "certain", "assorted", "countless", "lots", "plenty",
    "a number of", "a variety of", "wide range", "wide variety",
}

WEASEL_PHRASES = (
    "such as", "in order to", "as well as", "along with", "due to the fact",
    "with the goal of", "for the purpose of", "in the process of",
    "was able to", "were able to", "had the opportunity to", "including but",
    "on a daily basis", "on a regular basis", "as needed", "when necessary",
)

PRONOUNS = {
    "i", "me", "my", "mine", "myself", "we", "us", "our", "ours", "ourselves",
    "you", "your", "yours", "he", "him", "his", "she", "her", "hers", "they",
    "them", "their", "theirs", "it", "its",
}

# OBSERVED: VMock reports pronoun *phrases* as single items, e.g. "I am 3",
# "I will 1", "I have 1", alongside bare "I 7" and "My 4".
PRONOUN_PHRASES = (
    "i am", "i was", "i will", "i have", "i had", "i can", "i would",
    "my own", "we are", "we were", "we will", "we have",
)

# OBSERVED filler vocabulary. VMock's Avoided Words panel on Resume_Masters_1
# listed exactly:  "That 1"  "Have 1"  "The 5".
#
# Two independent observations say the indefinite articles are NOT on VMock's
# list, and this set is deliberately restricted to what was actually seen:
#
#   1. Masters_1 contains 6 "a" and 3 "an" and VMock listed neither, while it
#      did list "The 5".
#   2. Brendan's 69 -> 77 rewrite, made in response to VMock's own feedback,
#      deleted every "the" (11), "that" (3) and "their" (1) and left "a"
#      untouched (13 -> 14). VMock's Impact rose by exactly the +4 its
#      "Remove overused and filler words" step had promised.
#
# An earlier version of this file guessed at "a / an / which / there / here /
# this / these / those / then / than". Only the three below were ever read off
# the product, so only those three are counted.
ARTICLES_AND_CONNECTORS = {
    "the", "that", "have",
}

BUZZWORDS = {
    "synergy", "synergies", "leverage", "leveraging", "go-getter", "guru",
    "ninja", "rockstar", "wizard", "thought leader", "results-driven",
    "detail-oriented", "self-starter", "team player", "hard worker",
    "hard-working", "motivated", "passionate", "dynamic", "seasoned",
    "value-add", "best-in-class", "world-class", "cutting-edge", "outside the box",
}

# ---------------------------------------------------------------------------
# PASSIVE VOICE
# ---------------------------------------------------------------------------
BE_VERBS = {"am", "is", "are", "was", "were", "be", "been", "being", "get", "got"}

IRREGULAR_PARTICIPLES = {
    "given", "taken", "written", "chosen", "driven", "shown", "known", "grown",
    "seen", "done", "made", "built", "sent", "kept", "held", "led", "run",
    "brought", "bought", "taught", "caught", "found", "won", "put", "set",
    "spent", "told", "left", "met", "read", "paid", "sold", "beaten", "broken",
    "spoken", "awarded", "selected", "assigned", "promoted", "hired", "tasked",
}

# ---------------------------------------------------------------------------
# COMPETENCIES - NACE-aligned, five buckets with named facets.
# ---------------------------------------------------------------------------
# Facet structure follows the taxonomy BU publishes for VMock. Full credit
# needs evidence across distinct facets, not one word repeated.

COMPETENCY_LEXICON = {
    "analytical": {
        "research": {
            "research", "researched", "investigate", "investigated", "survey",
            "surveyed", "literature review", "hypothesis", "experiment",
            "experimental", "fieldwork", "data collection", "sourced", "probe",
            "explored", "study", "studied", "empirical", "qualitative",
            "quantitative", "sampling", "ethnographic",
        },
        "analysis_evaluation": {
            "analyze", "analyzed", "analysis", "analytics", "evaluate",
            "evaluated", "assess", "assessed", "interpret", "interpreted",
            "diagnose", "diagnosed", "benchmark", "benchmarked", "compare",
            "correlation", "regression", "statistical", "statistics",
            "significance", "trend", "insight", "insights", "root cause",
            "a/b test", "hypothesis testing", "segmentation", "cohort",
        },
        "technical": {
            "python", "r", "sql", "java", "c++", "javascript", "matlab", "sas",
            "stata", "scala", "julia", "excel", "tableau", "power bi", "looker",
            "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "spark",
            "hadoop", "airflow", "dbt", "snowflake", "aws", "azure", "gcp",
            "docker", "kubernetes", "git", "linux", "bash", "algorithm",
            "machine learning", "deep learning", "nlp", "computer vision",
            "optimization", "simulation", "modeling", "model", "pipeline",
            "etl", "database", "api", "automation", "script", "dashboard",
        },
        "financial": {
            "budget", "budgeting", "forecast", "forecasting", "valuation",
            "p&l", "revenue", "cost", "margin", "roi", "npv", "irr", "ebitda",
            "financial model", "reconcile", "reconciled", "audit", "audited",
            "accounting", "gaap", "variance", "capital", "portfolio",
            "underwriting", "due diligence", "cash flow", "pricing",
        },
    },
    "communication": {
        "verbal_written": {
            "present", "presented", "presentation", "author", "authored",
            "wrote", "write", "drafted", "publish", "published", "report",
            "reported", "documented", "documentation", "brief", "briefed",
            "articulate", "articulated", "spoke", "speaking", "lecture",
            "lectured", "memo", "whitepaper", "newsletter", "blog", "copy",
            "editorial", "edited", "proofread", "storytelling", "narrative",
        },
        "promote_influence": {
            "pitch", "pitched", "persuade", "persuaded", "influence",
            "influenced", "advocate", "advocated", "market", "marketed",
            "promote", "promoted", "campaign", "outreach", "branding",
            "publicize", "evangelize", "negotiate", "negotiated", "sold",
            "sell", "convince", "lobbied", "recruited", "fundraised",
            "fundraising", "sponsorship",
        },
        "interpersonal": {
            "liaise", "liaised", "correspond", "corresponded", "consult",
            "consulted", "client", "clients", "stakeholder", "stakeholders",
            "cross-functional", "interviewed", "facilitated", "moderated",
            "mediated", "counseled", "advised", "relationship", "rapport",
            "onboarded", "customer-facing", "bilingual", "translated",
        },
        # VMock scans "position titles, degree program, any courses, languages,
        # software programs" as well as bullets, and rated Communication "Good
        # Job!" on two resumes whose bullets are pure systems work. The terms
        # below are the communication-carrying nouns that actually appear on
        # such resumes -- artefacts that exist to convey information to someone.
        "artifacts_teaching": {
            "notes", "note-taking", "transcription", "transcript",
            "translation", "translate", "dashboard", "dashboards",
            "visualization", "visualisation", "readme", "docs", "guide",
            "tutorial", "leaderboard", "paper", "papers", "publication",
            "poster", "summary", "summarize", "summarized", "annotate",
            "annotated", "labeling", "labelling", "feedback", "survey",
            "surveys", "review", "reviewed", "explained", "walkthrough",
            "demo", "demoed", "teaching assistant", "lab sections",
            "office hours", "students", "student", "course", "coursework",
            "instruction", "instructed", "tutoring", "taught", "curriculum",
            "reporting", "readable", "interface", "front-end", "frontend",
            "user-facing", "ui", "ux", "chat", "prompt", "prompting",
        },
    },
    "leadership": {
        "lead_manage": {
            "led", "lead", "leading", "manage", "managed", "manager",
            "supervise", "supervised", "direct", "directed", "head", "headed",
            "chair", "chaired", "captain", "president", "founder", "co-founder",
            "chief", "director", "principal", "oversee", "oversaw", "delegate",
            "delegated", "spearhead", "spearheaded", "championed", "governed",
            "team of", "reports", "direct reports",
        },
        "plan_organize": {
            "plan", "planned", "planning", "organize", "organized", "organised",
            "coordinate", "coordinated", "schedule", "scheduled", "strategize",
            "strategy", "strategic", "roadmap", "prioritize", "prioritized",
            "allocate", "allocated", "orchestrate", "orchestrated", "logistics",
            "milestone", "timeline", "workflow", "governance", "restructured",
        },
        # Ownership language. VMock rated Leadership "Good Job!" on resumes
        # whose only formal leadership title was a founder line, so the signal
        # it reads is plainly "who was answerable for this", not job titles.
        "own_drive": {
            "own", "owns", "owned", "ownership", "drove", "drive", "driving",
            "initiative", "board", "board seat", "coo", "ceo", "cto", "vp",
            "sole", "solely", "responsible", "accountable", "ran", "run",
            "running", "set up", "stood up", "founded", "co-founded",
            "cofounded", "launch", "launched", "roadmap", "hired", "hiring",
            "headcount", "recruited", "onboarding", "mentored", "trained",
            "decided", "decision", "policy", "standards", "convened",
            "end to end", "end-to-end", "from scratch", "greenfield",
        },
    },
    "teamwork": {
        "collaborate_relationships": {
            "collaborate", "collaborated", "collaboration", "partner",
            "partnered", "partnership", "team", "teams", "teamed", "joint",
            "co-authored", "co-led", "co-founded", "co-founder",
        "co-created", "co-developed", "co-designed", "co-built", "co-hosted", "peer", "peers", "committee", "cohort",
            "alliance", "coalition", "worked with", "alongside", "contributed",
            "cross-team", "interdisciplinary", "member",
        },
        "support_service": {
            "support", "supported", "assist", "assisted", "serve", "served",
            "service", "customer", "customers", "help desk", "helpdesk",
            "troubleshoot", "troubleshot", "resolve", "resolved", "respond",
            "responded", "maintain", "maintained", "administer", "administered",
            "processed", "fulfilled", "escalated", "ticket", "tickets", "sla",
        },
        # Working into someone else's system or handing work on. On the two
        # resumes VMock rated Teamwork "Good Job!", this is the only teamwork
        # vocabulary present -- there are no "collaborated with" bullets at all.
        "integrate_handoff": {
            "integrate", "integrated", "integration", "contributor",
            "contributors", "commits", "handoff", "handed off", "shared",
            "sharing", "reused", "adopted", "adoption", "downstream",
            "upstream", "staff", "colleague", "colleagues", "students",
            "clients", "users", "reviewers", "reviewing", "code review",
            "pair", "paired", "pairing", "coordination", "with the team",
            "other four", "teammates", "collaborators", "consortium",
            "open-source", "open source", "community", "workshop",
        },
    },
    "initiative": {
        "create_modify": {
            "create", "created", "build", "built", "design", "designed",
            "develop", "developed", "launch", "launched", "found", "founded",
            "establish", "established", "initiate", "initiated", "introduce",
            "introduced", "pioneer", "pioneered", "prototype", "prototyped",
            "invent", "invented", "redesign", "redesigned", "revamp",
            "revamped", "automate", "automated", "streamline", "streamlined",
            "from scratch", "ground up", "first", "novel",
        },
        "teach_mentor": {
            "teach", "taught", "mentor", "mentored", "tutor", "tutored",
            "train", "trained", "coach", "coached", "instruct", "instructed",
            "onboard", "onboarded", "educate", "educated", "guide", "guided",
            "workshop", "curriculum", "ta", "teaching assistant", "advised",
            "led training", "upskilled",
        },
    },
}

COMPETENCY_LABELS = {
    "analytical": "Analytical",
    "communication": "Communication",
    "leadership": "Leadership",
    "teamwork": "Teamwork",
    "initiative": "Initiative",
}

FACET_LABELS = {
    "research": "Research",
    "analysis_evaluation": "Analysis / Evaluation",
    "technical": "Technical",
    "financial": "Financial",
    "verbal_written": "Verbal / Written",
    "promote_influence": "Promote / Influence",
    "interpersonal": "Interpersonal",
    "lead_manage": "Lead / Manage",
    "plan_organize": "Plan / Organize",
    "collaborate_relationships": "Collaborate / Build Relationships",
    "support_service": "Admin Support / Customer Service",
    "create_modify": "Create / Modify",
    "teach_mentor": "Teach / Mentor",
}

# ---------------------------------------------------------------------------
# SENIORITY LADDER - career progression signal
# ---------------------------------------------------------------------------
SENIORITY_LADDER = [
    (1, {"volunteer", "shadow", "observer", "trainee", "apprentice"}),
    (2, {"intern", "internship", "co-op", "coop", "assistant", "aide",
         "student", "tutor", "ambassador", "clerk"}),
    (3, {"analyst", "associate", "coordinator", "specialist", "developer",
         "engineer", "designer", "consultant", "researcher", "technician",
         "representative", "teaching assistant", "research assistant"}),
    (4, {"senior", "sr", "lead", "supervisor", "manager", "captain",
         "president", "chair", "head", "principal", "staff"}),
    (5, {"director", "founder", "co-founder", "cofounder", "chief", "ceo",
         "cto", "coo", "cfo", "partner", "vp", "vice president", "owner"}),
]

# ---------------------------------------------------------------------------
# SECTIONS
# ---------------------------------------------------------------------------
# canonical -> accepted heading strings (lowercased, punctuation stripped)
SECTION_SYNONYMS = {
    "education": [
        "education", "academic background", "academics", "educational background",
        "education & training", "education and training",
    ],
    "experience": [
        "experience", "work experience", "professional experience",
        "relevant experience", "employment", "employment history",
        "work history", "industry experience", "internship experience",
        "internships", "professional background", "career history",
    ],
    "leadership": [
        "leadership & activities", "leadership and activities", "leadership",
        "activities", "leadership experience", "extracurricular activities",
        "extracurriculars", "campus involvement", "involvement",
        "activities & leadership", "activities and leadership",
        "leadership & involvement", "co-curriculars", "cocurriculars",
    ],
    "skills": [
        "skills", "technical skills", "skills & interests", "skills and interests",
        "core competencies", "technical proficiencies", "proficiencies",
        "additional skills", "skills, activities & interests", "tools",
        "technologies", "technical expertise",
    ],
    "projects": [
        "projects", "selected projects", "technical projects", "academic projects",
        "personal projects", "project experience", "portfolio",
    ],
    "research": [
        "research", "research experience", "research projects",
    ],
    "awards": [
        "awards", "honors", "honours", "awards & honors", "awards and honors",
        "honors & awards", "honours and awards", "achievements",
        "honors and awards", "distinctions", "scholarships",
    ],
    "publications": ["publications", "papers", "presentations & publications"],
    "certifications": [
        "certifications", "certificates", "licenses", "licenses & certifications",
        "licences and certifications", "credentials",
    ],
    "coursework": [
        "relevant coursework", "coursework", "selected coursework", "courses",
    ],
    "volunteer": [
        "volunteer", "volunteer experience", "community service",
        "community involvement", "service",
    ],
    "interests": ["interests", "hobbies", "personal interests"],
    "summary": [
        "summary", "professional summary", "objective", "career objective",
        "profile", "about me", "personal statement",
    ],
    "languages": ["languages", "language skills"],
}

# VMock's "Essential Sections" check: these must be present.
ESSENTIAL_SECTIONS = ["education", "experience"]

# Sections most career centres advise against on a student resume.
DISCOURAGED_SECTIONS = ["summary", "interests"]

# Under quirks.heading_ampersand_strict, only the "&" spelling is accepted.
AMPERSAND_PREFERRED = {
    "leadership and activities": "Leadership & Activities",
    "activities and leadership": "Activities & Leadership",
    "skills and interests": "Skills & Interests",
    "awards and honors": "Awards & Honors",
    "honors and awards": "Honors & Awards",
    "education and training": "Education & Training",
}

# ---------------------------------------------------------------------------
# FORMATTING PRIMITIVES
# ---------------------------------------------------------------------------
BULLET_GLYPHS = "•●▪◦‣⁃·■○∙-–—*o>"
# These double as ordinary characters, so the parser only treats them as
# bullets when whitespace follows.
AMBIGUOUS_GLYPHS = "-\u2013\u2014*o>"

MONTHS_FULL = [
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
]
MONTHS_ABBR = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep",
               "oct", "nov", "dec"]
# Forms VMock rejects. "Sept" is the classic one.
MONTHS_BAD_ABBR = {"sept", "sept.", "jan.", "feb.", "mar.", "apr.", "jun.",
                   "jul.", "aug.", "sep.", "oct.", "nov.", "dec.", "june.",
                   "july."}

# ---------------------------------------------------------------------------
# SPELL-CHECK WHITELIST
# ---------------------------------------------------------------------------
# Real VMock famously rejects these and refuses to learn them. With
# quirks.aggressive_spellcheck off, the clone accepts them.
TECH_WHITELIST = {
    "python", "numpy", "pandas", "scipy", "sklearn", "scikit", "pytorch",
    "tensorflow", "keras", "matplotlib", "seaborn", "plotly", "jupyter",
    "anaconda", "conda", "pypi", "flask", "django", "sqlalchemy",
    # OBSERVED accepted by VMock -- present in a resume it scored and absent
    # from the "Re-examine the spellings" list it printed for that resume.
    "asr", "poincaré", "poincare", "architected", "multithreading",
    "leaderboard",
    # OBSERVED flagged by VMock, so deliberately NOT whitelisted:
    #   fastapi, websocket, websockets, supabase

    "postgres", "postgresql", "mysql", "sqlite", "mongodb", "redis", "kafka",
    "hadoop", "spark", "pyspark", "hive", "presto", "snowflake", "databricks",
    "airflow", "dbt", "looker", "tableau", "powerbi", "sas", "stata", "spss",
    "matlab", "octave", "rstudio", "tidyverse", "ggplot", "dplyr", "shiny",
    "javascript", "typescript", "nodejs", "node", "npm", "yarn", "webpack",
    "react", "redux", "angular", "vue", "svelte", "nextjs", "nuxt", "jquery",
    "html", "css", "sass", "scss", "tailwind", "bootstrap", "graphql", "rest",
    "json", "xml", "yaml", "csv", "api", "apis", "sdk", "cli", "gui", "ide",
    "github", "gitlab", "bitbucket", "jira", "confluence", "asana", "trello",
    "docker", "kubernetes", "k8s", "terraform", "ansible", "jenkins", "ci",
    "cd", "devops", "aws", "ec2", "s3", "lambda", "rds", "azure", "gcp",
    "bigquery", "firebase", "heroku", "netlify", "vercel", "nginx", "apache",
    "linux", "ubuntu", "macos", "ios", "android", "bash", "zsh", "powershell",
    "vim", "vscode", "pycharm", "intellij", "eclipse", "xcode", "latex",
    "overleaf", "markdown", "notion", "figma", "sketch", "canva", "photoshop",
    "illustrator", "indesign", "premiere", "autocad", "solidworks", "ansys",
    "simulink", "labview", "quickbooks", "netsuite", "salesforce", "hubspot",
    "workday", "sap", "oracle", "servicenow", "splunk", "datadog", "grafana",
    "prometheus", "elasticsearch", "kibana", "rabbitmq", "celery", "grpc",
    "oauth", "jwt", "saml", "ldap", "vpn", "sql", "nosql", "etl", "elt", "olap",
    "kpi", "kpis", "roi", "saas", "paas", "iaas", "b2b", "b2c", "crm", "erp",
    "ml", "ai", "nlp", "llm", "llms", "cnn", "rnn", "lstm", "gan", "bert",
    "gpt", "rag", "xgboost", "lightgbm", "catboost", "arima", "anova", "pca",
    "svm", "knn", "auc", "roc", "rmse", "mae", "mape", "cagr", "ebitda",
    "gaap", "ifrs", "npv", "irr", "capm", "wacc", "fpga", "asic", "iot", "gpu",
    "cpu", "ram", "ssd", "http", "https", "tcp", "udp", "dns", "cdn", "ux",
    "ui", "seo", "sem", "ppc", "ctr", "cpa", "cpc", "arr", "mrr", "ltv", "cac",
    "roadmap", "roadmaps", "rollout", "rollouts", "handover", "upskilled", "onboarding",
    "laude", "summa", "magna", "cum", "valedictorian",
    "salutatorian", "alumni", "alumnus", "practicum", "capstone",
    # "webhook", "idempotency", "rebasing" deliberately NOT whitelisted:
    # VMock reports all three as misspelled (red) -- observed verbatim.
    # OBSERVED accepted by VMock (never flagged on a real report):
    "checkpointing", "backend", "backends", "schemas", "schema",
    "webhooks", "idempotent", "cron", "crontab", "programmatically", "eval", "evals", "ivp", "ode",
    "pde", "runge", "kutta", "cromer", "euler", "poincare", "lyapunov",
    "stratification", "poststratification", "multilevel", "bayesian",
    "frequentist", "heteroskedasticity", "multicollinearity", "bootstrapping",
    "tokenization", "embeddings", "finetuning", "quantization", "inference",
    "middleware", "serverless", "microservice", "microservices", "railway", "vite", "tailwind", "deno", "stripe",
    "sso", "oauth2", "cors", "csrf", "xss", "sql injection", "observability",
    "telemetry", "throughput", "latency", "concurrency", "idempotence",
    "backtest", "backtesting", "walkforward", "changelog", "monorepo",
    "gpa", "sat", "act", "gre", "gmat", "lsat", "mcat", "cfa", "cpa", "pmp",
    "phd", "mba", "msc", "bsc", "bcom", "beng", "mads", "stem", "nace", "ta",
    "tas", "ras", "usd", "cad", "eur", "gbp", "qtr", "yoy", "qoq", "mom",
}

# Spoken languages. VMock's guide is explicit that it scans "position titles,
# degree program, any courses, languages, software programs" -- someone working
# in three languages is carrying communication evidence a keyword scan misses.
SPOKEN_LANGUAGES = {
    "english", "mandarin", "chinese", "cantonese", "spanish", "french",
    "german", "italian", "portuguese", "russian", "arabic", "hebrew", "hindi",
    "urdu", "bengali", "punjabi", "tamil", "telugu", "marathi", "gujarati",
    "japanese", "korean", "vietnamese", "thai", "indonesian", "malay",
    "tagalog", "filipino", "turkish", "persian", "farsi", "polish", "czech",
    "slovak", "hungarian", "romanian", "bulgarian", "serbian", "croatian",
    "bosnian", "slovenian", "greek", "dutch", "flemish", "swedish", "danish",
    "norwegian", "finnish", "icelandic", "ukrainian", "belarusian", "latvian",
    "lithuanian", "estonian", "albanian", "macedonian", "swahili", "yoruba",
    "igbo", "hausa", "amharic", "somali", "zulu", "afrikaans", "nepali",
    "sinhala", "burmese", "khmer", "lao", "mongolian", "kazakh", "uzbek",
    "azerbaijani", "armenian", "georgian", "catalan", "basque", "galician",
    "welsh", "irish", "gaelic", "maltese", "latin", "cantonese",
}

MONTH_TOKENS = set(MONTHS_FULL) | set(MONTHS_ABBR)


# ---------------------------------------------------------------------------
# COMMONWEALTH SPELLINGS
# ---------------------------------------------------------------------------
# The bundled dictionary is en_US, so Canadian/UK/AU spellings would all be
# flagged. Real VMock is US-tuned and does flag them; this set lets the clone
# accept them (presentation.spell.commonwealth_ok in rules.yaml).
COMMONWEALTH_OK = {
    "honours", "honour", "honoured", "colour", "colours", "coloured",
    "favour", "favours", "favoured", "favourite", "behaviour", "behaviours",
    "labour", "labours", "neighbour", "endeavour", "endeavours", "rumour",
    "harbour", "flavour", "armour", "vapour", "saviour", "valour",
    "organisation", "organisations", "organisational", "organise", "organised",
    "organising", "specialise", "specialised", "specialising", "specialisation",
    "analyse", "analysed", "analysing", "recognise", "recognised", "recognising",
    "prioritise", "prioritised", "prioritising", "optimise", "optimised",
    "optimising", "utilise", "utilised", "utilising", "maximise", "maximised",
    "minimise", "minimised", "standardise", "standardised", "summarise",
    "summarised", "emphasise", "emphasised", "categorise", "categorised",
    "digitise", "digitised", "modernise", "modernised", "realise", "realised",
    "apologise", "authorise", "authorised", "characterise", "computerise",
    "centre", "centres", "centred", "theatre", "metre", "metres", "litre",
    "litres", "kilometre", "kilometres", "fibre", "calibre", "sombre",
    "programme", "programmes", "licence", "licences", "defence", "offence",
    "practise", "practised", "pretence",
    "travelled", "travelling", "traveller", "modelling", "modelled",
    "labelled", "labelling", "cancelled", "cancelling", "counselled",
    "counselling", "enrolled", "enrolment", "fulfilment", "instalment",
    "skilful", "wilful", "judgement", "acknowledgement", "ageing",
    "learnt", "spelt", "burnt", "dreamt", "amongst", "whilst", "towards",
    "catalogue", "catalogues", "dialogue", "dialogues", "analogue",
    "cheque", "cheques", "storey", "storeys", "grey", "sceptical",
    "aluminium", "cosy", "moustache", "plough", "draught", "tyre",
}
