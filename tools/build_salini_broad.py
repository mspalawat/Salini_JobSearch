#!/usr/bin/env python3
"""Build broad (field-level) resume variants for Salini Sadangi from the master HTML.

Header, CSS and section icons are lifted from resumes/master/Resume_Salini_Sadangi.html so
the variants stay visually identical to the master. Content follows the claims discipline in
Madhvendra_Master_Profile.md (Mastercard $626 = 12-month target; Okapi = three-method
reconciliation, USD 14-16M; Fujitec = passed at the ask, no countering).

Usage: python3 resumes/tools/build_salini_broad.py   (run from JobSearch root)
Outputs resumes/Resume_Salini_Sadangi_Broad_<Field>.html + .pdf and copies them to
Salini_JobSearch/variants/.
"""
import re, subprocess, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "resumes/master/Resume_Salini_Sadangi.html"
OUT_DIR = ROOT / "resumes"
COPY_DIR = ROOT / "Salini_JobSearch/variants"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

master = MASTER.read_text(encoding="utf-8")
HEAD = master[: master.index("</header>") + len("</header>")]
ICON = {}
for name in ["Summary", "Education", "Experience", "Skills"]:
    ICON[name] = re.search(r"<h2>(<svg(?:(?!</svg>).)*</svg>)" + name + "</h2>", master, re.S).group(1)
ICON["Projects"] = re.search(r"<h2>(<svg(?:(?!</svg>).)*</svg>)Research, Valuation", master, re.S).group(1)
LINK_ICON = re.search(r'(<svg class="ic" width="10".*?</svg>)', master, re.S).group(1)
PORTFOLIO = "https://saliniportfolionextjs.vercel.app/work/"

def h2(icon, title):
    return f"<h2>{ICON[icon]}{title}</h2>"

def entry(title, right, bullets, slug=None, sub=None):
    if slug:
        title = f'<a class="plink" href="{PORTFOLIO}{slug}">{title} {LINK_ICON}</a>'
    s = f'<div class="entry">\n<div class="row"><span class="l">{title}</span><span class="r">{right}</span></div>'
    if sub:
        s += f'\n<div class="sub">{sub}</div>'
    if bullets:
        s += "\n<ul>" + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>"
    return s + "</div>"

EDUCATION = (
    h2("Education", "Education")
    + entry("Singapore Management University", "Singapore · 2025 – Jan 2027", [], sub="M.Sc., Applied Finance")
    + entry("Christ University, Bengaluru", "India · 2020 – 2024", [], sub="B.Com., Finance &amp; Accountancy")
)

