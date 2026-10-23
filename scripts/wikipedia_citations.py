#!/usr/bin/env python3
"""wikipedia_citations: which domains do the most-read Wikipedia articles cite, across languages?

  python3 scripts/wikipedia_citations.py top        # top articles per language -> data/wikipedia/top_articles.json
  python3 scripts/wikipedia_citations.py cite       # their cited domains       -> data/wikipedia/raw/<lang>.jsonl
  python3 scripts/wikipedia_citations.py summarize  # domain counts             -> data/wikipedia/domains.json

Top articles: the Wikimedia Pageviews API (wikimedia.org, no robots.txt restrictions), monthly top lists for
the twelve months to MONTHS_END, summed, main-namespace titles only, top N per language.
Citations: each article page at /wiki/<title> (Wikipedia's robots.txt welcomes low-speed bots on article
pages and disallows /w/ and /api/, which are not used). Only links inside the article's reference lists
are counted. Archived links (web.archive.org and archive.today) are credited to the original domain.
Identifier resolvers (DOI, Handle, ISBN, VIAF and the like) are not counted as sources.
"""
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_union import registrable, SECOND_LEVEL  # noqa: E402

UA = "library-consensus-sources/0.2 (https://github.com/lukewp/library-consensus-sources; AI-assisted research)"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "wikipedia"
LANGS = ["en", "es", "de", "fr", "ja", "ru", "it", "pt", "zh", "pl", "nl", "ar", "fa", "tr", "ko", "id", "uk", "sv", "vi", "hi"]
TOP_N = 200
TOP_PER_LANG = 5   # a language's most-cited domains enter the open-web tier even below the cross-language threshold
MONTHS_END = (2026, 9)
DELAY = 1.0  # per language worker; 4 workers in parallel
IDENTIFIERS = {"doi.org", "handle.net", "viaf.org", "isni.org", "orcid.org", "loc.gov/id", "d-nb.info", "worldcat.org", "wikidata.org",
               "wikipedia.org", "wikimedia.org", "wikisource.org", "wiktionary.org", "wikiquote.org", "wikinews.org", "mediawiki.org",
               "identifiers.org", "arxiv.org/abs", "pubmed.ncbi", "jstor.org/stable", "ssrn", "zenodo", "bnf.fr/ark", "idref.fr",
               "geohack", "toolforge.org", "wmflabs.org", "openstreetmap.org", "google.com/maps", "archive.ph", "archive.today",
               "archive.is", "web.archive.org"}
DROP_REG = {"doi.org", "handle.net", "viaf.org", "isni.org", "orcid.org", "wikidata.org", "wikipedia.org", "wikimedia.org", "wikisource.org",
            "wiktionary.org", "mediawiki.org", "toolforge.org", "wmflabs.org", "identifiers.org", "idref.fr", "d-nb.info", "archive.ph",
            "archive.today", "archive.is", "webcitation.org", "archive-it.org", "ghostarchive.org", "issn.org", "zdb-katalog.de", "sudoc.fr", "sudoc.abes.fr", "ndl.go.jp", "nla.gov.au/anbd", "bnf.fr/ark"}


def get(url, tries=3):
    for i in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                time.sleep(30 * (i + 1))
                continue
            return e.code, ""
        except Exception:
            time.sleep(5)
    return None, ""


def months():
    y, m = MONTHS_END
    out = []
    for _ in range(12):
        out.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


