#!/usr/bin/env python3
"""
apply.py — build one job application for Salini Sadangi from the terminal.

    python3 apply.py                      # interactive
    python3 apply.py --jd-file jd.txt     # read the job description from a file
    python3 apply.py --no-ai              # template mode, zero API calls
    python3 apply.py --ai                 # skip the AI prompt, use AI if a provider is available

What it produces, in applications/<Company>_<Role>/ :
    Salini_Sadangi_Resume.html / .pdf      nearest broad variant, summary tailored by AI when enabled
    CoverLetter_Salini_Sadangi_<Company>.html / .pdf
    Email_<Company>.txt                    direct application email or portal follow-up, plus a mailto link
    notes.md                               job description, tags, which model wrote what, checks that ran
and appends one row to tracker/salini_jobs.csv (dedupe on company + role), then rebuilds the tracker.

Providers, tried in this order when AI is on: Gemini (free tier) -> Groq (Llama 3.3 70B, free tier)
-> Ollama (local Llama) -> template only. Keys live in .env (see .env.example). No third-party
Python packages are required; openpyxl is optional and only used to rebuild the xlsx tracker.

Every AI output passes through hard checks before it is used:
    1. every number in the text must already exist in facts.md or the chosen resume variant
    2. no em dash, en dash or hyphen in letters and emails (house rule)
    3. American spelling
    4. availability stated as immediate
If a check fails the model gets one retry with the failure named; after that the template text is used.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VARIANTS = ROOT / "variants"
TEMPLATES = ROOT / "templates"
TRACKER_DIR = ROOT / "tracker"
TRACKER_CSV = TRACKER_DIR / "salini_jobs.csv"
APPS = ROOT / "applications"
FACTS = ROOT / "facts.md"

NAME = "Salini Sadangi"
EMAIL = "salinisadangi26@gmail.com"

# --------------------------------------------------------------------------- small utilities


def load_env() -> None:
    """Minimal .env loader so python-dotenv is not needed."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def say(msg: str) -> None:
    print(f"  {msg}")


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        val = ""
    return val or default


def ask_yes(prompt: str, default: bool = False) -> bool:
    d = "Y/n" if default else "y/N"
    val = ask(f"{prompt} ({d})").lower()
    if not val:
        return default
    return val.startswith("y")


def ask_multiline(prompt: str) -> str:
    print(f"{prompt}\n  (paste, then type END on its own line)")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def slug(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")
    return s or "X"


def salutation(name: str) -> str:
    """'Ms Tan' -> 'Ms Tan', 'Dr. Lee Wei' -> 'Dr. Lee', 'Priya Nair' -> 'Priya'."""
    parts = name.split()
    if not parts:
        return "Hiring Team"
    if parts[0].rstrip(".").lower() in ("mr", "ms", "mrs", "miss", "dr", "prof") and len(parts) > 1:
        return " ".join(parts[:2])
    return parts[0]


def strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", s))


def find_chrome() -> str | None:
    env = os.environ.get("CHROME_PATH")
    if env and Path(env).exists():
        return env
    candidates = {
        "Darwin": [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ],
        "Linux": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge"],
        "Windows": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ],
    }[platform.system() if platform.system() in ("Darwin", "Windows") else "Linux"]
    for c in candidates:
        if Path(c).exists():
            return c
        w = shutil.which(c)
        if w:
            return w
    return None


def html_to_pdf(chrome: str | None, html_path: Path) -> Path | None:
    if not chrome:
        return None
    pdf = html_path.with_suffix(".pdf")
    cmd = [chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
           f"--print-to-pdf={pdf}", html_path.resolve().as_uri()]
    try:
        subprocess.run(cmd, capture_output=True, timeout=90)
    except Exception as exc:  # noqa: BLE001
        say(f"PDF failed for {html_path.name}: {exc}")
        return None
    return pdf if pdf.exists() else None


# --------------------------------------------------------------------------- variant selection