# ---- Project library (canonical, claims-checked) -----------------------------------------
P = {
    "MA": dict(title="Mastercard Inc. (NYSE: MA) — Equity Research Initiation", right="Equity Research · SMU · co-authored", slug="mastercard",
        bullets=["Co-authored an initiation with a <b>STRONG BUY and a US$626 12-month target (+25%)</b>, an 80/20 blend of FCFF DCF and EV/EBITDA / P/E comparables over a full 3-statement model (8.46% WACC, 3.2% terminal growth); thesis: Value-Added Services compounding at a 16.3% CAGR."]),
    "DIS": dict(title="The Walt Disney Co. (NYSE: DIS) — Initiation of Coverage", right="Equity Research · SMU · co-authored", slug="disney",
        bullets=["Contributed to a 24-page initiation: <b>HOLD, US$107 target</b> via a 5-year FCFF DCF (9.27% WACC) cross-checked against a Sum-of-the-Parts bear/base/bull envelope (US$84 / 107 / 176), with segment theses across Experiences, DTC and Linear Networks."]),
    "FUJ": dict(title="Fujitec Co. (TSE: 6406) — PE Co-Investment Memorandum", right="APECS PE Case Competition 2026 · team", slug="fujitec",
        bullets=["Evaluated a US$1.0bn minority co-investment (~22%) alongside EQT in a take-private on a 3-statement model; recommended <b>passing at the US$4.1bn ask</b>: 17.2% IRR / 2.19× against a 20% hurdle, which clears only at ~US$3.5bn EV (20.7% / 2.53×)."]),
    "OKAPI": dict(title="Okapi Solar — PE/VC Investment Memorandum &amp; Valuation", right="Specialty Finance · SMU · group", slug="okapi-solar",
        bullets=["Reframed a Malaysian rooftop-solar startup as a <b>~5% NIM specialty-finance lender</b>; triangulated DCF / VC / NSV methods to a defensible <b>~US$15–16M EV</b> and a diluted ~1.9× / ~16% XIRR, gating the proceed on credit-loss, funding-line and SAFE-dilution diligence."]),
    "VN": dict(title="Vietnam Gas-Fired Power Plant — Investment Memorandum", right="Project &amp; Infrastructure Financing · SMU · group", slug="vietnam-power",
        bullets=["Authored an investment memorandum for a gas-fired power plant and presented it to a mock investment committee (<b>conditional approval</b>); sized the debt, structured the capital stack and ran debt-service-coverage and equity-return sensitivities across financing scenarios."]),
    "HD": dict(title="Home Depot (NYSE: HD) — Equity Valuation", right="Equity Analysis · SMU · group", slug="home-depot",
        bullets=["Built a DCF intrinsic valuation cross-checked against comparable-company analysis (EV/EBITDA, P/E) to frame a fair-value range and investment view."]),
    "BOS": dict(title="Bank of Singapore — EAM / Wealth-Management Strategy Case", right="Investment Advisory &amp; Wealth Management · SMU · group", slug="bank-of-singapore",
        bullets=["Analyzed BOS's External Intermediaries Desk (EAM): centralized vs decentralized service models, the retrocession conflict and onboarding friction; recommended repositioning as an <b>&ldquo;Asian Gateway&rdquo; custodian</b> on the OCBC ecosystem and Aa1 credit strength."]),
    "ARR": dict(title="Arrived — Fractional Real-Estate Investment Platform", right="Financial Analytics &amp; Innovation · SMU · group", slug=None,
        bullets=["Analyzed the business model and investment case of a fractional real-estate ownership platform: property-level unit economics, investor return profile, fee structure and platform risks."]),
    "IMP": dict(title="Impaakt — Sustainable Finance &amp; Impact Measurement Case", right="Sustainable Finance &amp; Impact Investing · SMU · awarded an A", slug=None,
        bullets=["Assessed an impact-measurement framework used in capital-allocation decisions, scoring real-world company impact from public disclosures into a concise, evidence-backed report."]),
}

def proj(key, **over):
    d = dict(P[key]); d.update(over)
    return entry(d["title"], d["right"], d["bullets"], slug=d.get("slug"))

EXP_DEFAULT = [
    "Prepared quarterly P&amp;L, balance-sheet and cash-flow statements for an SME food-products business through the month-end close and budgeting cycle, alongside a full-time B.Com.",
    "Ran variance and working-capital reviews in Excel to flag cost overruns and tighten the reporting pack ahead of senior review.",
    "Handled indirect-tax compliance end-to-end — <b>GSTR-1 / GSTR-3B filings and TDS</b> — owning the statutory filing cadence and supporting documentation.",
]
def experience(bullets=EXP_DEFAULT, right="Bhubaneswar, India · Jun 2022 – Jun 2024"):
    return h2("Experience", "Experience") + entry("Jeevan Amrit Food Products Pvt. Ltd. — Financial Analyst (Part-Time)", right, bullets)

CERTS = "<b>Certifications:</b> Bloomberg Market Concepts, Spreadsheet Analysis &amp; ESG (Oct 2026) · CFA Level I candidate (Feb 2027) · Advanced Excel — Christ University."
LANG = "<b>Languages:</b> English &amp; Hindi (fluent) · French (conversational). <b>Activities:</b> Finance Club Case Competition, Christ University — 3rd place (2022)."
AVAIL = "<b>Availability:</b> Immediate, internship or full-time, Singapore; M.Sc. completes January 2027."

