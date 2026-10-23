#!/usr/bin/env python3
"""fetch_terms: gather the access and terms evidence for every platform domain in the union.

  python3 scripts/fetch_terms.py [--shard K/N]

Per registrable domain it records, in data/terms/raw/<domain>.json:
  - robots.txt: HTTP status, AI agents named (and whether fully disallowed), whether "*" or our
    agent may fetch "/", the crawl delay;
  - TDM Reservation Protocol: /.well-known/tdmrep.json and a tdm-reservation meta tag;
  - the home page: status, final URL, title, whether a bot check answered, paywall and sign-in cues;
  - the terms page(s) linked from the home page: URL, and sentences that mention automated access,
    scraping, crawling, robots, bulk or systematic downloading, text and data mining, or AI.
It never fetches a path robots.txt disallows for us, identifies itself honestly, and does not
retry past a bot check. Evidence only: data/terms/classify notes turn it into readings.
"""
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_libguides import USER_AGENT, parse_robots, group_for, allowed, ai_named, OUR_TOKENS, text_of  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUTDIR = ROOT / "data" / "terms" / "raw"
DELAY = 3.0
TERMS_LINK = re.compile(r"(terms|conditions|legal|tos\b|terms-of|user[- ]agreement|acceptable[- ]use|nutzungsbedingungen|agb|"
                        r"conditions[- ]g[ée]n[ée]rales|mentions[- ]l[ée]gales|aviso[- ]legal|t[ée]rminos|condiciones|"
                        r"gebruiksvoorwaarden|voorwaarden|condizioni|termini|license[- ]agreement|copyright)", re.I)
CLAUSE = re.compile(r"(automat|scrap|crawl|spider|robot|\bbots?\b|harvest|bulk download|systematic(ally)? download|"
                    r"text[- ]and[- ]data[- ]mining|data mining|\btdm\b|artificial intelligence|\bai\b|machine learning|"
                    r"large language|\bllms?\b|train(ing)? (a |any )?(model|ai)|generative|reserv\w* (the|its|all) rights? .{0,40}mining)", re.I)
PAYWALL = re.compile(r"(subscribe|subscription|institutional (access|login)|sign in|log in|login|purchase|buy now|pricing|"
                     r"free trial|members only|access through your institution|athens|shibboleth)", re.I)
COMMON_PATHS = ["/terms", "/terms-of-use", "/terms-and-conditions", "/terms-of-service", "/legal", "/legal/terms", "/about/terms", "/tos"]
BOTCHECK = re.compile(r"(just a moment|checking your browser|cf-chl|captcha|are you a robot|access denied|attention required|"
                      r"enable javascript and cookies|request unsuccessful|incapsula|perimeterx|datadome)", re.I)


