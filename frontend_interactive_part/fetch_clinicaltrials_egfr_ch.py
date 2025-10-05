# fetch_ctgov_egfr_ch_fallback.py
# Usage: python fetch_ctgov_egfr_ch_fallback.py
import csv, time, requests

OUT = "clinicaltrials.csv"
HDRS = {"User-Agent":"SpacePath/1.0","Accept":"application/json"}

def v2():
    # v2 doesn’t accept 'filter.location.country' → fold country into query.term
    rows, token = [], None
    while True:
        params = {"query.term":"EGFR Switzerland", "pageSize":100}
        if token: params["pageToken"] = token
        r = requests.get("https://clinicaltrials.gov/api/v2/studies", params=params, headers=HDRS, timeout=30)
        if r.status_code != 200: return None
        js = r.json()
        for s in js.get("studies", []):
            ps = s.get("protocolSection", {}) or {}
            ident = ps.get("identificationModule", {}) or {}
            desc  = ps.get("descriptionModule", {}) or {}
            nct   = ident.get("nctId","")
            title = (ident.get("briefTitle") or "").strip()
            summ  = (desc.get("briefSummary") or "").strip()
            link  = f"https://clinicaltrials.gov/study/{nct}" if nct else ""
            if title and "switzerland" in (str(ps).lower()):
                rows.append({"Title":title, "Summary":summ, "Link":link})
        token = js.get("nextPageToken")
        if not token: break
    return rows

def v1_fields():
    # Standard, documented; country via AREA[...] in expr
    BASE = "https://clinicaltrials.gov/api/query/study_fields"
    COMMON = {"expr":"EGFR AND AREA[LocationCountry] Switzerland",
              "fields":"NCTId,OfficialTitle,BriefTitle,BriefSummary",
              "fmt":"json"}
    def get(p):
        for k in range(3):
            r = requests.get(BASE, params=p, headers=HDRS, timeout=30)
            if r.ok:
                try: return r.json()
                except: pass
            time.sleep(1.2*(k+1))
        return None
    js = get({**COMMON,"min_rnk":1,"max_rnk":1})
    if not js: return None
    total = int(js["StudyFieldsResponse"]["NStudiesFound"])
    rows, i = [], 1
    while i <= total:
        j = get({**COMMON,"min_rnk":i,"max_rnk":min(i+99,total)})
        if not j: return None
        for s in j["StudyFieldsResponse"]["StudyFields"]:
            nct = (s.get("NCTId") or [""])[0]
            title = ((s.get("OfficialTitle") or [""])[0] or (s.get("BriefTitle") or [""])[0]).strip()
            summ  = (s.get("BriefSummary") or [""])[0].strip()
            link  = f"https://clinicaltrials.gov/study/{nct}" if nct else ""
            if title: rows.append({"Title":title, "Summary":summ, "Link":link})
        i = i + 100
        time.sleep(0.25)
    return rows

def v1_full():
    # Broader payload; we parse needed fields
    BASE = "https://clinicaltrials.gov/api/query/full_studies"
    COMMON = {"expr":"EGFR AND AREA[LocationCountry] Switzerland","fmt":"json"}
    def get(p):
        for k in range(3):
            r = requests.get(BASE, params=p, headers=HDRS, timeout=30)
            if r.ok:
                try: return r.json()
                except: pass
            time.sleep(1.2*(k+1))
        return None
    j = get({**COMMON,"min_rnk":1,"max_rnk":1})
    if not j: return None
    nfound = int(j["FullStudiesResponse"]["NStudiesFound"])
    rows; rows=[]
    i=1
    while i<=nfound:
        js = get({**COMMON,"min_rnk":i,"max_rnk":min(i+19,nfound)})
        if not js: return None
        for fs in js["FullStudiesResponse"].get("FullStudies", []):
            s = fs.get("Study", {})
            ident = (s.get("ProtocolSection", {}) or {}).get("IdentificationModule", {}) or {}
            desc  = (s.get("ProtocolSection", {}) or {}).get("DescriptionModule", {}) or {}
            nct   = ident.get("NCTId","")
            title = (ident.get("BriefTitle") or "").strip()
            summ  = (desc.get("BriefSummary") or "").strip()
            link  = f"https://clinicaltrials.gov/study/{nct}" if nct else ""
            if title: rows.append({"Title":title, "Summary":summ, "Link":link})
        i = i+20
        time.sleep(0.35)
    return rows

if __name__ == "__main__":
    rows = v2() or v1_fields() or v1_full()
    if not rows:
        raise SystemExit("❌ Couldn’t reach CT.gov from this host. Try from your Mac or check firewall/DNS.")
    with open(OUT,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["Title","Summary","Link"])
        w.writeheader(); w.writerows(rows)
    print(f"✅ Saved {len(rows)} studies to {OUT}")