def skills(rows):
    return h2("Skills", "Skills") + "".join(f'<div class="skill"><b>{k}:</b> {v}</div>' for k, v in rows)

def extras(*lines):
    return "".join(f'<div class="extra">{l}</div>' for l in lines)

# ---- Variants ------------------------------------------------------------------------------
V = {}

V["Infra_RealEstate"] = dict(
    tag="Infrastructure · Real Assets · Project Finance",
    summary="Master of Applied Finance candidate at SMU with a B.Com in Finance &amp; Accountancy and two years of part-time financial-reporting experience at an SME. Project work follows the real-asset investment lifecycle: a gas-fired power plant financing memo taken through debt sizing and coverage sensitivities to a mock investment committee, a solar-leasing platform underwritten as a receivables book, a US$1.0bn take-private co-investment tested against a return hurdle, a fractional real-estate platform's unit economics and an impact-measurement case. Advanced Excel modeler with Bloomberg and Capital IQ exposure; Bloomberg ESG certified; CFA Level I candidate (Feb 2027), seeking infrastructure, real-estate and project-finance roles in Singapore.",
    order=["projects", "experience"],
    ptitle="Infrastructure, Real-Asset &amp; Investment Analysis — Coursework &amp; Competitions",
    projects=[proj("VN"), proj("OKAPI"), proj("FUJ"), proj("ARR"),
              proj("DIS", bullets=["Contributed to a 24-page initiation (<b>HOLD, US$107 target</b>) via FCFF DCF and a Sum-of-the-Parts envelope; the Experiences segment thesis (parks, resorts, cruise lines) rested on hospitality-demand and capex-cycle assumptions."]),
              proj("IMP", bullets=["Assessed an impact-measurement framework used in capital-allocation decisions; relevant to green and social asset classification in infrastructure and real-estate portfolios. Awarded an A."])],
    skills=[("Infrastructure &amp; Real Assets", "Project-finance capital structuring, debt sizing, DSCR and equity-return sensitivities, feasibility and market research, receivables and credit analysis, returns analysis (IRR, equity multiple), investment-approval papers"),
            ("Valuation &amp; Reporting", "3-statement modeling, DCF (FCFF), comparables, scenario analysis, financial-statement preparation, performance tracking against budget"),
            ("Tools", "Microsoft Excel (advanced financial modeling), Bloomberg Terminal, Capital IQ, PowerPoint")],
    extra=["<b>Other coursework:</b> Mastercard — co-authored initiation, US$626 12-month target · Home Depot — DCF and comparables valuation · Bank of Singapore — EAM strategy case.", CERTS, LANG, AVAIL],
)

V["InvestmentBanking"] = dict(
    tag="Investment Banking · Corporate Finance · Valuation",
    summary="Master of Applied Finance candidate at SMU with a B.Com in Finance &amp; Accountancy and two years of part-time financial-reporting experience. Deal and valuation work: a US$1.0bn take-private co-investment argued on returns against a hurdle, a STRONG BUY initiation on Mastercard over a full 3-statement model, a specialty-finance valuation reconciled across three methods, and a project-financing memorandum approved by a mock investment committee. Fast and exact in Excel and PowerPoint; Bloomberg BMC, Spreadsheet Analysis and ESG certified; CFA Level I candidate (Feb 2027), targeting investment banking and corporate-finance roles in Singapore.",
    order=["projects", "experience"],
    ptitle="Valuation &amp; Transaction Analysis — Coursework &amp; Competitions",
    projects=[proj("FUJ", bullets=P["FUJ"]["bullets"] + ["Built bear/base/bull returns on an EBITDA-growth × exit-multiple framework; defended the recommendation before a practitioner panel."]),
              proj("MA"), proj("OKAPI"), proj("VN"), proj("DIS"),
              proj("BOS", bullets=["Analyzed a private bank's External Intermediaries Desk (service models, retrocession conflict, onboarding friction) and recommended an <b>&ldquo;Asian Gateway&rdquo; custodian</b> repositioning on the OCBC ecosystem and Aa1 credit strength."])],
    skills=[("Corporate Finance", "3-statement financial models, DCF (FCFF), trading comparables, returns analysis for take-privates (IRR, multiple of money), capital-structure and debt sizing, scenario and sensitivity analysis, investment-memorandum and pitch-style writing"),
            ("Accounting", "Financial-statement preparation (P&amp;L, balance sheet, cash flow), month-end close, variance and working-capital analysis"),
            ("Tools", "Microsoft Excel, PowerPoint and Word (advanced), Bloomberg Terminal, Capital IQ")],
    extra=["<b>Other coursework:</b> Home Depot — DCF and comparables valuation · Arrived — real-estate platform case · Impaakt — impact-measurement case, awarded an A.", CERTS, LANG, AVAIL],
)

