#!/usr/bin/env python3
"""subject_guides: which open-web sources do libraries' news, free-web, data and government guides point to?

  python3 scripts/subject_guides.py collect     # -> data/guides/raw/<host>.json
  python3 scripts/subject_guides.py summarize   # -> data/guides/domains.json

For each collected library: read its LibGuides sitemap.xml, keep guides whose address names one of the
guide kinds below (at most MAX_GUIDES), fetch each guide's first page, and record the external links in it.
Same politeness as the A-Z collector: robots.txt first, honest user agent, the host's crawl delay (>= 10 s).
"""
import json
import re
import sys
import time
import urllib.parse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_libguides import get, parse_robots, group_for, allowed, OUR_TOKENS, MIN_DELAY  # noqa: E402
from build_union import registrable, SECOND_LEVEL, PROXY_HOST, INFRA_DOMAINS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "guides"
MAX_GUIDES = 8
KINDS = [
    ("news", r"news|newspaper|current[-_]?events|journalism|fact[-_]?check|misinformation|media[-_]?literacy"),
    ("free_web", r"free[-_]?(resources|web|online|sources|databases)|freeresources|open[-_]?(resources|web|sources)|internet[-_]?resources|web[-_]?resources|websites|public[-_]?resources"),
    ("data", r"statistics|stats\b|datasets|data[-_]?sources|find[-_]?data|finding[-_]?data|data[-_]?resources|socialdata|econdata"),
    ("government", r"government|govdocs|gov[-_]?info|govinfo|official[-_]?publications|government[-_]?information|policy[-_]?sources"),
]
# Page furniture rather than recommendations: licence badges, office and cloud hosts.
CHROME = {"creativecommons.org", "sharepoint.com", "outlook.com", "office.com", "microsoft.com", "amazonaws.com", "cloudfront.net",
          "googleapis.com", "gstatic.com", "bit.ly", "forms.gle", "qualtrics.com", "zoom.us", "calendly.com", "libchat.com"}
SHARE = re.compile(r"(sharer|share\?|intent/tweet|addtoany|mailto:|javascript:)", re.I)


def kind_of(url):
    path = urllib.parse.urlsplit(url).path.lower()
    for k, rx in KINDS:
        if re.search(rx, path):
            return k
    return None


def collect_one(libfile):
    d = json.loads(libfile.read_text())
    lib, host = d["library"], d["library"]["host"]
    target = OUT / "raw" / f"{host}.json"
    if target.exists():
        return host, "skip"
    robots = (ROOT / "data" / "raw" / f"{host}.robots.txt")
    ours = group_for(parse_robots(robots.read_text()), OUR_TOKENS) if robots.exists() else {"rules": [], "delay": None}
    last = {"t": 0.0, "delay": max(MIN_DELAY, ours.get("delay") or 0)}
    out = {"library": lib, "guides": [], "status": None}
    if not allowed(ours, "/sitemap.xml"):
        out["status"] = "robots disallows the sitemap"
    else:
        st, _, sm = get(f"https://{host}/sitemap.xml", last)
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sm) if st == 200 else []
        picks = [(u, kind_of(u)) for u in locs if kind_of(u)]
        seen_kinds = Counter()
        chosen = []
        for u, k in picks:  # spread across kinds, at most MAX_GUIDES
            if seen_kinds[k] < 3 and len(chosen) < MAX_GUIDES:
                chosen.append((u, k))
                seen_kinds[k] += 1
        for u, k in chosen:
            path = urllib.parse.urlsplit(u).path or "/"
            if not allowed(ours, path):
                continue
            st, final, page = get(u, last)
            if st != 200:
                continue
            start = page.find('id="s-lg-guide-main"')
            body = page[start:] if start >= 0 else page
            for marker in ('id="s-lib-footer', 'id="s-lg-public-footer', '<footer', 'id="s-lg-guide-footer'):
                cut = body.find(marker)
                if cut > 0:
                    body = body[:cut]
            links = []
            for h in re.findall(r'(?is)<a[^>]+href="(https?://[^"]+)"', body):
                if SHARE.search(h):
                    continue
                hh = urllib.parse.urlsplit(h).netloc.lower()
                if not hh or hh == host or PROXY_HOST.search(hh):
                    continue
                rd = registrable(hh)
                if rd in INFRA_DOMAINS or rd in CHROME or rd == registrable(host):
                    continue
                links.append(rd)
            out["guides"].append({"url": final, "kind": k, "domains": sorted(set(links))})
        out["status"] = f"{len(out['guides'])} guides" if st is not None else "sitemap unreadable"
    target.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return host, out["status"]


def collect():
    (OUT / "raw").mkdir(parents=True, exist_ok=True)
    libs = [f for f in sorted((ROOT / "data" / "raw").glob("*.json"))
            if json.loads(f.read_text()).get("items")]
    with ThreadPoolExecutor(max_workers=24) as ex:
        for host, st in ex.map(collect_one, libs):
            print(host, st, flush=True)


def summarize():
    local = set(json.loads((ROOT / "data" / "local_domains.json").read_text()))
    by = defaultdict(lambda: {"libraries": set(), "regions": set(), "kinds": Counter()})
    n_libs, kinds_libs = 0, Counter()
    for f in sorted((OUT / "raw").glob("*.json")):
        r = json.loads(f.read_text())
        if not r["guides"]:
            continue
        n_libs += 1
        host, region = r["library"]["host"], r["library"]["region"]
        for k in {g["kind"] for g in r["guides"]}:
            kinds_libs[k] += 1
        for g in r["guides"]:
            for d in g["domains"]:
                if d in local or d in SECOND_LEVEL:
                    continue
                x = by[d]
                x["libraries"].add(host)
                x["regions"].add(region)
                x["kinds"][g["kind"]] += 1
    rows = sorted(({"domain": d, "n_libraries": len(x["libraries"]), "n_regions": len(x["regions"]), "kinds": dict(x["kinds"])}
                   for d, x in by.items()), key=lambda r: (-r["n_libraries"], -r["n_regions"]))
    (OUT / "domains.json").write_text(json.dumps({"n_libraries_with_guides": n_libs, "libraries_by_kind": dict(kinds_libs),
                                                 "domains": rows}, indent=1, ensure_ascii=False))
    print(n_libs, "libraries with matching guides;", len(rows), "domains;", dict(kinds_libs))


if __name__ == "__main__":
    {"collect": collect, "summarize": summarize}[sys.argv[1]]()
