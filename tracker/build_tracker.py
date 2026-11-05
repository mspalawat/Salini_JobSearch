#!/usr/bin/env python3
"""Builds Salini_Job_Tracker.xlsx and Salini_Job_Tracker.html from salini_jobs.csv.
Run after every CSV change: python3 build_tracker.py
All dashboard numbers are formulas (xlsx) or computed at render (html) - nothing hardcoded."""
import csv, json, datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.formatting.rule import FormulaRule
from openpyxl.utils import get_column_letter

HERE = Path(__file__).parent
CSV = HERE / "salini_jobs.csv"
XLSX = HERE / "Salini_Job_Tracker.xlsx"
HTML = HERE / "Salini_Job_Tracker.html"

# validated status palette (dataviz validator: all six checks pass on #FDF2F8)
STATUS = {  # status -> (chip fill, chip ink for xlsx; hex for html)
    "Prepared":  "B45309",
    "Applied":   "DB2777",
    "Interview": "7C3AED",
    "Offer":     "059669",
    "Rejected":  "9F1239",
}
STATUS_ORDER = list(STATUS)

PINK   = "DB2777"
BLUSH  = "FDF2F8"
BLUSH2 = "FCE7F3"
INK    = "46061F"
MUTED  = "9D6B80"

DATE_COLS = {"date_added", "deadline", "date_applied", "next_action_due", "interview_date"}
NUM_COLS = {"id", "fit_score"}