V["EquityResearch"] = dict(
    tag="Equity Research · Investment Analysis",
    summary="Master of Applied Finance candidate at SMU with a B.Com in Finance &amp; Accountancy, drawn to research for the discipline of putting a view on paper and defending it. Co-authored two equity initiations with explicit calls and targets (Mastercard, Disney), built a DCF-and-comparables valuation on Home Depot, argued a US$1.0bn private-equity position against a return hurdle and reconciled a specialty-finance valuation across three methods. Bloomberg Market Concepts, Spreadsheet Analysis and ESG certified; Capital IQ exposure; CFA Level I candidate (Feb 2027), targeting equity-research and investment-analyst roles in Singapore.",
    order=["projects", "experience"],
    ptitle="Equity Research &amp; Valuation — Coursework &amp; Competitions",
    projects=[proj("MA", bullets=["Co-authored an initiation with a <b>STRONG BUY and a US$626 12-month target (+25%)</b>, an 80/20 blend of FCFF DCF and EV/EBITDA / P/E comparables.",
                                  "Built the DCF on an 8.46% WACC and 3.2% terminal growth over a full 3-statement model, with sensitivity grids on discount rate and growth; thesis: Value-Added Services compounding at a 16.3% CAGR."]),
              proj("DIS", bullets=P["DIS"]["bullets"] + ["Sourced every figure to filings, results presentations and earnings-call material, with balance-sheet and cash-flow checks built into the model."]),
              proj("HD"), proj("FUJ"), proj("OKAPI"), proj("VN")],
    skills=[("Research &amp; Valuation", "Equity valuation (DCF, comparables, Sum-of-the-Parts), 3-statement modeling, WACC and beta estimation, company and sector research, reading filings and earnings releases, written recommendations with a call and a target"),
            ("Markets &amp; ESG", "Economic indicators, fixed income and equities (Bloomberg Market Concepts), ESG data and disclosure analysis (Bloomberg ESG), impact-measurement case work"),
            ("Tools", "Microsoft Excel (advanced financial modeling), Bloomberg Terminal, Capital IQ, PowerPoint")],
    extra=["<b>Other coursework:</b> Bank of Singapore — EAM strategy case · Arrived — real-estate platform case · Impaakt — impact-measurement case, awarded an A.", CERTS, LANG, AVAIL],
)

