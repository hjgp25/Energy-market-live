#!/usr/bin/env python3
"""
Energy Market Live updater.

Primary weekly breakdown:
  https://petroplanet.com/rig-count
  (presentation of Baker Hughes rig-count data)

Canada / official summary fallback:
  https://rigcount.bakerhughes.com/

The updater preserves the last good data if a source is unavailable or stale.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

OUT = Path("rigcount.json")
PETRO = "https://petroplanet.com/rig-count"
BAKER = "https://rigcount.bakerhughes.com/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; EnergyMarketLive/1.0)",
    "Accept-Language": "en-US,en;q=0.9",
}

STATE_CODES = {
    "Alabama":"AL","Alaska":"AK","Arizona":"AZ","Arkansas":"AR","California":"CA","Colorado":"CO",
    "Connecticut":"CT","Delaware":"DE","Florida":"FL","Georgia":"GA","Hawaii":"HI","Idaho":"ID",
    "Illinois":"IL","Indiana":"IN","Iowa":"IA","Kansas":"KS","Kentucky":"KY","Louisiana":"LA",
    "Maine":"ME","Maryland":"MD","Massachusetts":"MA","Michigan":"MI","Minnesota":"MN","Mississippi":"MS",
    "Missouri":"MO","Montana":"MT","Nebraska":"NE","Nevada":"NV","New Hampshire":"NH","New Jersey":"NJ",
    "New Mexico":"NM","New York":"NY","North Carolina":"NC","North Dakota":"ND","Ohio":"OH","Oklahoma":"OK",
    "Oregon":"OR","Pennsylvania":"PA","Rhode Island":"RI","South Carolina":"SC","South Dakota":"SD",
    "Tennessee":"TN","Texas":"TX","Utah":"UT","Vermont":"VT","Virginia":"VA","Washington":"WA",
    "West Virginia":"WV","Wisconsin":"WI","Wyoming":"WY"
}

def clean(s):
    return re.sub(r"\s+"," ",s or "").strip()

def number(s):
    s = clean(s).replace(",","")
    if s.lower() in {"unch","unchanged","—","-",""}:
        return 0
    m = re.search(r"[+-]?\d+",s)
    return int(m.group()) if m else None

def dt(s):
    try:
        return dateparser.parse(clean(s), fuzzy=True)
    except Exception:
        return datetime(1900,1,1)

def read_existing():
    if not OUT.exists():
        return {}
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return {}

def table_after_heading(soup, heading_text):
    target = None
    for h in soup.find_all(["h2","h3"]):
        if heading_text.lower() in clean(h.get_text(" ",strip=True)).lower():
            target = h
            break
    if not target:
        return None
    return target.find_next("table")

def parse_rows(table):
    if not table:
        return []
    rows=[]
    for tr in table.find_all("tr"):
        cells=[clean(x.get_text(" ",strip=True)) for x in tr.find_all(["th","td"])]
        if cells:
            rows.append(cells)
    return rows

def scrape_petro(existing):
    r=requests.get(PETRO,headers=HEADERS,timeout=30)
    r.raise_for_status()
    soup=BeautifulSoup(r.text,"html.parser")
    text=clean(soup.get_text(" ",strip=True))
    m=re.search(r"week ending ([A-Za-z]+ \d{1,2}, \d{4})",text,re.I)
    if not m:
        raise RuntimeError("Could not find PetroPlanet report date")
    report_date=m.group(1)

    states=[]
    for row in parse_rows(table_after_heading(soup,"By state"))[1:]:
        if len(row)<3: continue
        name=row[0]
        if name not in STATE_CODES: continue
        states.append({
            "code":STATE_CODES[name],
            "name":name,
            "count":number(row[1]) or 0,
            "change":number(row[2])
        })

    basins=[]
    for row in parse_rows(table_after_heading(soup,"By basin"))[1:]:
        if len(row)<3: continue
        basins.append({"name":row[0],"count":number(row[1]) or 0,"change":number(row[2])})

    drill={}
    for row in parse_rows(table_after_heading(soup,"Oil vs gas"))[1:]:
        if len(row)<3: continue
        key=row[0].lower().replace(" ","_")
        drill[key]={"count":number(row[1]) or 0,"change":number(row[2])}

    traj={}
    for row in parse_rows(table_after_heading(soup,"By trajectory"))[1:]:
        if len(row)<3: continue
        traj[row[0].lower()]={"count":number(row[1]) or 0,"change":number(row[2])}

    loc={}
    for row in parse_rows(table_after_heading(soup,"By location"))[1:]:
        if len(row)<3: continue
        key=row[0].lower().replace(" ","_")
        loc[key]={"count":number(row[1]) or 0,"change":number(row[2])}

    us_match=re.search(r"(\d+)\s*US rigs\s*[·•]\s*([^·•]+)",text,re.I)
    if us_match:
        us_count=int(us_match.group(1))
        us_change=number(us_match.group(2))
    else:
        us_count=existing.get("us",{}).get("count")
        us_change=existing.get("us",{}).get("change")

    return {
        "report_date":report_date,
        "state_report_date":report_date,
        "basin_report_date":report_date,
        "us":{"count":us_count,"change":us_change},
        "states":states,
        "basins":basins,
        "drill_for":drill,
        "trajectory":traj,
        "location":loc,
    }

def scrape_baker_summary():
    r=requests.get(BAKER,headers=HEADERS,timeout=30)
    r.raise_for_status()
    soup=BeautifulSoup(r.text,"html.parser")
    result={}
    for table in soup.find_all("table"):
        rows=parse_rows(table)
        for row in rows:
            if len(row)<4: continue
            label=row[0].strip().lower()
            item={"last_count":row[1],"count":number(row[2]),"change":number(row[3])}
            if label in {"u.s.","us","u.s"} or label.startswith("u.s."):
                result["us"]=item
            elif label.startswith("canada"):
                result["canada"]=item
            elif label.startswith("international"):
                result["international"]=item
    return result

def main():
    existing=read_existing()
    merged=dict(existing)

    try:
        p=scrape_petro(existing)
        old_state=existing.get("state_report_date","January 1, 1900")
        if dt(p["state_report_date"]) >= dt(old_state):
            for k in ("states","state_report_date","basins","basin_report_date","drill_for","trajectory","location"):
                if p.get(k):
                    merged[k]=p[k]
        old_report=existing.get("report_date","January 1, 1900")
        if dt(p["report_date"]) >= dt(old_report):
            merged["report_date"]=p["report_date"]
            if p.get("us",{}).get("count") is not None:
                merged["us"]=p["us"]
    except Exception as e:
        print("PetroPlanet warning:",e)

    try:
        b=scrape_baker_summary()
        if b.get("canada",{}).get("count") is not None:
            merged["canada"]={
                "count":b["canada"]["count"],
                "change":b["canada"]["change"],
                "last_count":b["canada"]["last_count"]
            }
        if b.get("international",{}).get("count") is not None:
            merged["international"]={
                "count":b["international"]["count"],
                "change":b["international"]["change"],
                "last_count":b["international"]["last_count"]
            }
    except Exception as e:
        print("Baker Hughes warning:",e)

    merged["source"]="Baker Hughes Rig Count"
    merged["fetched_at"]=datetime.now(timezone.utc).isoformat(timespec="seconds")
    OUT.write_text(json.dumps(merged,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(merged,indent=2))

if __name__=="__main__":
    main()
