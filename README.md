# Salini JobSearch

One command builds a complete job application: tailored resume, cover letter, email draft, notes, and a
tracker row.

## Setup (once)

```bash
git clone git@github.com:mspalawat/Salini_JobSearch.git
cd Salini_JobSearch
cp .env.example .env        # then paste your keys into .env
pip install openpyxl        # optional, only for the Excel tracker
```

Requirements: Python 3.10+, Google Chrome (for PDFs). Nothing else.

Free AI keys (any one is enough, all three is best):

| Provider | Where | Notes |
|---|---|---|
| Gemini | https://aistudio.google.com/apikey | Best quality. Free tier may use your text to improve Google models. |
| Groq | https://console.groq.com/keys | Llama 3.3 70B, fast, stricter rate limits. |
| Ollama | https://ollama.com, then `ollama pull llama3.1` | Fully local, needs 16 GB RAM or more. |

No key at all still works: the program then uses the built-in templates.

## Use

```bash
python3 apply.py
```

It asks, in order: use AI or not, company, role, location, tags, URL, deadline, how you apply
(direct email or portal), contact name and email, then the job description (paste, then type `END`
on its own line). It picks the closest resume variant and lets you override it.

Shortcuts:

```bash
python3 apply.py --jd-file jd.txt          # job description from a file
python3 apply.py --no-ai                   # templates only, no API calls
python3 apply.py --ai --variant Risk_Markets
```

Output lands in `applications/<Company>_<Role>/`:

- `Salini_Sadangi_Resume.pdf` (+ `.html`)
- `CoverLetter_Salini_Sadangi_<Company>.pdf` (+ `.html`)
- `Email_<Company>.txt` with subject, body and a `mailto:` link
- `notes.md` with the job description, which model wrote what, and the checks that ran

The tracker row goes into `tracker/salini_jobs.csv` and `tracker/Salini_Job_Tracker.html` is rebuilt.

## Guardrails

- The AI may only use `facts.md`. Every number it writes is checked against that file and the chosen
  resume; anything else is rejected and retried once, then the template text is used.
- Letters and emails are stripped of em dashes, en dashes and hyphens, converted to American spelling,
  and must state immediate availability.
- The program never sends email. Open the `mailto:` link or paste the text, attach the PDFs, read it
  once, then send.

## Resume variants

`variants/` holds six one-page resumes built from the master (`Resume_Salini_Sadangi.html`):
Infra_RealEstate, InvestmentBanking, EquityResearch, Operations_Marketing, Accounting_Tax_FPA,
Risk_Markets. Regenerate with `python3 tools/build_salini_broad.py` after editing the master
(the script expects the master at `resumes/master/` in the parent JobSearch folder).

## Updating facts

Edit `facts.md` when something changes (new certification, new project, graduation). That file is the
only thing the AI reads about Salini.