V["Operations_Marketing"] = dict(
    tag="Business Operations · Client &amp; Market Analysis",
    summary="Master of Applied Finance candidate at SMU who spent two years inside a growing SME: reconciling the numbers, liaising with vendors and hitting statutory deadlines every single month. Combines that operator's grounding with analytical training (platform business cases, payments-network research, a private-bank client-service case) and a client-first communication style sharpened through committee presentations. Organized, deadline-proof and quick with Excel and PowerPoint; suited to operations, client-success, marketing-analytics and business-management roles in Singapore.",
    order=["experience", "projects"],
    ptitle="Selected Projects — Platforms, Clients &amp; Research",
    exp=["Acted as the point of contact with vendors and counterparties on invoice, payment and filing queries, resolving mismatches quickly and keeping relationships professional under deadline pressure.",
         "Owned the monthly statutory filing cadence (GST, TDS) end-to-end and prepared quarterly financial statements; two years without a missed deadline while multitasking across close, reviews and follow-ups.",
         "Ran variance and working-capital reviews in Excel, turning messy operational data into clear reports the owners could act on."],
    projects=[proj("BOS", title="Bank of Singapore — Client-Service &amp; Operations Strategy Case", bullets=["Analyzed how BOS serves external asset managers, mapping onboarding friction, service-model trade-offs (centralized vs decentralized) and client pain points, and recommended a repositioning built on the strengths clients actually value."]),
              proj("MA", title="Mastercard Inc. (NYSE: MA) — Payments-Network Research", right="Payments Sector · SMU · co-authored", bullets=["Co-authored an equity initiation (STRONG BUY, US$626 12-month target) on the world's second-largest payment network, studying how transaction volumes, merchant adoption and value-added services drive platform economics."]),
              proj("ARR", bullets=["Analyzed a high-growth marketplace platform: its onboarding funnel, unit economics, fee structure and user-experience trade-offs, as an investment and product case."]),
              proj("OKAPI", title="Okapi Solar — Subscription-Platform Valuation", bullets=["Valued a Malaysian rooftop-solar platform that onboards households onto a monthly subscription; modeled sign-up economics, payment collections and credit-loss assumptions over a 5-year horizon, with the proceed gated on diligence."]),
              proj("VN", bullets=["Authored a memorandum and presented it to a mock investment committee, winning conditional approval: building the case, fielding challenges live and defending the recommendation."]),
              proj("IMP", bullets=["Researched and scored a company's real-world impact from public sources into a concise, evidence-backed report; the same research-and-synthesis work as market and customer reporting."])],
    skills=[("Operations &amp; Coordination", "Vendor and counterparty liaison, onboarding and query resolution, deadline and calendar management, multitasking across parallel workstreams, meticulous documentation"),
            ("Communication", "Explaining numbers and processes in plain language, committee presentations, professional written correspondence with external partners"),
            ("Analysis &amp; Reporting", "Excel (advanced): usage reports, variance reviews, reconciliations, pivot tables and lookups; industry, platform and customer research; PowerPoint reporting packs"),
            ("Mindset", "Operator's ownership from SME experience, detail-oriented, fast learner, energized by startups, payments and platform businesses")],
    extra=["<b>Other work:</b> The Walt Disney Co. — 24-page equity initiation (co-authored) · Fujitec — PE case competition memo (APECS 2026) · Home Depot — DCF and comparables valuation.", CERTS, LANG, AVAIL],
)