def load_rows():
    with CSV.open(encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        return list(rdr), rdr.fieldnames

def parse_date(s):
    try:
        return datetime.datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        return None

# ---------------------------------------------------------------- xlsx
def build_xlsx(rows, cols):
    wb = Workbook()
    data = wb.active
    data.title = "Data"
    thin = Side(style="thin", color=BLUSH2)
    border = Border(bottom=thin)

    for c, name in enumerate(cols, 1):
        cell = data.cell(row=1, column=c, value=name.replace("_", " ").title())
        cell.font = Font(name="Inter Tight", bold=True, color="FFFFFF", size=10)
        cell.fill = PatternFill("solid", fgColor=PINK)
        cell.alignment = Alignment(vertical="center")
    data.freeze_panes = "D2"

    for r, row in enumerate(rows, 2):
        for c, name in enumerate(cols, 1):
            v = row.get(name, "")
            if name in DATE_COLS and v:
                v = parse_date(v) or v
            elif name in NUM_COLS and v:
                try: v = float(v) if name == "fit_score" else int(v)
                except ValueError: pass
            cell = data.cell(row=r, column=c, value=v)
            cell.font = Font(name="Inter", size=10, color=INK)
            cell.border = border
            cell.alignment = Alignment(vertical="top", wrap_text=name in ("jd_summary", "jd_full", "notes", "next_action"))
            if name in DATE_COLS and isinstance(v, datetime.date):
                cell.number_format = "DD MMM YYYY"
            if r % 2 == 0:
                cell.fill = PatternFill("solid", fgColor=BLUSH)

    widths = dict(id=5, company=24, role=30, location=12, work_mode=10, source_url=22,
                  date_added=12, deadline=12, date_applied=12, status=11, priority=9,
                  fit_score=9, resume_variant=30, cover_letter_path=30, salary_range=18,
                  contact_person=22, next_action=32, next_action_due=13, interview_round=13,
                  interview_date=13, interviewer=16, interview_outcome=14, prep_doc=30,
                  jd_summary=40, jd_full=50, notes=40)
    for c, name in enumerate(cols, 1):
        data.column_dimensions[get_column_letter(c)].width = widths.get(name, 14)

    # status chip colours via conditional formatting (live: recolours if you edit by hand)
    j = get_column_letter(cols.index("status") + 1)
    rng = f"{j}2:{j}500"
    for st, hexc in STATUS.items():
        data.conditional_formatting.add(rng, FormulaRule(
            formula=[f'${j}2="{st}"'],
            fill=PatternFill("solid", fgColor=hexc),
            font=Font(name="Inter", size=10, bold=True, color="FFFFFF")))

    # ------- Dashboard: every number is a formula against Data -------
    dash = wb.create_sheet("Dashboard", 0)
    dash.sheet_view.showGridLines = False
    for col, w in zip("ABCDEFG", (2, 26, 14, 4, 26, 14, 2)):
        dash.column_dimensions[col].width = w

    dash["B2"] = "Salini · Job Application Tracker"
    dash["B2"].font = Font(name="Inter Tight", size=20, bold=True, color=INK)
    dash["B3"] = "All figures update live from the Data sheet"
    dash["B3"].font = Font(name="Inter", size=10, italic=True, color=MUTED)

    J, H, L, R, T = [get_column_letter(cols.index(n) + 1) for n in
                     ("status", "deadline", "fit_score", "next_action_due", "interview_date")]
    A = get_column_letter(cols.index("id") + 1)
    D = f"Data!${{c}}$2:${{c}}$500"
    def rngf(c): return D.format(c=c)

    tiles = [
        ("Total tracked",        f"=COUNTA({rngf(A)})", "0"),
        ("Prepared",             f'=COUNTIF({rngf(J)},"Prepared")', "0"),
        ("Applied",              f'=COUNTIF({rngf(J)},"Applied")', "0"),
        ("Interview",            f'=COUNTIF({rngf(J)},"Interview")', "0"),
        ("Offers",               f'=COUNTIF({rngf(J)},"Offer")', "0"),
        ("Rejected",             f'=COUNTIF({rngf(J)},"Rejected")', "0"),
        ("Sent (non-prepared)",  "=C5-C6", "0"),                       # cell-referenced
        ("Response rate",        '=IFERROR((C8+C9)/C11,"-")', "0.0%"), # interviews+offers / sent
        ("Average fit score",    f'=IFERROR(ROUND(AVERAGE({rngf(L)}),1),"-")', "0.0"),
        ("Next deadline",        f'=IFERROR(MINIFS({rngf(H)},{rngf(H)},">="&TODAY()),"-")', "DD MMM YYYY"),
        ("Days to next deadline","=IF(ISNUMBER(C14),C14-TODAY(),\"-\")", "0"),
        ("Actions due in 7 days",f'=COUNTIFS({rngf(R)},">="&TODAY(),{rngf(R)},"<="&TODAY()+7)', "0"),
        ("Upcoming interviews",  f'=COUNTIFS({rngf(T)},">="&TODAY())', "0"),
    ]
    for i, (label, formula, fmt) in enumerate(tiles):
        r = 5 + i
        lc, vc = dash.cell(row=r, column=2, value=label), dash.cell(row=r, column=3, value=formula)
        lc.font = Font(name="Inter", size=11, color=INK)
        vc.font = Font(name="Inter Tight", size=13, bold=True, color=PINK)
        vc.number_format = fmt
        vc.alignment = Alignment(horizontal="right")
        fill = PatternFill("solid", fgColor=BLUSH if i % 2 else BLUSH2)
        lc.fill = fill; vc.fill = fill

    wb.save(XLSX)

# ---------------------------------------------------------------- html
def build_html(rows):
    payload = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    built = datetime.date.today().strftime("%d %b %Y")
    status_js = json.dumps({k: "#" + v for k, v in STATUS.items()})
    order_js = json.dumps(STATUS_ORDER)
    html = HTML_TEMPLATE.replace("__DATA__", payload).replace("__BUILT__", built) \
                        .replace("__STATUS__", status_js).replace("__ORDER__", order_js)
    HTML.write_text(html, encoding="utf-8")

HTML_TEMPLATE = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Salini · Job Application Tracker</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Inter+Tight:wght@600;700&display=swap');
:root{--bg:#FDF2F8;--card:#FFFFFF;--ink:#46061F;--muted:#9D6B80;--rule:#F5D0E1;--accent:#DB2777;--accent-soft:#FCE7F3;}
*{box-sizing:border-box;margin:0;}
body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--ink);font-size:14px;line-height:1.5;padding:32px 24px 64px;}
.wrap{max-width:1100px;margin:0 auto;}
h1{font-family:'Inter Tight',sans-serif;font-size:clamp(24px,3vw,32px);font-weight:700;letter-spacing:-.02em;}
.sub{color:var(--muted);font-size:13px;margin:4px 0 24px;}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:24px;}
.tile{background:var(--card);border-radius:16px;padding:16px;box-shadow:0 1px 2px rgba(70,6,31,.06);}
.tile .k{font-size:12px;color:var(--muted);font-weight:500;}
.tile .v{font-family:'Inter Tight',sans-serif;font-size:28px;font-weight:700;font-variant-numeric:tabular-nums;margin-top:2px;}
.tile .v small{font-size:14px;color:var(--muted);font-weight:600;}
.card{background:var(--card);border-radius:16px;padding:20px;box-shadow:0 1px 2px rgba(70,6,31,.06);margin-bottom:24px;}
.card h2{font-family:'Inter Tight',sans-serif;font-size:15px;font-weight:600;margin-bottom:12px;}
.bar{display:flex;height:28px;border-radius:8px;overflow:hidden;background:var(--accent-soft);gap:2px;}
.bar div{transition:opacity .15s ease-out;}
.bar div:hover{opacity:.82;}
.legend{display:flex;flex-wrap:wrap;gap:14px;margin-top:10px;font-size:12px;color:var(--ink);}
.legend span{display:inline-flex;align-items:center;gap:6px;font-variant-numeric:tabular-nums;}
.legend i{width:10px;height:10px;border-radius:3px;display:inline-block;}
.actions li{list-style:none;display:flex;justify-content:space-between;gap:12px;padding:8px 0;border-bottom:1px solid var(--rule);font-size:13px;}
.actions li:last-child{border-bottom:0;}
.due{color:var(--muted);font-variant-numeric:tabular-nums;white-space:nowrap;}
.due.over{color:#9F1239;font-weight:600;}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px;}
.chips button{font:inherit;font-size:12px;font-weight:500;padding:6px 12px;border-radius:9999px;border:1px solid var(--rule);background:var(--card);color:var(--ink);cursor:pointer;}
.chips button:hover{border-color:var(--accent);}
.chips button:focus-visible{outline:2px solid var(--accent);outline-offset:2px;}
.chips button[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:#fff;}
table{width:100%;border-collapse:collapse;font-size:13px;}
th{font-family:'Inter Tight',sans-serif;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);text-align:left;padding:8px 10px;border-bottom:2px solid var(--rule);cursor:pointer;user-select:none;white-space:nowrap;}
th:hover{color:var(--accent);}
td{padding:10px;border-bottom:1px solid var(--rule);vertical-align:top;font-variant-numeric:tabular-nums;}
tr:hover td{background:var(--bg);}
.co{font-weight:600;}
.role{color:var(--muted);font-size:12px;}
.pill{display:inline-block;padding:2px 10px;border-radius:9999px;color:#fff;font-size:11px;font-weight:600;}
details{margin-top:6px;}
summary{cursor:pointer;font-size:12px;color:var(--accent);font-weight:500;}
summary:focus-visible{outline:2px solid var(--accent);outline-offset:2px;}
.jd{font-size:12px;color:var(--ink);background:var(--bg);border-radius:8px;padding:10px 12px;margin-top:6px;white-space:pre-wrap;}
.meta{font-size:12px;color:var(--muted);margin-top:4px;}
@media (max-width:720px){.hide-sm{display:none;}}
@media print{body{background:#fff;padding:0;} .card,.tile{box-shadow:none;border:1px solid var(--rule);}}
</style></head><body><div class="wrap">
<h1>Salini · Job Application Tracker</h1>
<p class="sub">Rebuilt __BUILT__ from salini_jobs.csv — every figure below is computed from the table, nothing is hardcoded.</p>
<div class="tiles" id="tiles"></div>
<div class="card"><h2>Pipeline by status</h2><div class="bar" id="bar" role="img" aria-label="Applications by status"></div><div class="legend" id="legend"></div></div>
<div class="card"><h2>Next actions</h2><ul class="actions" id="actions"></ul></div>
<div class="card"><h2>Applications</h2><div class="chips" id="chips"></div>
<table aria-label="Applications table"><thead><tr>
<th data-k="company">Company / Role</th><th data-k="status">Status</th><th data-k="priority" class="hide-sm">Priority</th>
<th data-k="fit_score">Fit</th><th data-k="deadline">Deadline</th><th data-k="date_applied" class="hide-sm">Applied</th>
<th data-k="resume_variant" class="hide-sm">Resume</th></tr></thead><tbody id="tbody"></tbody></table></div>
</div>
<script>
const DATA=__DATA__, C=__STATUS__, ORDER=__ORDER__;
const today=new Date(); today.setHours(0,0,0,0);
const d=s=>s?new Date(s+"T00:00:00"):null;
const fmt=s=>{const x=d(s);return x?x.toLocaleDateString("en-SG",{day:"2-digit",month:"short"}):"—";};
const by=k=>DATA.filter(r=>r.status===k).length;
const sent=DATA.length-by("Prepared");
const resp=sent? (by("Interview")+by("Offer"))/sent : null;
const fits=DATA.map(r=>parseFloat(r.fit_score)).filter(n=>!isNaN(n));
const nextDl=DATA.map(r=>d(r.deadline)).filter(x=>x&&x>=today).sort((a,b)=>a-b)[0];
const tiles=[["Total tracked",DATA.length],["Sent",sent],["Interviews",by("Interview")],["Offers",by("Offer")],
 ["Response rate",resp==null?"—":Math.round(resp*100)+"<small>%</small>"],
 ["Avg fit score",fits.length?(fits.reduce((a,b)=>a+b,0)/fits.length).toFixed(1):"—"],
 ["Next deadline",nextDl?nextDl.toLocaleDateString("en-SG",{day:"2-digit",month:"short"})+` <small>${Math.round((nextDl-today)/864e5)}d</small>`:"—"]];
document.getElementById("tiles").innerHTML=tiles.map(([k,v])=>`<div class="tile"><div class="k">${k}</div><div class="v">${v}</div></div>`).join("");
const bar=document.getElementById("bar"), leg=document.getElementById("legend");
ORDER.forEach(st=>{const n=by(st); if(n){const el=document.createElement("div");
 el.style.cssText=`background:${C[st]};flex:${n} 1 0`; el.title=`${st}: ${n}`; bar.appendChild(el);}
 leg.insertAdjacentHTML("beforeend",`<span><i style="background:${C[st]}"></i>${st} · ${by(st)}</span>`);});
const acts=DATA.filter(r=>r.next_action).map(r=>({t:`${r.company} — ${r.next_action}`,due:r.next_action_due}))
 .sort((a,b)=>(a.due||"9999").localeCompare(b.due||"9999"));
document.getElementById("actions").innerHTML=acts.length?acts.map(a=>{const over=a.due&&d(a.due)<today;
 return `<li><span>${a.t}</span><span class="due ${over?"over":""}">${a.due?fmt(a.due)+(over?" · overdue":""):""}</span></li>`;}).join("")
 :"<li>Nothing pending 🎉</li>";
const chipsEl=document.getElementById("chips"); let filter="All", sortK="id", asc=true;
["All",...ORDER].forEach(s=>{const b=document.createElement("button"); b.textContent=s==="All"?`All · ${DATA.length}`:`${s} · ${by(s)}`;
 b.setAttribute("aria-pressed",s===filter); b.onclick=()=>{filter=s;[...chipsEl.children].forEach(x=>x.setAttribute("aria-pressed",x===b));render();};
 chipsEl.appendChild(b);});
document.querySelectorAll("th").forEach(th=>th.onclick=()=>{const k=th.dataset.k; asc=(sortK===k)?!asc:true; sortK=k; render();});
function render(){
 const rows=DATA.filter(r=>filter==="All"||r.status===filter)
  .sort((a,b)=>{let x=a[sortK]??"",y=b[sortK]??""; const nx=parseFloat(x),ny=parseFloat(y);
   if(!isNaN(nx)&&!isNaN(ny)){x=nx;y=ny;} const c=x<y?-1:x>y?1:0; return asc?c:-c;});
 document.getElementById("tbody").innerHTML=rows.map(r=>`<tr>
  <td><div class="co">${r.company}</div><div class="role">${r.role}</div>
   <details><summary>Details & JD</summary>
    ${r.jd_summary?`<div class="jd"><b>Summary:</b> ${r.jd_summary}</div>`:""}
    ${r.jd_full?`<div class="jd">${r.jd_full}</div>`:""}
    ${r.notes?`<div class="meta"><b>Notes:</b> ${r.notes}</div>`:""}
    ${r.resume_variant?`<div class="meta"><b>Resume:</b> ${r.resume_variant}</div>`:""}
    ${r.cover_letter_path?`<div class="meta"><b>Cover letter:</b> ${r.cover_letter_path}</div>`:""}
    ${r.prep_doc?`<div class="meta"><b>Prep:</b> ${r.prep_doc}</div>`:""}
    ${r.source_url?`<div class="meta"><a href="${r.source_url}">Job posting ↗</a></div>`:""}
   </details></td>
  <td><span class="pill" style="background:${C[r.status]||"#9D6B80"}">${r.status}</span></td>
  <td class="hide-sm">${r.priority||"—"}</td>
  <td>${r.fit_score||"—"}</td>
  <td>${fmt(r.deadline)}</td>
  <td class="hide-sm">${fmt(r.date_applied)}</td>
  <td class="hide-sm" style="font-size:12px;color:var(--muted)">${(r.resume_variant||"—").replace("Resume_Salini_Sadangi","…")}</td>
 </tr>`).join("");}
render();
</script></body></html>
"""

if __name__ == "__main__":
    rows, cols = load_rows()
    build_xlsx(rows, cols)
    build_html(rows)
    print(f"Built {XLSX.name} and {HTML.name} from {len(rows)} rows")