VARIANT_KEYWORDS = {
    "Infra_RealEstate": ["infrastructure", "real estate", "real-estate", "property", "reit", "project finance",
                         "energy", "renewable", "power", "utilities", "fund management", "asset management",
                         "lodging", "logistics", "data centre", "data center", "esg", "sustainab"],
    "InvestmentBanking": ["investment banking", "ib ", "m&a", "mergers", "corporate finance", "capital markets",
                          "ecm", "dcm", "coverage", "pitch", "transaction", "deal", "private equity", "fig",
                          "advisory", "valuation"],
    "EquityResearch": ["equity research", "research analyst", "investment analyst", "equities", "market analyst",
                       "buy-side", "sell-side", "portfolio", "stock", "securities", "dealer", "fund", "asset management"],
    "Operations_Marketing": ["operations", "marketing", "customer success", "merchant", "client service",
                             "business development", "growth", "partnerships", "onboarding", "hr", "human resources",
                             "investor relations", "communications", "management trainee", "coordinator", "program"],
    "Accounting_Tax_FPA": ["accounting", "accountant", "tax", "fp&a", "financial planning", "finance intern",
                           "finance associate", "audit", "reporting", "controller", "budget", "gst", "compliance",
                           "bookkeeping", "payroll"],
    "Risk_Markets": ["risk", "model validation", "irrbb", "liquidity", "treasury", "alm", "markets", "trading",
                     "structured products", "derivatives", "fixed income", "ficc", "credit", "quant", "documentation"],
}
VARIANT_LABEL = {
    "Infra_RealEstate": "Infrastructure, real estate, project finance",
    "InvestmentBanking": "Investment banking, corporate finance",
    "EquityResearch": "Equity research, investment analyst",
    "Operations_Marketing": "Operations, marketing, client-facing",
    "Accounting_Tax_FPA": "Accounting, tax, FP&A",
    "Risk_Markets": "Risk, markets, structured products",
}


def pick_variant(role: str, jd: str, tags: list[str]) -> list[tuple[str, int]]:
    text = f"{role} {' '.join(tags)} {jd}".lower()
    scores = []
    for name, kws in VARIANT_KEYWORDS.items():
        score = 0
        for kw in kws:
            n = text.count(kw)
            if n:
                score += 2 + min(n, 4)  # presence weighs more than repetition
            if kw in role.lower() or kw in " ".join(tags).lower():
                score += 6
        scores.append((name, score))
    scores.sort(key=lambda x: -x[1])
    return scores


# --------------------------------------------------------------------------- house-style checks

AMERICAN = {
    "analysed": "analyzed", "analyse": "analyze", "analysing": "analyzing", "modelling": "modeling",
    "modelled": "modeled", "modeller": "modeler", "organisation": "organization", "organisations": "organizations",
    "organised": "organized", "organise": "organize", "centralised": "centralized", "decentralised": "decentralized",
    "programme": "program", "programmes": "programs", "favour": "favor", "favourable": "favorable",
    "realise": "realize", "realised": "realized", "recognise": "recognize", "recognised": "recognized",
    "optimise": "optimize", "optimised": "optimized", "optimisation": "optimization", "prioritise": "prioritize",
    "prioritised": "prioritized", "specialise": "specialize", "specialised": "specialized", "summarise": "summarize",
    "summarised": "summarized", "utilise": "utilize", "colour": "color", "behaviour": "behavior",
    "labour": "labor", "licence": "license", "defence": "defense", "practise": "practice", "sceptical": "skeptical",
    "judgement": "judgment", "catalogue": "catalog", "travelling": "traveling", "cancelled": "canceled",
    "learnt": "learned", "whilst": "while", "amongst": "among", "centre": "center", "fulfil": "fulfill",
}
HYPHEN_WORDS = {
    "co-authored": "coauthored", "co-author": "coauthor", "co-investment": "co investment", "e-mail": "email",
    "follow-up": "follow up", "month-end": "month end", "year-end": "year end", "take-private": "take private",
    "long-term": "long term", "short-term": "short term", "real-estate": "real estate", "cash-flow": "cash flow",
    "3-statement": "three statement", "12-month": "12 month", "5-year": "five year", "24-page": "24 page",
    "part-time": "part time", "full-time": "full time", "well-suited": "well suited", "hands-on": "hands on",
    "start-up": "startup", "set-up": "setup", "decision-making": "decision making", "sum-of-the-parts": "sum of the parts",
    "buy-side": "buy side", "sell-side": "sell side", "post-money": "post money", "pre-tax": "pretax",
    "working-capital": "working capital", "debt-service": "debt service", "credit-loss": "credit loss",
}


def americanize(text: str) -> str:
    def fix(m: re.Match) -> str:
        w = m.group(0)
        low = w.lower()
        if low in AMERICAN:
            rep = AMERICAN[low]
            return rep.capitalize() if w[0].isupper() else rep
        return w
    return re.sub(r"[A-Za-z]+", fix, text)