V["Accounting_Tax_FPA"] = dict(
    tag="Accounting · Tax · FP&amp;A",
    summary="B.Com in Finance &amp; Accountancy and Master of Applied Finance candidate at SMU, with two years of hands-on financial-reporting and Indian indirect-tax compliance experience. Prepared statutory financial statements and owned GSTR-1 / GSTR-3B and TDS filing cadences for an SME; comfortable across month-end close, budgeting, variance analysis and full 3-statement / DCF modeling. Bloomberg Spreadsheet Analysis certified; detail-oriented and documentation-driven, targeting accounting, tax, FP&amp;A and finance-analyst roles in Singapore.",
    order=["experience", "projects"],
    ptitle="Selected Projects — Financial Modeling &amp; Analysis",
    exp=["Owned indirect-tax compliance end-to-end — <b>GSTR-1 / GSTR-3B filings and TDS</b> — managing the statutory filing cadence, reconciliations and audit-ready supporting documentation.",
         "Prepared quarterly P&amp;L, balance-sheet and cash-flow statements for an SME food-products business, supporting the month-end close and the annual budgeting cycle.",
         "Ran variance and working-capital reviews in Excel to flag cost overruns and tighten the reporting pack ahead of senior review; reconciled sales registers against invoices and vendor records every month."],
    projects=[proj("MA", bullets=["Built a full 3-statement model and FCFF DCF, deriving after-tax operating cash flows off an effective tax rate, to support a <b>STRONG BUY, US$626 12-month target</b>; cross-checked on EV/EBITDA and P/E. Modeled Value-Added Services at a 16.3% CAGR lifting the EBIT margin to 61.9%."]),
              proj("DIS", bullets=["Contributed to a 24-page initiation (<b>HOLD, US$107 target</b>) built on a segment-level 3-statement model with after-tax FCFF, a 9.27% WACC and 3.0% terminal growth across Experiences, DTC and Linear Networks."]),
              proj("VN", bullets=["Authored an investment memorandum presented to a mock investment committee (conditional approval); structured the capital stack and ran sensitivities on debt-service coverage and equity returns, weighing project-level tax treatment in the after-tax equity economics."]),
              proj("FUJ"),
              proj("OKAPI", title="Okapi Solar &amp; Home Depot — Valuation Projects", right="Specialty Finance / Equity Analysis · SMU · group", bullets=["Okapi: reframed a solar-leasing startup as a ~5% NIM specialty lender and reconciled DCF / VC / NSV methods to a ~US$15–16M EV, challenging a 0% credit-loss assumption. Home Depot: DCF intrinsic valuation cross-checked against EV/EBITDA and P/E comparables."])],
    skills=[("Accounting &amp; Reporting", "Financial-statement preparation (P&amp;L, balance sheet, cash flow), month-end close, budgeting and variance analysis, working-capital analysis, reconciliations"),
            ("Tax &amp; Compliance", "Indian indirect tax (GSTR-1 / GSTR-3B, TDS), statutory filing and reconciliation, tax documentation, compliance workflows"),
            ("Financial Analysis", "3-statement modeling, DCF / FCFF with after-tax cash flows, corporate finance, comparable-company analysis, sensitivity analysis"),
            ("Tools", "Microsoft Excel (advanced: modeling, pivot tables, lookups, data tables), Bloomberg Terminal, Capital IQ, PowerPoint, Word")],
    extra=["<b>Other coursework:</b> Bank of Singapore — wealth-management / EAM strategy case · Arrived — real-estate platform case · Impaakt — sustainable-finance impact case, awarded an A.", CERTS, LANG, AVAIL],
)

