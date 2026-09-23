"""Deterministic ATS keyword matching — runs with or without an LLM.

This is the 'tool' half of the agent: cheap, reliable, explainable analysis
that the LLM then reasons over. Keeping it deterministic stops the model
from hallucinating a match score.
"""
from __future__ import annotations

import re
from collections import Counter

STOPWORDS = set("""
a an the and or but if then than that this these those with without within into onto from for
to of in on at by as is are was were be been being being do does did doing have has had having
we you they he she it i our your their his her its us them me my mine yours ours theirs
will would shall should can could may might must not no nor so such very more most other another
each every any some all both few many much own same only just also who whom whose which what when
where why how there here about across after against among around before behind below beneath beside
between beyond during except inside near off out over through under until up upon while
work working works job jobs role roles position positions team teams company companies candidate
candidates experience experiences year years plus etc via using use used strong good great excellent
ability able skills skill knowledge understanding responsibilities requirements qualifications
new well including include includes ensure ensuring help helping support supporting looking seeking
join joining opportunity offer offers benefits apply application please must-have nice
""".split())

# Multi-word phrases worth catching as single keywords.
PHRASES = [
    "machine learning", "deep learning", "data science", "data engineering", "data analysis",
    "project management", "product management", "stakeholder management", "change management",
    "continuous integration", "continuous delivery", "unit testing", "test automation",
    "version control", "code review", "agile", "scrum", "kanban", "ci/cd", "devops",
    "rest api", "restful api", "microservices", "event driven", "distributed systems",
    "cloud computing", "infrastructure as code", "site reliability", "observability",
    "natural language processing", "computer vision", "large language models",
    "business intelligence", "data warehouse", "data pipeline", "etl", "elt",
    "customer success", "account management", "go to market", "lead generation",
    "financial modelling", "financial modeling", "risk management", "internal controls",
    "public speaking", "cross functional", "problem solving", "attention to detail",
]

# Tokens that must survive tokenisation intact.
KEEP = {"c++", "c#", ".net", "node.js", "ci/cd", "a/b", "f#", "objective-c", "go", "r"}


def tokenize(text: str) -> list[str]:
    text = text.lower()
    raw = re.findall(r"[a-z0-9][a-z0-9\+\#\.\-/]*", text)
    out = []
    for t in raw:
        t = t.strip(".-/")
        if not t:
            continue
        out.append(t)
    return out


def _ngrams(tokens: list[str], n: int) -> list[str]:
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


SECTION_NOISE = re.compile(
    r"\b(m/f/d|w/m/d|f/m/d|d/f/m|gmbh|ag|inc|ltd|remote|hybrid|onsite|fulltime|"
    r"full-time|part-time|permanent|salary|eur|usd)\b")


def extract_keywords(jd: str, limit: int = 40) -> list[tuple[str, int]]:
    """Return [(keyword, weight)] from a job description, most important first.

    Unigrams + curated multi-word phrases + bigrams that actually repeat.
    Bigrams never cross a line break, which keeps out junk like 'spark airflow'.
    """
    lines = [ln for ln in jd.lower().split("\n")]
    all_tokens = tokenize(jd)
    lowered = " ".join(all_tokens)

    counts: Counter[str] = Counter()

    # 1) curated phrases
    for phrase in PHRASES:
        c = lowered.count(phrase)
        if c:
            counts[phrase] += c * 4

    # 2) unigrams
    for t in all_tokens:
        if t in KEEP:
            counts[t] += 3
            continue
        if len(t) < 3 or t in STOPWORDS or t.isdigit() or SECTION_NOISE.fullmatch(t):
            continue
        counts[t] += 1

    # 3) bigrams, per line only, and only if they repeat
    bigram_counts: Counter[str] = Counter()
    for line in lines:
        toks = tokenize(line)
        for bg in _ngrams(toks, 2):
            a, b = bg.split(" ", 1)
            if a in STOPWORDS or b in STOPWORDS:
                continue
            if len(a) < 3 or len(b) < 3 or a.isdigit() or b.isdigit():
                continue
            if SECTION_NOISE.search(bg):
                continue
            bigram_counts[bg] += 1
    for bg, c in bigram_counts.items():
        if c >= 2 or bg in PHRASES:
            counts[bg] += c * 3

    # 4) boost requirement lines
    for line in lines:
        if re.match(r"^\s*(-|\d+\.|\*|•)", line) or re.search(
                r"\b(require|required|must|essential|expect|qualification)", line):
            for t in set(tokenize(line)):
                if t in counts:
                    counts[t] += 2
            for bg in set(_ngrams(tokenize(line), 2)):
                if bg in counts:
                    counts[bg] += 2

    ranked = [(k, v) for k, v in counts.most_common() if v >= 2]

    # 5) drop unigrams that only ever appear inside a kept multi-word term
    multi = [k for k, _ in ranked if " " in k][:limit]
    multi_parts = {w for p in multi for w in p.split()}
    final: list[tuple[str, int]] = []
    for k, v in ranked:
        if " " not in k and k in multi_parts and v < 4:
            continue
        final.append((k, v))
        if len(final) >= limit:
            break
    return final


def match(cv_text: str, jd_text: str, limit: int = 40) -> dict:
    """Compare CV against JD keywords -> score + matched/missing lists."""
    keywords = extract_keywords(jd_text, limit=limit)
    cv_tokens = set(tokenize(cv_text))
    cv_lower = " ".join(tokenize(cv_text))

    matched, missing = [], []
    total_w = got_w = 0
    for kw, w in keywords:
        total_w += w
        hit = (kw in cv_lower) if " " in kw else (kw in cv_tokens)
        if hit:
            got_w += w
            matched.append(kw)
        else:
            missing.append(kw)

    score = round(100 * got_w / total_w) if total_w else 0
    return {
        "score": score,
        "matched": matched,
        "missing": missing,
        "keywords": [k for k, _ in keywords],
    }


def readability_flags(cv_text: str) -> list[str]:
    """Cheap ATS-hygiene checks on the CV text."""
    flags = []
    low = cv_text.lower()
    if len(cv_text) < 600:
        flags.append("CV text is very short — the file may be image-based or parsing failed.")
    if not re.search(r"[\w\.\-]+@[\w\-]+\.\w+", cv_text):
        flags.append("No email address detected — ATS may fail to extract your contact info.")
    if not re.search(r"(\+?\d[\d \-/()]{7,})", cv_text):
        flags.append("No phone number detected.")
    if not re.search(r"\b(19|20)\d{2}\b", cv_text):
        flags.append("No dates detected — add month/year ranges to each role.")
    if not re.search(r"\b(experience|employment|work history|berufserfahrung)\b", low):
        flags.append("No clear 'Experience' section heading found — ATS parsers rely on standard headings.")
    if not re.search(r"\b(education|ausbildung|studium)\b", low):
        flags.append("No clear 'Education' section heading found.")
    if not re.search(r"\b(skills|kenntnisse|kompetenzen)\b", low):
        flags.append("No clear 'Skills' section — add one with the JD's exact tool names.")
    bullets = len(re.findall(r"^\s*-\s+", cv_text, flags=re.MULTILINE))
    if bullets < 5:
        flags.append("Few bullet points detected — use bullets, not paragraphs, for achievements.")
    if len(re.findall(r"\b\d+%|\b\d+\s*(k|m|mio|million|users|customers|hours|days)\b", low)) < 3:
        flags.append("Few quantified results — add numbers (%, €, headcount, time saved) to bullets.")
    if "|" in cv_text and cv_text.count("|") > 20:
        flags.append("Lots of table pipes detected — tables/columns often break ATS parsing.")
    return flags
