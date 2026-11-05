#!/usr/bin/env python3
"""
apply_paste.py — build an application from a block you got out of an online AI chat. No API key needed.

The loop:
    1. Open any AI chat (ChatGPT, Gemini, Claude, Copilot). Upload facts.md and paste AI_KICKOFF.md.
    2. Give the chat the job description. It replies with a block between
       === SALINI APPLICATION START === and === SALINI APPLICATION END ===.
    3. Run this program and paste that block (or save it to a file and pass --file).
    4. The program validates the block, builds the resume PDF, cover letter PDF, email draft and
       notes, and logs the job in the tracker. Exactly the same outputs as apply.py.

    python3 apply_paste.py                 # paste the block, finish with END on its own line
    python3 apply_paste.py --file block.txt
    python3 apply_paste.py --file block.txt --jd-file jd.txt   # keep the full job description in notes

The chat writes the prose; this program checks it (numbers against facts.md, no dashes, American
spelling, immediate availability, no projects that are not Salini's) and does the layout.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apply as A  # noqa: E402  (the shared engine)

START, END = "=== SALINI APPLICATION START ===", "=== SALINI APPLICATION END ==="
SCALAR = ["COMPANY", "ROLE", "LOCATION", "TAGS", "VARIANT", "MODE", "PORTAL", "CONTACT_NAME", "CONTACT_EMAIL",
          "URL", "DEADLINE", "TAG", "EMAIL_SUBJECT", "JD_SUMMARY"]
BLOCKS = ["SUMMARY", "LETTER", "EMAIL_BODY", "JD"]
KEYS = set(SCALAR + BLOCKS)


def read_block(args) -> str:
    if args.file:
        return Path(args.file).read_text(encoding="utf-8", errors="ignore")
    print("Paste the block from the chat, then type END on its own line.")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "END" and any(END in l for l in lines):
            break
        if line.strip() == "END" and not lines:
            continue
        lines.append(line)
        if END in line:
            break
    return "\n".join(lines)


def parse_block(text: str) -> dict:
    """KEY: value lines; block keys (SUMMARY, LETTER, EMAIL_BODY, JD) run until the next KEY: line."""
    if START in text:
        text = text.split(START, 1)[1]
    if END in text:
        text = text.split(END, 1)[0]
    text = re.sub(r"^```.*$", "", text, flags=re.M)  # stray code fences
    data: dict[str, str] = {}
    key = None
    buf: list[str] = []
    for raw in text.splitlines():
        m = re.match(r"^\s*([A-Z_]+)\s*:\s*(.*)$", raw)
        if m and m.group(1) in KEYS:
            if key:
                data[key] = "\n".join(buf).strip()
            key, buf = m.group(1), [m.group(2)]
        elif key:
            buf.append(raw)
    if key:
        data[key] = "\n".join(buf).strip()
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description="Build an application from a pasted chat block.")
    ap.add_argument("--file", help="file holding the block from the chat")
    ap.add_argument("--jd-file", help="full job description to keep in notes and the tracker")
    args = ap.parse_args()

    A.load_env()
    print("\nSalini application builder (paste mode)\n" + "=" * 39)
    chrome = A.find_chrome()
    A.say(f"PDF engine: {'found' if chrome else 'NOT found, HTML only (install Chrome or set CHROME_PATH in .env)'}")

    data = parse_block(read_block(args))
    missing = [k for k in ("COMPANY", "ROLE", "SUMMARY", "LETTER", "EMAIL_SUBJECT", "EMAIL_BODY") if not data.get(k)]
    if missing:
        print(f"\nBlock is missing: {', '.join(missing)}. Ask the chat to resend the full block.")
        return 1

    tags = [t.strip() for t in data.get("TAGS", "").split(",") if t.strip()]
    jd = Path(args.jd_file).read_text(encoding="utf-8", errors="ignore").strip() if args.jd_file else data.get("JD", "")
    mode = "direct" if data.get("MODE", "portal").lower().startswith("d") else "portal"
    job = dict(company=data["COMPANY"], role=data["ROLE"], location=data.get("LOCATION") or "Singapore", tags=tags,
               url=data.get("URL", ""), deadline=data.get("DEADLINE", ""), mode=mode, portal=data.get("PORTAL", ""),
               contact_name=data.get("CONTACT_NAME", ""), contact_email=data.get("CONTACT_EMAIL", ""),
               jd=jd or data.get("JD_SUMMARY", ""))

    ranked = A.pick_variant(job["role"], job["jd"], tags)
    variant = data.get("VARIANT", "").strip()
    if variant not in A.VARIANT_KEYWORDS:
        variant = ranked[0][0]
    A.say(f"Variant: {variant} ({A.VARIANT_LABEL[variant]}); keyword match {ranked[:2]}")

    # validation, same rules apply.py enforces on API output
    facts = A.FACTS.read_text(encoding="utf-8")
    variant_text = A.strip_tags((A.VARIANTS / f"Resume_Salini_Sadangi_Broad_{variant}.html").read_text(encoding="utf-8"))
    allowed = A.numbers_in(facts) | A.numbers_in(variant_text) | A.numbers_in(job["jd"]) | {"2027", "2026", "2025", "2024", "2022"}
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", data["LETTER"]) if p.strip()]
    problems = {
        "summary": A.validate_summary({"summary": data["SUMMARY"], "tag": data.get("TAG", "")}, allowed),
        "letter": A.validate_letter({"paragraphs": paragraphs}, allowed),
        "email": A.validate_email({"subject": data["EMAIL_SUBJECT"], "body": data["EMAIL_BODY"]}, allowed),
    }
    log = []
    hard = {"summary": [], "letter": [], "email": []}
    for part, probs in problems.items():
        for pr in probs:
            # invented facts block the build; length and formatting slips only warn
            if re.search(r"numbers not in FACTS|not Salini's|holds a Master|tool that is not", pr):
                hard[part].append(pr)
            else:
                log.append(f"{part} warning: {pr}")
    for part, probs in hard.items():
        if probs:
            print(f"\nREJECTED {part}: " + "; ".join(probs))
    if any(hard.values()):
        print("Paste the problems above back into the chat, ask it to fix them using facts.md only, and run again.")
        return 2
    for l in log:
        A.say(l)

    out_dir = A.APPS / f"{A.slug(job['company'])}_{A.slug(job['role'])}"
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = data.get("TAG", "")
    if not tag:
        src = (A.VARIANTS / f"Resume_Salini_Sadangi_Broad_{variant}.html").read_text(encoding="utf-8")
        tag = A.strip_tags(re.search(r'<div class="tag">(.*?)</div>', src).group(1))

    A.say("Building resume...")
    resume_html = A.write_resume(variant, out_dir, data["SUMMARY"], tag)
    A.say("Building cover letter...")
    letter_html = A.write_letter(job, out_dir, paragraphs, tag)
    A.say("Building email...")
    email_txt = A.write_email(job, out_dir, data["EMAIL_SUBJECT"], data["EMAIL_BODY"])
    log.insert(0, "source: pasted block from online chat")
    A.finish(job, variant, ranked, out_dir, chrome, resume_html, letter_html, email_txt,
             {"summary": "chat", "letter": "chat", "email": "chat"}, log)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(130)