V["Risk_Markets"] = dict(
    tag="Risk · Markets · Model Validation",
    summary="Master of Applied Finance candidate at SMU (completing January 2027) with a B.Com in Finance &amp; Accountancy and two years of part-time reporting and reconciliation experience. Project work is built on challenging the numbers behind a decision: debt-service and equity-return sensitivities on a power-plant financing, a multi-variable stress of a levered receivables book, a US$1.0bn co-investment tested against its hurdle, and two equity initiations with explicit calls. Methodical, skeptical of an assumption until it is evidenced, and clear in written findings. Bloomberg Market Concepts, Spreadsheet Analysis and ESG certified; CFA Level I candidate (Feb 2027), targeting risk, markets and structured-products roles in Singapore.",
    order=["projects", "experience"],
    ptitle="Risk, Sensitivity &amp; Market Analysis — Coursework &amp; Competitions",
    exp=["Reconciled sales registers against invoices and vendor records every month ahead of GST returns and TDS filings; traced each mismatch to its source and kept audit-ready documentation for every filing, two years without a missed statutory deadline.",
         "Prepared quarterly P&amp;L, balance-sheet and cash-flow statements through the month-end close; ran variance and working-capital reviews in Excel to flag cost overruns ahead of senior review."],
    projects=[proj("VN", title="Vietnam Gas-Fired Power Plant — Financing Memorandum &amp; Coverage Sensitivities", bullets=["Authored an investment memorandum presented to a mock investment committee (conditional approval, with conditions attached to the risks the memo named); sized the debt and ran debt-service-coverage and equity-return sensitivities across financing and interest-rate scenarios to show where the structure held and where it broke."]),
              proj("OKAPI", title="Okapi Solar — Receivables Book: Credit, Funding &amp; Scenario Stress", bullets=["Restated a solar-leasing startup as a ~5% NIM specialty lender and challenged its <b>0% expected-credit-loss assumption</b> (a ~3.4% annual loss rate zeroes pre-tax profit); flagged MYR receivables against unhedged EUR/USD debt and single-facility refinancing risk; reconciled DCF / VC / NSV to a ~US$15–16M EV."]),
              proj("FUJ"),
              proj("MA", bullets=["Co-authored an initiation (<b>STRONG BUY, US$626 12-month target</b>) over a full 3-statement model: regression beta, 8.46% WACC, 3.2% terminal growth, sensitivity grids on discount rate and growth, EV/EBITDA and P/E cross-checks."]),
              proj("DIS", bullets=["Contributed to a 24-page initiation (<b>HOLD, US$107 target</b>): 5-year FCFF DCF at a 9.27% WACC cross-checked against a Sum-of-the-Parts bear/base/bull envelope (US$84 / 107 / 176); every figure sourced to filings, with balance-sheet and cash-flow checks built into the model."]),
              proj("BOS", title="Bank of Singapore — Balance-Sheet Strength as a Client Proposition", bullets=["Analyzed a private bank's External Intermediaries Desk (custody, onboarding, reporting, the split of KYC / AML responsibilities) and recommended an &ldquo;Asian Gateway&rdquo; custodian repositioning built on the OCBC ecosystem and Aa1 credit strength."])],
    skills=[("Risk &amp; Validation", "Scenario and sensitivity analysis (rates, coverage, credit loss, funding cost), stress of modeling assumptions, cash-flow and debt-sizing models, reconciliation and root-cause analysis, audit-ready documentation, written findings for senior review"),
            ("Finance &amp; Markets", "3-statement modeling, DCF (FCFF), WACC and beta estimation, comparables, financial-statement analysis, descriptive statistics and regression (coursework); economic indicators, fixed income, currencies and equities (Bloomberg Market Concepts)"),
            ("Tools", "Microsoft Excel (advanced: modeling, pivots, lookups, data tables), Bloomberg Terminal, Capital IQ, PowerPoint; Python basics")],
    extra=["<b>Other coursework:</b> Home Depot — DCF and comparables valuation · Arrived — real-estate platform case (fee and liquidity structure) · Impaakt — impact-measurement framework assessment, awarded an A.", CERTS, LANG, AVAIL],
)

# ---- Assemble & render -----------------------------------------------------------------------
def build(name, v):
    head = HEAD.replace("<title>Salini Sadangi — Finance</title>", f"<title>Salini Sadangi — {re.sub('<[^>]+>','',v['tag']).replace('&amp;','&')}</title>")
    head = head.replace('<div class="tag">Finance · Investment Analysis</div>', f'<div class="tag">{v["tag"]}</div>')
    body = h2("Summary", "Summary") + f'<p class="summary">{v["summary"]}</p>' + EDUCATION
    blocks = {
        "projects": h2("Projects", v["ptitle"]) + "".join(v["projects"]),
        "experience": experience(v.get("exp", EXP_DEFAULT)),
    }
    for k in v["order"]:
        body += blocks[k]
    body += skills(v["skills"]) + extras(*v["extra"]) + "</div></body></html>"
    return head + body

def pages(pdf):
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    return int(re.search(r"Pages:\s+(\d+)", out).group(1))

def render(html_path, pdf_path):
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf_path}", f"file://{html_path}"], capture_output=True)

COPY_DIR.mkdir(parents=True, exist_ok=True)
only = sys.argv[1:] or list(V)
for name in only:
    v = V[name]
    html = build(name, v)
    hp = OUT_DIR / f"Resume_Salini_Sadangi_Broad_{name}.html"
    pp = hp.with_suffix(".pdf")
    for fs in ["10.0", "9.8", "9.6", "9.4", "9.2", "9.0"]:
        h = html.replace("font-size:10.0px;line-height:1.32;", f"font-size:{fs}px;line-height:1.32;")
        hp.write_text(h, encoding="utf-8")
        render(hp, pp)
        n = pages(pp)
        if n == 1:
            break
    print(f"{name}: {n} page(s) at {fs}px")
    shutil.copy(hp, COPY_DIR / hp.name)
    shutil.copy(pp, COPY_DIR / pp.name)