def fetch(url, max_bytes=1_500_000):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json;q=0.9,*/*;q=0.5"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.geturl(), r.read(max_bytes).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        try:
            body = e.read(200_000).decode("utf-8", "replace")
        except Exception:
            body = ""
        return e.code, url, body
    except Exception as e:
        return None, url, f"{type(e).__name__}: {e}"


def sentences(text, rx, limit=14):
    out = []
    for s in re.split(r"(?<=[.;!?])\s+", text):
        if rx.search(s) and 25 < len(s) < 900:
            out.append(s.strip())
            if len(out) >= limit:
                break
    return out


def one(domain):
    rec = {"domain": domain, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "user_agent": USER_AGENT}
    base = None
    for cand in (f"https://www.{domain}", f"https://{domain}"):
        st, final, body = fetch(cand + "/robots.txt", 300_000)
        if st is not None:
            base = cand
            break
    if base is None:
        rec["status"] = "unreachable"
        return rec
    groups = parse_robots(body) if st == 200 else []
    ours = group_for(groups, OUR_TOKENS)
    rec["robots"] = {"http_status": st, "url": final, "ai_agents_named": ai_named(groups), "crawl_delay": ours.get("delay"),
                     "root_allowed_for_us": allowed(ours, "/"), "group_applied": ours.get("agents")}
    time.sleep(DELAY)
    st2, _, tdm = fetch(base + "/.well-known/tdmrep.json", 100_000)
    rec["tdmrep_json"] = tdm[:2000] if st2 == 200 and tdm.strip().startswith(("[", "{")) else None
    if not rec["robots"]["root_allowed_for_us"]:
        rec["status"] = "robots disallows the home page for us"
        return rec
    time.sleep(DELAY)
    st, final, page = fetch(base + "/")
    text = text_of(re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", page))
    title = re.search(r"(?is)<title[^>]*>(.*?)</title>", page)
    rec["home"] = {"http_status": st, "final_url": final, "title": text_of(title.group(1))[:200] if title else None,
                   "bot_check": bool(BOTCHECK.search(page[:20000])) or st in (401, 403, 429, 503),
                   "paywall_cues": sorted(set(m.group(0).lower() for m in PAYWALL.finditer(text)))[:12],
                   "tdm_meta": (re.search(r'(?i)<meta[^>]+name="tdm-reservation"[^>]+content="([^"]*)"', page) or [None, None])[1],
                   "about_text": text[:600]}
    if rec["home"]["bot_check"] or st != 200:
        rec["status"] = "home page refused or bot check"
        return rec
    links = []
    for m in re.finditer(r'(?is)<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', page):
        href, label = html.unescape(m.group(1)), text_of(m.group(2))
        if TERMS_LINK.search(label) or TERMS_LINK.search(href.rsplit("/", 1)[-1]):
            url = urllib.parse.urljoin(final, href)
            if url.startswith("http") and url not in [l[0] for l in links]:
                links.append((url, label[:80]))
    links.sort(key=lambda l: (0 if re.search(r"terms|conditions|tos|agreement|voorwaarden|bedingungen", l[1] + l[0], re.I) else 1))
    rec["terms"] = []
    for url, label in links[:2]:
        u = urllib.parse.urlsplit(url)
        if registrable_host(u.netloc) == domain and not allowed(ours, u.path or "/"):
            rec["terms"].append({"url": url, "label": label, "skipped": "robots disallows"})
            continue
        time.sleep(DELAY)
        st3, final3, tpage = fetch(url)
        ttext = text_of(re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", tpage))
        rec["terms"].append({"url": final3, "label": label, "http_status": st3, "chars": len(ttext),
                             "bot_check": bool(BOTCHECK.search(tpage[:20000])) or st3 in (401, 403, 429, 503),
                             "clauses": sentences(ttext, CLAUSE)})
    if not rec["terms"]:
        # No terms link found on the home page (often a script-built page): try the usual paths, allowed ones only.
        for path in COMMON_PATHS:
            if not allowed(ours, path):
                continue
            time.sleep(DELAY)
            st3, final3, tpage = fetch(base + path)
            ttext = text_of(re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", tpage))
            if st3 == 200 and len(ttext) > 800 and re.search(r"(terms|conditions|agreement|use of (this|the) (site|service|website))", ttext[:3000], re.I) \
                    and not BOTCHECK.search(tpage[:20000]):
                rec["terms"].append({"url": final3, "label": f"(path {path})", "http_status": st3, "chars": len(ttext),
                                     "bot_check": False, "clauses": sentences(ttext, CLAUSE), "found_by": "common path"})
                break
    rec["status"] = "ok" if rec["terms"] else "no terms page found"
    return rec


def registrable_host(h):
    from build_union import registrable
    return registrable(h)


def main():
    args = sys.argv[1:]
    domains = json.loads((ROOT / "data" / "domains.json").read_text())["domains"]
    if "--min-libraries" in args:
        m = int(args[args.index("--min-libraries") + 1])
        domains = [d for d in domains if d["max_libraries"] >= m]
    if "--shard" in args:
        k, n = map(int, args[args.index("--shard") + 1].split("/"))
        domains = domains[k::n]
    OUTDIR.mkdir(parents=True, exist_ok=True)
    def needs(d):
        f = OUTDIR / f"{d['domain']}.json"
        if not f.exists():
            return True
        return "--retry-no-terms" in args and json.loads(f.read_text()).get("status") == "no terms link on home page"
    todo = [d for d in domains if needs(d)]
    print(f"{len(todo)} domains to fetch", flush=True)

    def work(d):
        try:
            rec = one(d["domain"])
        except Exception as e:
            rec = {"domain": d["domain"], "status": f"failed: {type(e).__name__}: {e}"}
        (OUTDIR / f"{d['domain']}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False))
        return d["domain"], rec.get("status")

    with ThreadPoolExecutor(max_workers=6) as ex:
        for dom, st in ex.map(work, todo):
            print(f"{dom}: {st}", flush=True)


if __name__ == "__main__":
    main()