def dedash(text: str) -> str:
    """House rule: no em dash, en dash or hyphen in letters and emails."""
    text = text.replace("\u2014", ", ").replace("\u2013", " to ").replace("\u2012", " to ")
    for k, v in HYPHEN_WORDS.items():
        text = re.sub(re.escape(k), lambda m, v=v: (v[0].upper() + v[1:]) if m.group(0)[0].isupper() else v, text, flags=re.I)
    text = re.sub(r"(?<=\d)-(?=\d)", " to ", text)        # 2022-2024 -> 2022 to 2024
    text = re.sub(r"(?<=\w)-(?=\w)", " ", text)           # any leftover joined words
    text = re.sub(r"\s-\s", ", ", text)                   # spaced hyphen used as dash
    text = text.replace("-", "")
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r" ,", ",", text)
    return text


def has_dash(text: str) -> bool:
    return bool(re.search(r"[\u2012\u2013\u2014-]", text))


NUM_RE = re.compile(r"(?<![A-Za-z])[$€£]?\d[\d,]*(?:\.\d+)?(?:%|x|×|bn|m|k)?", re.I)


def numbers_in(text: str) -> set[str]:
    out = set()
    for m in NUM_RE.findall(text):
        n = m.lower().replace(",", "").replace("×", "x").lstrip("$€£")
        n = re.sub(r"(bn|m|k|x|%)$", "", n)
        if n and n not in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10"):
            out.add(n)
    return out


def numbers_not_in_facts(text: str, allowed: set[str]) -> set[str]:
    return {n for n in numbers_in(text) if n not in allowed}


def content_problems(text: str, allowed: set[str]) -> list[str]:
    """Checks shared by summary, letter and email validators."""
    probs = []
    bad = numbers_not_in_facts(text, allowed)
    if bad:
        probs.append("numbers not in FACTS: " + ", ".join(sorted(bad)))
    if re.search(r"micron|kairos|mantike", text, re.I):
        probs.append("mentions a project that is not Salini's")
    if re.search(r"\b(hold|holds|have|has|with|earned|completed|obtained)\s+(a|an|my)?\s*(master|m\.?sc)", text, re.I):
        probs.append("the M.Sc. is not finished: say 'completing in January 2027', never 'holds a Master's'")
    if re.search(r"\b(java|sql|power bi|vba|tableau|r\b|c\+\+)", text, re.I):
        probs.append("claims a tool that is not in FACTS")
    return probs


# --------------------------------------------------------------------------- AI providers


class Provider:
    name = "none"

    def complete(self, system: str, user: str) -> str:  # returns raw text (expected JSON)
        raise NotImplementedError


class Gemini(Provider):
    name = "gemini"

    def __init__(self, key: str, model: str):
        self.key, self.model = key, model

    def complete(self, system: str, user: str) -> str:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
               f"?key={urllib.parse.quote(self.key)}")
        body = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.4, "responseMimeType": "application/json"},
        }
        data = _post_json(url, body, {})
        return data["candidates"][0]["content"]["parts"][0]["text"]


class Groq(Provider):
    name = "groq"

    def __init__(self, key: str, model: str):
        self.key, self.model = key, model

    def complete(self, system: str, user: str) -> str:
        body = {
            "model": self.model,
            "temperature": 0.4,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        data = _post_json("https://api.groq.com/openai/v1/chat/completions", body,
                          {"Authorization": f"Bearer {self.key}"})
        return data["choices"][0]["message"]["content"]


class Ollama(Provider):
    name = "ollama"

    def __init__(self, model: str, host: str):
        self.model, self.host = model, host.rstrip("/")

    def complete(self, system: str, user: str) -> str:
        body = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.4},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        data = _post_json(f"{self.host}/api/chat", body, {}, timeout=300)
        return data["message"]["content"]


