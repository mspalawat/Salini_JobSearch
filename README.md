# Salini JobSearch

Everything needed to produce one complete job application in a few minutes: a one-page resume matched
to the role, a cover letter, an email draft, notes, and a row in the application tracker.

Two ways to run it. Pick whichever fits the moment.

| | `apply.py` | `apply_paste.py` |
|---|---|---|
| Where the writing happens | API call from the terminal (Gemini, Groq or local Llama) | Any AI chat in the browser (ChatGPT, Gemini, Claude, Copilot) |
| Needs an API key | Yes, free tier (or no key for template-only mode) | No |
| What you type | Company, role, job description | Paste the block the chat gave you |
| Who checks the facts | The program, automatically, with retries | The program, before building; it tells you what to send back to the chat |
| Output | Identical | Identical |

## Setup, once

```bash
git clone git@github.com:mspalawat/Salini_JobSearch.git
cd Salini_JobSearch
```

Needs Python 3.10 or newer and Google Chrome (for the PDFs). No Python packages are required.
Optional: `pip install openpyxl` to also rebuild the Excel version of the tracker.

For `apply.py` with AI, copy `.env.example` to `.env` and paste at least one key:

| Provider | Key | Notes |
|---|---|---|
| Gemini | https://aistudio.google.com/apikey | Best quality, no card. Free tier may use your text to improve Google models. |
| Groq | https://console.groq.com/keys | Llama 3.3 70B, fast, stricter rate limits. |
| Ollama | https://ollama.com then `ollama pull llama3.1` | Fully local, needs 16 GB RAM or more. |

The program tries them in that order and falls back to the built-in templates if none works.

## Way 1: terminal with API

```bash
python3 apply.py
```

It asks: use AI or not, company, role, location, tags, URL, deadline, direct email or portal, contact
name and email, then the job description (paste it, then type `END` on its own line). It proposes the
closest resume variant and lets you override it.

Shortcuts:

```bash
python3 apply.py --jd-file jd.txt            # job description from a file
python3 apply.py --no-ai                     # templates only, zero API calls
python3 apply.py --ai --variant Risk_Markets # no questions about AI or variant
```

## Way 2: browser chat plus terminal

1. Open your AI chat. Upload `facts.md` (or paste it). Paste the contents of `AI_KICKOFF.md`.
   The chat should answer "Ready. Send me the first job."
2. Send it the job description with the company, role, and whether you apply by email or portal.
3. It replies with a block between `=== SALINI APPLICATION START ===` and `=== SALINI APPLICATION END ===`.
4. In the terminal:

```bash
python3 apply_paste.py
```

   Paste the block, press Enter, type `END` on its own line. Or save the block to a file:

```bash
python3 apply_paste.py --file block.txt --jd-file jd.txt
```

If the program prints `REJECTED ...`, copy that line back into the chat. It fixes only that and
resends the block. Run again.

## What you get

`applications/<Company>_<Role>/`

- `Salini_Sadangi_Resume.pdf` and `.html`: the matched variant with a summary written for this job
- `CoverLetter_Salini_Sadangi_<Company>.pdf` and `.html`
- `Email_<Company>.txt`: subject, body, attachment reminder, and a `mailto:` link you can paste into
  the browser address bar to open a prefilled draft
- `notes.md`: job description, which model or chat wrote what, and the checks that ran

Plus one row in `tracker/salini_jobs.csv` (no duplicates on company + role) and a rebuilt
`tracker/Salini_Job_Tracker.html`. Open that file in a browser to see the pipeline.

Nothing is sent anywhere. Attach the PDFs, read once, send.

## Guardrails that run every time

- Every number in the summary, letter and email must already exist in `facts.md`, the chosen resume,
  or the job description. Anything else is rejected.
- Micron, Kairos and Mantike are rejected (not Salini's projects). "Holds a Master's" is rejected (still
  studying). Tools not in facts.md (SQL, VBA, Power BI, Java) are rejected.
- Letters and emails are stripped of em dashes, en dashes and hyphens, converted to American spelling,
  and must state immediate availability.

## Files

| Path | What it is |
|---|---|
| `apply.py` | API-driven builder; also the shared engine both programs use |
| `apply_paste.py` | Paste-mode builder, no API |
| `AI_KICKOFF.md` | Prompt to start any chat as the writer |
| `facts.md` | The only facts about Salini any AI is allowed to use. Edit this when something changes. |
| `variants/` | Six one-page resumes plus the master |
| `templates/cover_letter.html` | Letter layout, same typography as the resumes |
| `tracker/` | `salini_jobs.csv` is the source of truth; `build_tracker.py` rebuilds the HTML and XLSX |
| `tools/build_salini_broad.py` | Regenerates the six variants from the master (expects the parent JobSearch folder) |
| `.env.example` | Keys and options for `apply.py` |

## Resume variants

| Variant | Use for |
|---|---|
| Infra_RealEstate | Infrastructure, energy, real estate, REITs, fund management |
| InvestmentBanking | IB, M&A, corporate finance, FIG |
| EquityResearch | Research, investment analyst, equities, asset management |
| Operations_Marketing | Operations, client service, marketing, HR, investor relations |
| Accounting_Tax_FPA | Accounting, tax, FP&A, finance intern, audit |
| Risk_Markets | Risk, treasury, markets, trading, structured products |

## When facts change

Edit `facts.md`. If the master resume changes too, regenerate the variants and commit. Both programs
read these files at run time, so a change takes effect on the next run.
