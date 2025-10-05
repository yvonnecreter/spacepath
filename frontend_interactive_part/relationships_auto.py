# spacepath_from_llm.py
# pip install openai python-dotenv pandas

import os, json, pathlib, re, webbrowser
import pandas as pd
from collections import defaultdict, Counter

# ---------------- CONFIG ----------------
PROTEIN   = "EGFR"
QUERY     = "EGFR in microgravity"
NASA_CSV  = "nasa_papers.csv"          # columns: Title, Abstract(optional), Link
TRIALS_CSV= "clinicaltrials.csv"       # columns: Title, Summary(optional), Link
USE_GPT   = True                       # set False to use rule-based fallback
MODEL     = "gpt-4o-mini"                   # summarizer/extractor
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # set in env

# --------- helpers: load data ----------
def load_csv(path):
    if not pathlib.Path(path).exists(): return pd.DataFrame(columns=["Title","Abstract","Link"])
    df = pd.read_csv(path)
    for col in ["Title","Abstract","Link","Summary"]:
        if col not in df.columns: df[col] = ""
    return df.fillna("")

nasa_df   = load_csv(NASA_CSV)
trials_df = load_csv(TRIALS_CSV)

# --------- LLM extraction (JSON schema) ----------
def llm_extract_blocks(chunks):
    """
    Input: list of dicts [{"title":..., "text":..., "source":"NASA/CT", "url":...}, ...]
    Output schema:
    {
      "nodes":[{"id":"EGFR","type":"Protein"}, ...],
      "edges":[{"from":"EGFR","to":"MAPK pathway","label":"participates_in","weight":12,"refs":["<url>"]}, ...],
      "confidence":[{"term":"EGFR","nasa":90,"clinical":95}, ...]
    }
    """
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    sys = (
      "You are an expert biomedical curator. "
      "Extract a compact knowledge graph for the user query. "
      "Only return VALID JSON matching the schema. "
      "Node types allowed: Protein, Synonym, Pathway, Condition, Outcome, Drug, Trial, Evidence.\n"
      "Relations allowed: aliases, participates_in, affected_by, leads_to, targeted_by, studied_in, reported_in, described_in, linked_to.\n"
      "Set weight ~ number/strength of mentions (1-20). For confidence, give nasa/clinical (0-100) per main terms."
    )
    user = {
      "query": QUERY,
      "protein": PROTEIN,
      "chunks": chunks[:30]  # limit tokens for hackathon
    }

    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0.2,
        messages=[
            {"role":"system","content":sys},
            {"role":"user","content":f"Return ONLY JSON. {json.dumps(user)}"}
        ]
    )
    txt = resp.choices[0].message.content.strip()
    # strip code fences if any
    txt = re.sub(r"^```json|```$", "", txt).strip()
    return json.loads(txt)

# ---------- fallback: simple rules (titles only) ----------
def fallback_extract(nasa_df, trials_df):
    def has(t, *keys): 
        t=t.lower(); return any(k in t for k in keys)
    nodes = {
        "EGFR":("Protein",), "ERBB1":("Synonym",), "HER1":("Synonym",),
        "MAPK Pathway":("Pathway",), "PI3K-AKT Pathway":("Pathway",),
        "Microgravity":("Condition",), "Cell Proliferation":("Outcome",),
        "Osimertinib":("Drug",), "NSCLC Trials":("Trial",),
        "NASA Papers":("Evidence",), "ClinicalTrials.gov":("Evidence",)
    }
    edges = [
        ("EGFR","ERBB1","aliases",4,[]), ("EGFR","HER1","aliases",4,[]),
        ("EGFR","MAPK Pathway","participates_in",8,[]),
        ("EGFR","PI3K-AKT Pathway","participates_in",6,[]),
        ("EGFR","Microgravity","affected_by",5,[]),
        ("Microgravity","Cell Proliferation","leads_to",6,[]),
        ("EGFR","Osimertinib","targeted_by",10,[]),
        ("Osimertinib","NSCLC Trials","studied_in",6,[]),
        ("EGFR","NASA Papers","reported_in",len(nasa_df),[]),
        ("EGFR","ClinicalTrials.gov","linked_to",len(trials_df),[])
    ]
    conf = [
        {"term":"EGFR","nasa":80,"clinical":95},
        {"term":"MAPK Pathway","nasa":65,"clinical":60},
        {"term":"PI3K-AKT Pathway","nasa":60,"clinical":55},
        {"term":"Microgravity","nasa":95,"clinical":35},
        {"term":"Cell Proliferation","nasa":70,"clinical":60},
        {"term":"Osimertinib","nasa":25,"clinical":95},
        {"term":"NSCLC Trials","nasa":20,"clinical":98},
    ]
    return {
      "nodes":[{"id":k,"type":v[0]} for k,v in nodes.items()],
      "edges":[{"from":a,"to":b,"label":lab,"weight":w,"refs":refs} for a,b,lab,w,refs in edges],
      "confidence":conf
    }

# ---------- build chunks for LLM ----------
def build_chunks(nasa_df, trials_df, limit_nasa=20, limit_trials=10):
    nasa = []
    for _,r in nasa_df.head(limit_nasa).iterrows():
        nasa.append({"title":r["Title"], "text":(r.get("Abstract","") or r["Title"]), "source":"NASA", "url":r.get("Link","")})
    trials = []
    for _,r in trials_df.head(limit_trials).iterrows():
        trials.append({"title":r["Title"], "text":(r.get("Summary","") or r["Title"]), "source":"Clinical", "url":r.get("Link","")})
    return nasa + trials

