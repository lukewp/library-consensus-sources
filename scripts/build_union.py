#!/usr/bin/env python3
"""build_union: merge every collected library list into one union with consensus counts.

  python3 scripts/build_union.py            # reads data/raw/*.json, writes data/union.json and data/libraries.json

Titles are matched after normalization (case, accents, punctuation, '&', a leading 'The',
and vendor qualifiers in brackets such as '(ProQuest)' or '- EBSCO'). A domain is taken from
a library's own link when the link points off the library's host (unwrapping proxy URLs).
Standard library only; deterministic, so the union can be recomputed from data/raw.
"""
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
VENDORS = ["proquest", "ebsco", "ebscohost", "gale", "ovid", "elsevier", "sciencedirect", "springer", "wiley", "jstor", "lexisnexis",
           "lexis", "westlaw", "thomson reuters", "clarivate", "web of science", "scopus", "taylor francis", "sage", "oxford", "cambridge",
           "emerald", "ieee", "acm", "infobase", "credo", "statista", "bloomberg", "refinitiv", "lseg", "factiva", "dow jones", "nexis uni",
           "heinonline", "cqpress", "cq", "brill", "de gruyter", "project muse", "oclc", "firstsearch", "apa", "apa psycnet", "csa",
           "cabi", "nlm", "ncbi", "gale cengage", "readex", "adam matthew", "alexander street", "kanopy", "naxos", "pressreader",
           "newsbank", "eikon", "s p", "capital iq", "wrds", "mergent", "ibisworld", "passport", "euromonitor", "via proquest",
           "via ebsco", "via ovid", "via gale"]
PROXY_HOST = re.compile(r"(ezproxy|proxy|login\.|\.idm\.oclc\.org|openathens|shibboleth|wayf|libproxy|eres\.|lib-ezproxy)", re.I)
SECOND_LEVEL = {"ac.ae", "ac.bd", "ac.id", "ac.il", "ac.in", "ac.ir", "ac.jp", "ac.ke", "ac.kr", "ac.nz", "ac.th", "ac.uk", "ac.za", "art.br", "bel.tr", "biz.id", "co.ae", "co.id", "co.il", "co.in", "co.ir", "co.jp", "co.ke", "co.kr", "co.nz", "co.th", "co.uk", "co.za", "com.ar", "com.au", "com.bd", "com.br", "com.cn", "com.co", "com.eg", "com.es", "com.gh", "com.hk", "com.mx", "com.my", "com.ng", "com.pe", "com.ph", "com.pk", "com.pl", "com.qa", "com.sa", "com.sg", "com.tr", "com.tw", "com.ua", "com.vn", "edu.ar", "edu.au", "edu.cn", "edu.co", "edu.hk", "edu.mx", "edu.my", "edu.pe", "edu.pk", "edu.pl", "edu.sg", "edu.tr", "edu.tw", "edu.ua", "edu.vn", "europa.eu", "gen.tr", "go.id", "go.jp", "go.ke", "go.kr", "go.th", "gob.ar", "gob.es", "gob.mx", "gob.pe", "gov.ae", "gov.au", "gov.bd", "gov.br", "gov.cn", "gov.co", "gov.eg", "gov.gh", "gov.hk", "gov.il", "gov.in", "gov.ir", "gov.lk", "gov.my", "gov.ng", "gov.ph", "gov.pk", "gov.pl", "gov.qa", "gov.sa", "gov.sg", "gov.tr", "gov.tw", "gov.ua", "gov.uk", "gov.vn", "gov.za", "govt.nz", "in.ua", "jus.br", "leg.br", "mil.br", "my.id", "ne.jp", "ne.kr", "net.au", "net.br", "net.cn", "net.hk", "net.in", "net.mx", "net.nz", "net.ua", "net.vn", "nic.in", "or.id", "or.jp", "or.kr", "or.th", "org.ar", "org.au", "org.br", "org.cn", "org.co", "org.es", "org.hk", "org.il", "org.in", "org.ir", "org.mx", "org.nz", "org.pl", "org.sg", "org.tr", "org.tw", "org.ua", "org.uk", "org.vn", "org.za", "re.kr", "res.in", "sch.id", "tv.tr", "web.id"}


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