def _post_json(url: str, body: dict, headers: dict, timeout: int = 90) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def available_providers() -> list[Provider]:
    chain: list[Provider] = []
    if os.environ.get("GEMINI_API_KEY"):
        chain.append(Gemini(os.environ["GEMINI_API_KEY"], os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")))
    if os.environ.get("GROQ_API_KEY"):
        chain.append(Groq(os.environ["GROQ_API_KEY"], os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")))
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=2) as r:
            tags = json.loads(r.read().decode())
        want = os.environ.get("OLLAMA_MODEL", "llama3.1")
        names = [m.get("name", "") for m in tags.get("models", [])]
        pick = next((n for n in names if n.startswith(want)), None) or (names[0] if names else None)
        if pick:
            chain.append(Ollama(pick, host))
    except Exception:  # noqa: BLE001
        pass
    order = os.environ.get("PROVIDER_ORDER", "gemini,groq,ollama").split(",")
    chain.sort(key=lambda p: order.index(p.name) if p.name in order else 99)
    return chain


class AI:
    """Runs the provider chain with JSON parsing and one feedback retry per provider."""

    def __init__(self, chain: list[Provider], log: list[str]):
        self.chain, self.log = chain, log
        self.used: str | None = None

    def json(self, system: str, user: str, validate) -> dict | None:
        for p in self.chain:
            feedback = ""
            for attempt in (1, 2):
                try:
                    raw = p.complete(system, user + feedback)
                    raw = raw.strip()
                    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
                    obj = json.loads(raw)
                except urllib.error.HTTPError as exc:
                    detail = exc.read().decode(errors="ignore")[:200]
                    self.log.append(f"{p.name}: HTTP {exc.code} {detail}")
                    break  # quota / auth problem: move to next provider
                except Exception as exc:  # noqa: BLE001
                    self.log.append(f"{p.name} attempt {attempt}: {type(exc).__name__}: {exc}")
                    feedback = "\n\nYour previous reply was not valid JSON. Reply with one JSON object only."
                    continue
                problems = validate(obj)
                if not problems:
                    self.used = p.name
                    self.log.append(f"{p.name}: accepted on attempt {attempt}")
                    return obj
                self.log.append(f"{p.name} attempt {attempt} rejected: {'; '.join(problems)}")
                feedback = ("\n\nYour previous reply was rejected for these reasons: " + "; ".join(problems) +
                            ". Fix them. Use only facts from the FACTS section. Reply with one JSON object only.")
        return None


SYSTEM_PROMPT = """You write job-application documents for Salini Sadangi.
Hard rules:
- Use ONLY the FACTS section. Never invent a project, employer, tool, number, course, certification or date.
- If the job wants something not in FACTS, call it a learning target or leave it out. Never claim it.
- American spelling. No em dashes, no en dashes, no hyphens anywhere: write "coauthored", "month end", "three statement", "take private".
- Availability is immediate. Never write a salary figure.
- Salini is still studying: say 'completing the M.Sc. in January 2027'. Never say she holds a Master's degree.
- Plain, specific, confident. No "I am candid", no self-rejection lines, no exclamation marks, no buzzwords.
- Reply with one JSON object and nothing else."""


# --------------------------------------------------------------------------- document builders


def build_resume(variant: str, out_dir: Path, ai: AI | None, job: dict, facts: str, allowed: set[str]) -> tuple[Path, dict]:
    src = VARIANTS / f"Resume_Salini_Sadangi_Broad_{variant}.html"
    doc = src.read_text(encoding="utf-8")
    info = {"variant": variant, "summary_by": "template", "tag_by": "template"}
    if ai:
        cur_summary = strip_tags(re.search(r'<p class="summary">(.*?)</p>', doc, re.S).group(1))
        cur_tag = strip_tags(re.search(r'<div class="tag">(.*?)</div>', doc).group(1))
        user = (f"FACTS:\n{facts}\n\nCURRENT RESUME SUMMARY (rewrite this, same length within 10%):\n{cur_summary}\n\n"
                f"CURRENT HEADLINE TAG: {cur_tag}\n\nJOB: {job['role']} at {job['company']}\nTAGS: {', '.join(job['tags'])}\n"
                f"JOB DESCRIPTION:\n{job['jd'][:6000]}\n\n"
                "Task: rewrite the summary so it leads with what this job values most, keeping every fact true to FACTS, "
                "4 to 5 sentences, 600 to 800 characters. Also give a 3 to 5 word headline tag of the form "
                "'Field · Field · Field' using the middle dot character.\n"
                'Return {"summary": "...", "tag": "..."}')

        def validate(obj: dict) -> list[str]:
            probs = []
            s, t = obj.get("summary", ""), obj.get("tag", "")
            if not (450 <= len(s) <= 900):
                probs.append(f"summary length {len(s)} chars, need 450 to 900")
            probs += content_problems(s, allowed)
            if not t or len(t) > 60:
                probs.append("tag missing or too long")
            if "·" not in t:
                probs.append("tag must use the middle dot separator")
            return probs

        obj = ai.json(SYSTEM_PROMPT, user, validate)
        if obj:
            summary = html.escape(americanize(obj["summary"]), quote=False)
            tag = html.escape(obj["tag"], quote=False)
            doc = re.sub(r'(<p class="summary">).*?(</p>)', lambda m: m.group(1) + summary + m.group(2), doc, flags=re.S)
            doc = re.sub(r'(<div class="tag">).*?(</div>)', lambda m: m.group(1) + tag + m.group(2), doc)
            doc = re.sub(r"<title>.*?</title>", f"<title>{NAME} — {tag}</title>", doc, flags=re.S)
            info["summary_by"] = info["tag_by"] = ai.used
    out = out_dir / "Salini_Sadangi_Resume.html"
    out.write_text(doc, encoding="utf-8")
    return out, info


def template_letter(job: dict, variant: str) -> list[str]:
    """Dash-free fallback letter built from the variant's angle. Human should still read it."""
    angle = {
        "Infra_RealEstate": ("project and real asset investment work",
                             "a gas fired power plant financing memorandum taken to a mock investment committee, a solar leasing platform underwritten as a receivables book and a US$1.0bn take private co investment tested against a 20% hurdle"),
        "InvestmentBanking": ("valuation and transaction analysis",
                              "a US$1.0bn take private co investment argued on returns against a hurdle, a STRONG BUY initiation on Mastercard over a full three statement model and a project financing memorandum approved by a mock investment committee"),
        "EquityResearch": ("equity research",
                           "coauthored initiations on Mastercard (STRONG BUY, US$626 12 month target) and Disney (HOLD, US$107), a DCF and comparables valuation on Home Depot and a private equity memorandum defended before a practitioner panel"),
        "Operations_Marketing": ("operations and client facing work",
                                 "two years inside a growing SME handling vendors, filings and reporting to fixed deadlines, plus platform and client service cases on Bank of Singapore, Mastercard and a fractional real estate marketplace"),
        "Accounting_Tax_FPA": ("accounting, tax and reporting",
                               "two years preparing quarterly financial statements, running variance and working capital reviews and owning GSTR and TDS filings for an SME without a missed deadline"),
        "Risk_Markets": ("risk and market analysis",
                         "debt service and equity return sensitivities on a power plant financing, a credit and funding stress of a levered receivables book and two equity initiations with explicit calls"),
    }[variant]
    return [
        f"I am applying for the {job['role']} role at {job['company']}. I am completing the Master of Applied Finance at Singapore Management University in January 2027 and hold a B.Com in Finance and Accountancy, and I am available immediately.",
        f"The role sits close to my {angle[0]}: {angle[1]}. Alongside my undergraduate degree I spent two years as a part time financial analyst at an SME, preparing statutory accounts and owning its indirect tax filings end to end.",
        "I work fluently in Excel, Bloomberg and Capital IQ, hold the Bloomberg Market Concepts, Spreadsheet Analysis and ESG certifications, and sit the CFA Level I exam in February 2027. The models and memoranda above are available to walk through on a call.",
        f"Thank you for considering my application. I would welcome the chance to discuss how I can contribute to {job['company']}.",
    ]


def build_letter(job: dict, variant: str, out_dir: Path, ai: AI | None, facts: str, allowed: set[str], tag: str) -> tuple[Path, str]:
    paragraphs = template_letter(job, variant)
    by = "template"
    if ai:
        user = (f"FACTS:\n{facts}\n\nJOB: {job['role']} at {job['company']}\nTAGS: {', '.join(job['tags'])}\n"
                f"JOB DESCRIPTION:\n{job['jd'][:6000]}\n\n"
                "Task: write a cover letter body of exactly 4 paragraphs, 900 to 1400 characters total, no greeting and no sign off. "
                "Paragraph 1: the role and why Salini fits in one or two sentences, availability immediate. "
                "Paragraph 2: the two or three FACTS projects or experiences that match the job best, with their real numbers. "
                "Paragraph 3: the SME experience and the tools and certifications that matter for this job. "
                "Paragraph 4: a specific close offering to walk through the models or memoranda on a call, then thanks.\n"
                'Return {"paragraphs": ["...", "...", "...", "..."]}')

        def validate(obj: dict) -> list[str]:
            probs = []
            ps = obj.get("paragraphs")
            if not isinstance(ps, list) or len(ps) != 4:
                return ["need exactly 4 paragraphs"]
            text = "\n".join(ps)
            if not (700 <= len(text) <= 1700):
                probs.append(f"total length {len(text)} chars, need 700 to 1700")
            probs += content_problems(text, allowed)
            if not re.search(r"immediate", text, re.I):
                probs.append("availability must be stated as immediate")
            if re.search(r"\b(dear|sincerely|regards)\b", text, re.I):
                probs.append("no greeting or sign off inside paragraphs")
            return probs

        obj = ai.json(SYSTEM_PROMPT, user, validate)
        if obj:
            paragraphs = [dedash(americanize(p.strip())) for p in obj["paragraphs"]]
            by = ai.used
    tpl = (TEMPLATES / "cover_letter.html").read_text(encoding="utf-8")
    addressee = job["contact_name"] or f"Hiring Team, {job['company']}, Singapore"
    greeting = f"Dear {salutation(job['contact_name'])}," if job["contact_name"] else "Dear Hiring Team,"
    body = "\n".join(f"<p>{html.escape(p, quote=False)}</p>" for p in paragraphs)
    doc = (tpl.replace("{{ROLE}}", html.escape(job["role"])).replace("{{COMPANY}}", html.escape(job["company"]))
           .replace("{{TAG}}", tag).replace("{{DATE}}", dt.date.today().strftime("%-d %B %Y") if os.name != "nt" else dt.date.today().strftime("%d %B %Y"))
           .replace("{{ADDRESSEE}}", html.escape(addressee)).replace("{{GREETING}}", html.escape(greeting))
           .replace("{{PARAGRAPHS}}", body))
    out = out_dir / f"CoverLetter_Salini_Sadangi_{slug(job['company'])}.html"
    out.write_text(doc, encoding="utf-8")
    return out, by


def template_email(job: dict) -> tuple[str, str]:
    role, co = job["role"], job["company"]
    if job["mode"] == "direct":
        subject = f"Application for {role}"
        body = (f"Dear {job['contact_name'] or 'Hiring Team'},\n\n"
                f"I am writing to apply for the {role} position at {co}. I am completing the Master of Applied Finance at Singapore Management University in January 2027, hold a B.Com in Finance and Accountancy, and am available immediately.\n\n"
                f"My resume and cover letter are attached. In short: two years of part time financial reporting and tax compliance at an SME, coauthored equity initiations on Mastercard and Disney, private equity and infrastructure memoranda, and Bloomberg Market Concepts, Spreadsheet Analysis and ESG certifications.\n\n"
                f"I would welcome a conversation about the role and can walk through any of the models on a call.\n\n"
                f"Kind regards,\nSalini Sadangi\n+65 9357 4381 · {EMAIL}\nhttps://saliniportfolionextjs.vercel.app")
    else:
        subject = f"Following up on my application for {role}"
        body = (f"Dear {job['contact_name'] or 'Hiring Team'},\n\n"
                f"I submitted an application for the {role} position at {co} through {job['portal'] or 'your careers portal'} and wanted to introduce myself directly.\n\n"
                f"I am completing the Master of Applied Finance at Singapore Management University in January 2027 and am available immediately. My background: two years of part time financial reporting and tax compliance at an SME, coauthored equity initiations on Mastercard and Disney, private equity and infrastructure memoranda, and Bloomberg Market Concepts, Spreadsheet Analysis and ESG certifications.\n\n"
                f"I have attached my resume for convenience and would be glad to discuss the role at your convenience.\n\n"
                f"Kind regards,\nSalini Sadangi\n+65 9357 4381 · {EMAIL}\nhttps://saliniportfolionextjs.vercel.app")
    return subject, body


def build_email(job: dict, out_dir: Path, ai: AI | None, facts: str, allowed: set[str]) -> tuple[Path, str]:
    subject, body = template_email(job)
    by = "template"
    if ai:
        kind = ("a direct application email with resume and cover letter attached" if job["mode"] == "direct"
                else f"a short follow up email after applying through {job['portal'] or 'the careers portal'}")
        user = (f"FACTS:\n{facts}\n\nJOB: {job['role']} at {job['company']}\nRECIPIENT: {job['contact_name'] or 'Hiring Team'}\n"
                f"JOB DESCRIPTION:\n{job['jd'][:4000]}\n\n"
                f"Task: write {kind}. 90 to 160 words in the body, 3 short paragraphs, greeting 'Dear <name>,' and sign off "
                "'Kind regards,' then the name only (contact lines are added by the program). Mention availability is immediate. "
                "Subject line under 80 characters.\n"
                'Return {"subject": "...", "body": "..."}')

        def validate(obj: dict) -> list[str]:
            probs = []
            s, b = obj.get("subject", ""), obj.get("body", "")
            if not s or len(s) > 90:
                probs.append("subject missing or over 90 chars")
            words = len(b.split())
            if not (70 <= words <= 200):
                probs.append(f"body is {words} words, need 70 to 200")
            probs += content_problems(b, allowed)
            if not re.search(r"immediate", b, re.I):
                probs.append("availability must be stated as immediate")
            return probs

        obj = ai.json(SYSTEM_PROMPT, user, validate)
        if obj:
            subject = dedash(americanize(obj["subject"].strip()))
            body = dedash(americanize(obj["body"].strip()))
            body = re.sub(r"\n+\s*Salini Sadangi\s*$", "", body).rstrip()
            body += f"\nSalini Sadangi\n+65 9357 4381 · {EMAIL}\nhttps://saliniportfolionextjs.vercel.app"
            by = ai.used
    to = job["contact_email"] or ""
    mailto = f"mailto:{to}?" + urllib.parse.urlencode({"subject": subject, "body": body}, quote_via=urllib.parse.quote)
    out = out_dir / f"Email_{slug(job['company'])}.txt"
    out.write_text(f"To: {to or '[add recipient]'}\nSubject: {subject}\n\n{body}\n\n"
                   f"---\nAttach: Salini_Sadangi_Resume.pdf" + (", CoverLetter PDF" if job["mode"] == "direct" else "") +
                   f"\nOpen in your mail app (copy into the address bar):\n{mailto}\n", encoding="utf-8")
    return out, by


# --------------------------------------------------------------------------- tracker


def append_tracker(job: dict, variant: str, letter_rel: str, notes: str) -> str:
    if not TRACKER_CSV.exists():
        return "tracker csv missing, skipped"
    with TRACKER_CSV.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = reader.fieldnames or []
    key = (job["company"].strip().lower(), job["role"].strip().lower())
    for r in rows:
        if (r.get("company", "").strip().lower(), r.get("role", "").strip().lower()) == key:
            return f"already in tracker as id {r.get('id')}, no new row"
    next_id = max([int(r["id"]) for r in rows if r.get("id", "").isdigit()] + [0]) + 1
    today = dt.date.today().isoformat()
    row = {k: "" for k in fields}
    row.update({
        "id": str(next_id), "company": job["company"], "role": job["role"], "location": job["location"],
        "work_mode": "", "source_url": job["url"], "date_added": today, "deadline": job["deadline"],
        "status": "Prepared", "priority": "Medium", "resume_variant": f"Resume_Salini_Sadangi_Broad_{variant}",
        "cover_letter_path": letter_rel, "contact_person": job["contact_name"],
        "next_action": "Send email" if job["mode"] == "direct" else "Submit on portal, then send follow up",
        "jd_summary": " ".join(job["jd"].split())[:300], "jd_full": job["jd"], "notes": notes,
    })
    with TRACKER_CSV.open("a", encoding="utf-8", newline="") as f:
        csv.DictWriter(f, fieldnames=fields).writerow(row)
    msg = f"added as id {next_id}"
    build = TRACKER_DIR / "build_tracker.py"
    if build.exists():
        r = subprocess.run([sys.executable, str(build)], capture_output=True, text=True, cwd=TRACKER_DIR)
        msg += "; tracker rebuilt" if r.returncode == 0 else f"; tracker rebuild failed (pip install openpyxl): {r.stderr.strip()[-120:]}"
    return msg


# --------------------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser(description="Build one job application for Salini Sadangi.")
    ap.add_argument("--jd-file", help="read the job description from this file")
    ap.add_argument("--ai", action="store_true", help="use AI without asking")
    ap.add_argument("--no-ai", action="store_true", help="template mode, no API calls")
    ap.add_argument("--variant", choices=list(VARIANT_KEYWORDS), help="force a resume variant")
    args = ap.parse_args()

    load_env()
    print("\nSalini application builder\n" + "=" * 26)

    # 1. preflight
    chrome = find_chrome()
    say(f"PDF engine: {'found' if chrome else 'NOT found, HTML only (install Chrome or set CHROME_PATH in .env)'}")
    chain = available_providers()
    say("AI providers: " + (", ".join(p.name for p in chain) if chain else "none configured (see .env.example)"))

    # 2. AI toggle, asked up front
    use_ai = False
    if args.no_ai:
        use_ai = False
    elif args.ai:
        use_ai = bool(chain)
    elif chain:
        use_ai = ask_yes("Use AI to tailor the summary, cover letter and email?", default=True)
    if use_ai and not chain:
        say("No provider available, continuing in template mode.")
        use_ai = False
    if use_ai and chain and chain[0].name == "gemini":
        say("Note: Gemini free tier may use submitted text to improve Google models.")

    # 3. inputs
    print()
    company = ask("Company")
    role = ask("Job role / title")
    if not company or not role:
        print("Company and role are required.")
        return 1
    location = ask("Location", "Singapore")
    tags = [t.strip() for t in ask("Tags, comma separated (optional)").split(",") if t.strip()]
    url = ask("Posting URL (optional)")
    deadline = ask("Deadline YYYY-MM-DD (optional)")
    mode = "direct" if ask("How will you apply? direct email / portal", "portal").lower().startswith("d") else "portal"
    portal = ask("Portal name (optional)") if mode == "portal" else ""
    contact_name = ask("Contact name (optional)")
    contact_email = ask("Contact email (optional)")
    if args.jd_file:
        jd = Path(args.jd_file).read_text(encoding="utf-8", errors="ignore").strip()
    else:
        jd = ask_multiline("Job description")
    if not jd:
        say("Empty job description; variant selection will use role and tags only.")
    job = dict(company=company, role=role, location=location, tags=tags, url=url, deadline=deadline, mode=mode,
               portal=portal, contact_name=contact_name, contact_email=contact_email, jd=jd)

    # 4. variant
    ranked = pick_variant(role, jd, tags)
    variant = args.variant or ranked[0][0]
    print()
    say("Variant match: " + ", ".join(f"{n} ({s})" for n, s in ranked[:3]))
    if not args.variant:
        choice = ask("Resume variant", variant)
        if choice in VARIANT_KEYWORDS:
            variant = choice
    say(f"Using {variant}: {VARIANT_LABEL[variant]}")

    # 5. allowed numbers = facts + chosen variant
    facts = FACTS.read_text(encoding="utf-8")
    variant_text = strip_tags((VARIANTS / f"Resume_Salini_Sadangi_Broad_{variant}.html").read_text(encoding="utf-8"))
    allowed = numbers_in(facts) | numbers_in(variant_text) | numbers_in(jd) | {"2027", "2026", "2025", "2024", "2022"}

    out_dir = APPS / f"{slug(company)}_{slug(role)}"
    out_dir.mkdir(parents=True, exist_ok=True)
    log: list[str] = []
    ai = AI(chain, log) if use_ai else None

    # 6. documents
    print()
    say("Building resume...")
    resume_html, rinfo = build_resume(variant, out_dir, ai, job, facts, allowed)
    tag = strip_tags(re.search(r'<div class="tag">(.*?)</div>', resume_html.read_text(encoding="utf-8")).group(1))
    say("Building cover letter...")
    letter_html, letter_by = build_letter(job, variant, out_dir, ai, facts, allowed, html.escape(tag, quote=False))
    say("Building email...")
    email_txt, email_by = build_email(job, out_dir, ai, facts, allowed)

    # 7. house-style audit on the human-facing text
    audit = []
    letter_text = strip_tags(re.search(r'<div class="re">.*', letter_html.read_text(encoding="utf-8"), re.S).group(0))
    email_text = email_txt.read_text(encoding="utf-8").split("---")[0]
    for label, txt in (("cover letter", letter_text), ("email", email_text)):
        if has_dash(txt):
            audit.append(f"{label}: a dash survived, read it before sending")
        if not re.search(r"immediate", txt, re.I):
            audit.append(f"{label}: availability not stated as immediate")
    if not audit:
        audit.append("no dashes, availability immediate, numbers checked against facts.md")

    # 8. PDFs
    say("Rendering PDFs..." if chrome else "Skipping PDFs (no Chrome).")
    resume_pdf = html_to_pdf(chrome, resume_html)
    letter_pdf = html_to_pdf(chrome, letter_html)

    # 9. notes + tracker
    notes = (f"# {company} · {role}\n\nBuilt {dt.datetime.now():%Y-%m-%d %H:%M}\n\n"
             f"- Variant: {variant} ({VARIANT_LABEL[variant]}); match scores: {ranked[:3]}\n"
             f"- Summary by: {rinfo['summary_by']} · Letter by: {letter_by} · Email by: {email_by}\n"
             f"- Mode: {mode}{' via ' + portal if portal else ''}; contact: {contact_name or 'n/a'} {contact_email}\n"
             f"- Tags: {', '.join(tags) or 'none'}\n- URL: {url or 'n/a'}\n- Deadline: {deadline or 'n/a'}\n"
             f"- Checks: {'; '.join(audit)}\n"
             + ("- AI log:\n" + "".join(f"  - {l}\n" for l in log) if log else "")
             + f"\n## Job description\n\n{jd or '(none pasted)'}\n")
    (out_dir / "notes.md").write_text(notes, encoding="utf-8")
    letter_rel = str((letter_pdf or letter_html).relative_to(ROOT))
    tracker_msg = append_tracker(job, variant, letter_rel, f"built by apply.py; summary {rinfo['summary_by']}, letter {letter_by}, email {email_by}")

    # 10. report
    print("\nDone.")
    say(f"Folder: {out_dir.relative_to(ROOT)}")
    for p in (resume_pdf or resume_html, letter_pdf or letter_html, email_txt, out_dir / "notes.md"):
        say(f"  {p.name}")
    say(f"Tracker: {tracker_msg}")
    for a in audit:
        say(f"Check: {a}")
    if log:
        say("AI: " + log[-1])
    say("Read everything once before sending. The program does not send email.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(130)