chunks = build_chunks(nasa_df, trials_df)

if USE_GPT and OPENAI_API_KEY:
    try:
        kg = llm_extract_blocks(chunks)
    except Exception as e:
        print("LLM extraction failed, using fallback. Reason:", e)
        kg = fallback_extract(nasa_df, trials_df)
else:
    kg = fallback_extract(nasa_df, trials_df)

# ------------- render HTML (vis-network + Chart.js) --------------
def render_html(kg, outfile="spacepath_llm_demo.html"):
    nodes = kg["nodes"]; edges = kg["edges"]; conf = kg.get("confidence",[])
    # compute node values by sum of incident edge weights
    vals = defaultdict(int)
    for e in edges:
        vals[e["from"]]+=e.get("weight",1); vals[e["to"]]+=e.get("weight",1)
    for n in nodes:
        n["value"] = max(1, vals.get(n["id"],1))

    html = f"""<!doctype html>
<html><head>
<meta charset="utf-8"/>
<title>Space Path – {PROTEIN} graph</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/dist/vis-network.min.css"/>
<script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/dist/vis-network.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
 body {{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif}}
 .wrap{{display:flex;height:100vh}}
 #net{{flex:1 1 auto;border-right:1px solid #eee}}
 #side{{width:380px;padding:16px}}
 h3{{margin:8px 0 12px}}
 .pill{{display:inline-block;padding:2px 8px;margin:2px;border-radius:12px;font-size:12px;background:#f2f2f2}}
 .note{{font-size:12px;color:#666;margin-top:10px}}
</style></head>
<body>
<div class="wrap">
  <div id="net"></div>
  <div id="side">
    <h3>Confidence (NASA vs Clinical)</h3>
    <canvas id="bars" width="360" height="320"></canvas>
    <div style="margin-top:8px">
      <span class="pill" style="background:#e8fff7">Protein</span>
      <span class="pill" style="background:#f0fff0">Pathway</span>
      <span class="pill" style="background:#e3f2fd">Condition</span>
      <span class="pill" style="background:#e0f7fa">Outcome</span>
      <span class="pill" style="background:#fde2e4">Drug</span>
      <span class="pill" style="background:#ede7f6">Trial</span>
      <span class="pill" style="background:#eeeeee">Evidence</span>
    </div>
    <div class="note">Query: <b>{QUERY}</b><br/>Edge labels show relations; node size scales with evidence weight.</div>
  </div>
</div>
<script>
const nodes = {json.dumps(nodes)};
const edges = {json.dumps(edges)};
const conf  = {json.dumps(conf)};

const container = document.getElementById('net');
const data = {{
  nodes: new vis.DataSet(nodes.map(n=>({{
    id:n.id,label:n.id,group:n.type,value:n.value
  }}))),
  edges: new vis.DataSet(edges.map(e=>({{
    from:e.from,to:e.to,arrows:'to',label:e.label,width:1+0.2*(e.weight||1),font:{{align:'top'}},
    title:(e.refs && e.refs.length? 'Refs:\\n'+e.refs.join('\\n') : '')
  }})))
}};
const options = {{
  nodes: {{ shape:'dot', scaling:{{min:6,max:40}}, font:{{size:14}} }},
  groups: {{
    Protein:  {{ color:'#f4a261' }},
    Synonym:  {{ color:'#bdbdbd' }},
    Pathway:  {{ color:'#6fcf97' }},
    Condition:{{ color:'#56ccf2' }},
    Outcome:  {{ color:'#2dd4bf' }},
    Drug:     {{ color:'#f06292' }},
    Trial:    {{ color:'#9b59b6' }},
    Evidence: {{ color:'#90a4ae' }}
  }},
  edges: {{ color:{{color:'#808080'}}, smooth:true }},
  physics: {{ barnesHut:{{gravitationalConstant:-25000}}, stabilization:{{iterations:150}} }}
}};
new vis.Network(container, data, options);

// bars
const labels = (conf.length? conf.map(x=>x.term): ["EGFR"]);
const nasa   = (conf.length? conf.map(x=>x.nasa): [80]);
const clin   = (conf.length? conf.map(x=>x.clinical): [95]);
new Chart(document.getElementById('bars').getContext('2d'), {{
  type:'bar',
  data:{{ labels:labels, datasets:[
    {{ label:'NASA', data:nasa, backgroundColor:'#2a9d8f' }},
    {{ label:'Clinical', data:clin, backgroundColor:'#e76f51' }}
  ]}},
  options:{{
    responsive:true, plugins:{{legend:{{position:'bottom'}}}},
    scales:{{ x:{{stacked:true}}, y:{{stacked:true, beginAtZero:true, max:100, title:{{display:true,text:'Confidence (%)'}}}} }}
  }}
}});
</script>
</body></html>
"""
    out = pathlib.Path(outfile)
    out.write_text(html, encoding="utf-8")
    print(f"✅ Wrote {out.resolve()}")
    try:
        webbrowser.open(out.resolve().as_uri())
    except Exception:
        pass

render_html(kg)
# ----------------- end ------------------