NEW_WINDOW = re.compile(r"\s*(this link )?opens in (a )?new (window|tab)\s*$", re.I)
INFRA_DOMAINS = {"exlibrisgroup.com", "libguides.com", "springshare.com", "openathens.net", "oclc.org", "eduroam.org",
                 "serialssolutions.com", "libanswers.com", "libcal.com", "libwizard.com", "libapps.com", "doi.org"}
PORTALS = {"nelliportaali.fi", "googleapis.com"}
FREE_FLAG = re.compile(r"\b(open access|freely available|free resource|free to (use|access)|free access|public access|\bfree\b)", re.I)
RESTRICTED_FLAG = re.compile(r"(users only|login required|required|members only|on-campus|campus only|restricted|subscription)", re.I)


def clean_title(title):
    return NEW_WINDOW.sub("", title).strip()


def norm_title(title):
    t = strip_accents(clean_title(title)).lower()
    t = t.replace("&", " and ").replace("+", " and ")
    vendor_hint = None
    m = re.search(r"\(([^)]*)\)\s*$", t)
    if m and any(v in m.group(1) for v in VENDORS):
        vendor_hint, t = m.group(1).strip(), t[:m.start()]
    m = re.search(r"\s[-–—:|]\s*(via\s+)?([a-z ]+)$", t)
    if m and m.group(2).strip() in VENDORS:
        vendor_hint, t = m.group(2).strip(), t[:m.start()]
    t = re.sub(r"^\s*the\s+", "", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = re.sub(r"\b(database|online|db)\s*$", "", t.strip())
    return re.sub(r"\s+", " ", t).strip(), vendor_hint


# One organization, many country domains: credit them to one entry.
MERGE_COUNTRY = re.compile(r"^(google|youtube|amazon|yahoo|bing)\.(com?\.)?[a-z]{2,3}$")


def registrable(host):
    host = (host or "").lower().split(":")[0].lstrip(".")
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in SECOND_LEVEL:
        reg = ".".join(parts[-3:])
    else:
        reg = ".".join(parts[-2:]) if len(parts) >= 2 else host
    m = MERGE_COUNTRY.match(reg)
    if m and reg != f"{m.group(1)}.com":
        return f"{m.group(1)}.com"
    return reg




def main():
    libraries, entries = [], defaultdict(lambda: {"titles": Counter(), "libraries": set(), "regions": set(), "countries": set(),
                                                   "domains": Counter(), "hosts": Counter(), "vendor_hints": Counter(),
                                                   "free_flags": 0, "restricted_flags": 0, "vendors": Counter(), "types": Counter(),
                                                   "descriptions": [], "other_titles": set(), "links": {}, "link_hosts": {}})
    for f in sorted(RAW.glob("*.json")):
        d = json.loads(f.read_text())
        lib = d["library"]
        rec = {**lib, "status": d.get("status"), "items": len(d.get("items", [])), "count_reported": d.get("count_reported"),
               "collected_at": d.get("collected_at"), "site_identity": d.get("site_identity"),
               "robots_ai_agents_named": sorted((d.get("robots") or {}).get("ai_agents_named", {}).keys()),
               "robots_crawl_delay": (d.get("robots") or {}).get("crawl_delay")}
        libraries.append(rec)
        if not str(d.get("status", "")).startswith(("collected", "partial")) or not d.get("items"):
            continue
        for it in d["items"]:
            key, vh = norm_title(it["title"])
            if not key:
                continue
            e = entries[key]
            e["titles"][clean_title(it["title"])] += 1
            e["libraries"].add(lib["host"])
            e["regions"].add(lib["region"])
            e["countries"].add(lib["country"])
            e["links"].setdefault(lib["host"], it["href"])
            if vh:
                e["vendor_hints"][vh] += 1
            h = it.get("link_host")
            if h:
                e["link_hosts"].setdefault(lib["host"], h)
            if h and h != lib["host"] and not PROXY_HOST.search(h):
                rd = registrable(h)
                if rd != registrable(lib["host"]) and rd not in INFRA_DOMAINS:
                    e["hosts"][h] += 1
                    e["domains"][rd] += 1
            text = " ".join(sorted(set(it.get("flags", []) + it.get("badges", []))))
            if FREE_FLAG.search(text):
                e["free_flags"] += 1
            elif RESTRICTED_FLAG.search(text):
                e["restricted_flags"] += 1
            for k, v in it.get("fields", {}).items():
                if k.lower().startswith("vendor"):
                    for x in re.split(r"[;,]", v):
                        if x.strip():
                            e["vendors"][x.strip()] += 1
                elif "type" in k.lower():
                    for x in re.split(r"[;,]", v):
                        if x.strip():
                            e["types"][x.strip()] += 1
            if it.get("description") and len(e["descriptions"]) < 3:
                e["descriptions"].append(it["description"][:400])
            for k, v in it.get("fields", {}).items():
                if ("vendor" in k.lower() or "type" in k.lower()):
                    continue
                if len(e["other_titles"]) < 8:
                    e["other_titles"].add(v[:120])
    collected = [l for l in libraries if str(l["status"]).startswith(("collected", "partial")) and l["items"]]
    # A library's own proxy or portal domain shows up under one or two libraries across very many titles.
    # Real platforms show up under many libraries. Drop the former as library-local.
    use = defaultdict(lambda: defaultdict(set))  # domain -> library -> entry keys
    for key, e in entries.items():
        for lib_host, h in e["link_hosts"].items():
            use[registrable(h)][lib_host].add(key)
    local = set()
    for dom, by_lib in use.items():
        total = sum(len(v) for v in by_lib.values())
        top = max(len(v) for v in by_lib.values())
        academic = bool(re.search(r"(\.edu$|\.edu\.|\.ac\.|^ac\.|uni[-.]|universit|\.nl$|\.fi$|\.se$|\.dk$|\.ca$)", dom))
        if total >= 40 and top / total >= 0.85 and (academic or dom in PORTALS):
            local.add(dom)
    for e in entries.values():
        for dom in list(e["domains"]):
            if dom in local:
                del e["domains"][dom]
        for h in list(e["hosts"]):
            if registrable(h) in local:
                del e["hosts"][h]
    (ROOT / "data" / "local_domains.json").write_text(json.dumps(sorted(local), indent=1))
    n = len(collected)
    out = []
    for key, e in entries.items():
        out.append({
            "key": key,
            "title": e["titles"].most_common(1)[0][0],
            "n_libraries": len(e["libraries"]),
            "share": round(len(e["libraries"]) / n, 4) if n else 0,
            "n_regions": len(e["regions"]),
            "regions": sorted(e["regions"]),
            "n_countries": len(e["countries"]),
            "domains": dict(e["domains"].most_common(5)),
            "hosts": dict(e["hosts"].most_common(5)),
            "vendor_hints": dict(e["vendor_hints"].most_common(3)),
            "free_flagged_by": e["free_flags"],
            "restricted_flagged_by": e["restricted_flags"],
            "vendors": dict(e["vendors"].most_common(3)),
            "types": dict(e["types"].most_common(4)),
            "title_variants": [t for t, _ in e["titles"].most_common(6)],
            "other_titles": sorted(e["other_titles"]),

            "libraries": sorted(e["libraries"]),
            "sample_links": e["links"],
        })
    out.sort(key=lambda r: (-r["n_libraries"], -r["n_regions"], r["key"]))
    # Library-written descriptions are the libraries' text: kept locally for tagging, not published.
    (ROOT / "data" / "descriptions.local.json").write_text(json.dumps(
        {k: v["descriptions"][0] for k, v in entries.items() if v["descriptions"]}, ensure_ascii=False))
    (ROOT / "data" / "libraries.json").write_text(json.dumps({"n_collected": n, "libraries": libraries}, indent=1, ensure_ascii=False))
    (ROOT / "data" / "union.json").write_text(json.dumps({"n_libraries": n, "n_entries": len(out), "entries": out}, indent=1, ensure_ascii=False))
    dist = Counter(min(r["n_libraries"], 10) for r in out)
    print(f"libraries collected: {n} of {len(libraries)}; union entries: {len(out)}")
    print("entries by library count (10 = 10+):", dict(sorted(dist.items())))


if __name__ == "__main__":
    main()