def top():
    res = {}
    for lang in LANGS:
        views = Counter()
        for y, m in months():
            st, body = get(f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/{lang}.wikipedia/all-access/{y}/{m:02d}/all-days")
            if st == 200:
                for a in json.loads(body)["items"][0]["articles"]:
                    views[a["article"]] += a["views"]
            time.sleep(0.5)
        titles = [t for t, _ in views.most_common() if ":" not in t and t not in ("-", "Main_Page")][: TOP_N + 10]
        res[lang] = [{"title": t, "views_12m": views[t]} for t in titles]
        print(lang, len(titles), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "top_articles.json").write_text(json.dumps({"months_end": MONTHS_END, "top_n": TOP_N, "languages": res}, ensure_ascii=False, indent=1))


REF_BLOCK = re.compile(r'(?is)<ol class="[^"]*\breferences\b[^"]*"[^>]*>(.*?)</ol>')
HREF = re.compile(r'(?is)<a[^>]+class="[^"]*external[^"]*"[^>]+href="([^"]+)"|<a[^>]+href="([^"]+)"[^>]+class="[^"]*external[^"]*"')


def credit(url):
    url = html.unescape(url)
    if url.startswith("//"):
        url = "https:" + url
    m = re.match(r"https?://web\.archive\.org/web/[^/]+/(.+)", url) or re.match(r"https?://archive\.(?:org|ph|today|is)/[^/]+/(https?://.+)", url)
    archived = bool(m)
    if m:
        url = m.group(1)
        if not url.startswith("http"):
            url = "http://" + url
    host = urllib.parse.urlsplit(url).netloc.lower().split("@")[-1]
    if not host:
        return None, archived
    reg = registrable(host)
    if reg in DROP_REG:
        return None, archived
    return reg, archived


def cite_lang(lang, articles):
    path = OUT / "raw" / f"{lang}.jsonl"
    done = set()
    if path.exists():
        done = {json.loads(l)["title"] for l in path.read_text().splitlines() if l.strip()}
    with path.open("a") as fh:
        n = 0
        for a in articles:
            if n >= TOP_N:
                break
            t = a["title"]
            if t in done:
                n += 1
                continue
            st, page = get(f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(t)}")
            time.sleep(DELAY)
            if st != 200:
                continue
            blocks = REF_BLOCK.findall(page)
            if not blocks:
                continue  # main pages, disambiguations, lists without references
            doms, arch = Counter(), 0
            for b in blocks:
                for h1, h2 in HREF.findall(b):
                    d, was_archived = credit(h1 or h2)
                    if d:
                        doms[d] += 1
                        arch += was_archived
            fh.write(json.dumps({"lang": lang, "title": t, "views_12m": a["views_12m"], "domains": dict(doms), "archived_links": arch}, ensure_ascii=False) + "\n")
            fh.flush()
            n += 1
    return lang, n


def cite():
    top = json.loads((OUT / "top_articles.json").read_text())["languages"]
    (OUT / "raw").mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as ex:
        for lang, n in ex.map(lambda l: cite_lang(l, top[l]), LANGS):
            print(lang, n, "articles with references", flush=True)


def summarize():
    by = defaultdict(lambda: {"languages": set(), "articles": 0, "citations": 0})
    per_lang = Counter()
    for f in sorted((OUT / "raw").glob("*.jsonl")):
        for line in f.read_text().splitlines():
            r = json.loads(line)
            per_lang[r["lang"]] += 1
            for d, c in r["domains"].items():
                if d in SECOND_LEVEL or d in DROP_REG:
                    continue  # a bare public suffix (collected before the suffix list grew) or an archive/identifier host
                x = by[d]
                x["languages"].add(r["lang"])
                x["articles"] += 1
                x["citations"] += c
    # Per language: the TOP_PER_LANG domains cited by the most articles (ties broken by total citations).
    per = defaultdict(Counter)
    cites = defaultdict(Counter)
    for f in sorted((OUT / "raw").glob("*.jsonl")):
        for line in f.read_text().splitlines():
            r = json.loads(line)
            for d, c in r["domains"].items():
                if d in SECOND_LEVEL or d in DROP_REG:
                    continue
                per[r["lang"]][d] += 1
                cites[r["lang"]][d] += c
    top_in = defaultdict(list)
    for lang, ctr in per.items():
        for d, _ in sorted(ctr.items(), key=lambda kv: (-kv[1], -cites[lang][kv[0]], kv[0]))[:TOP_PER_LANG]:
            top_in[d].append(lang)
    rows = sorted(({"domain": d, "n_languages": len(x["languages"]), "languages": sorted(x["languages"]), "n_articles": x["articles"],
                    "citations": x["citations"], "top_in_languages": sorted(top_in.get(d, []))} for d, x in by.items()),
                  key=lambda r: (-r["n_languages"], -r["n_articles"]))
    (OUT / "domains.json").write_text(json.dumps({"articles_per_language": dict(per_lang), "n_articles": sum(per_lang.values()),
                                                  "domains": rows}, ensure_ascii=False, indent=1))
    print(sum(per_lang.values()), "articles;", len(rows), "domains;", sum(1 for r in rows if r["n_languages"] >= 10), "cited in 10+ languages")


if __name__ == "__main__":
    {"top": top, "cite": cite, "summarize": summarize}[sys.argv[1]]()
