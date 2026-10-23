#!/usr/bin/env python3
"""collect_libguides: read each sampled library's public LibGuides A-Z database list.

  python3 scripts/collect_libguides.py data/sample.json [--only HOST ...]

Writes data/raw/<host>.json (the list) and data/raw/<host>.robots.txt (the policy it ran under).

Politeness and policy (see METHOD.md):
  - Identifies itself honestly (USER_AGENT below); never impersonates a browser.
  - Reads robots.txt first. Skips the host if our agent or "*" is disallowed from the A-Z
    page or the list endpoint the page itself calls. Records every AI agent the file names.
  - Fetches only the unfiltered list (no subject, type or search filters: robots.txt on
    LibGuides disallows filtered A-Z views), page by page, as the page's own "load more" does.
  - Waits the larger of the robots Crawl-delay and MIN_DELAY between requests to a host.
Standard library only.
"""
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USER_AGENT = "library-consensus-sources/0.1 (AI-assisted research collection; +https://github.com/lukewp/library-consensus-sources)"
MIN_DELAY = 10.0
TIMEOUT = 60
AI_AGENT_NAMES = ["gptbot", "chatgpt-user", "oai-searchbot", "ccbot", "google-extended", "gemini-deep-research", "claudebot",
                  "claude-user", "claude-searchbot", "anthropic-ai", "claude-web", "perplexitybot", "perplexity-user", "bytespider",
                  "amazonbot", "applebot-extended", "meta-externalagent", "facebookbot", "cohere-ai", "youbot", "diffbot", "timpibot",
                  "omgilibot", "imagesiftbot", "duckassistbot", "mistralai-user"]
OUR_TOKENS = ["library-consensus-sources"]
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get(url, last):
    wait = last["delay"] - (time.time() - last["t"])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json;q=0.9,*/*;q=0.5"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            body = r.read().decode("utf-8", "replace")
            status, final = r.status, r.geturl()
    except urllib.error.HTTPError as e:
        body, status, final = e.read().decode("utf-8", "replace") if e.fp else "", e.code, url
    finally:
        last["t"] = time.time()
    return status, final, body


def parse_robots(text):
    groups, cur, in_rules = [], None, False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        k, v = [x.strip() for x in line.split(":", 1)]
        k = k.lower()
        if k == "user-agent":
            if cur is None or in_rules:
                cur = {"agents": [], "rules": [], "delay": None}
                groups.append(cur)
                in_rules = False
            cur["agents"].append(v.lower())
        elif cur is not None and k in ("allow", "disallow"):
            in_rules = True
            cur["rules"].append((k, v))
        elif cur is not None and k == "crawl-delay":
            in_rules = True
            try:
                cur["delay"] = float(v)
            except ValueError:
                pass
    return groups


def group_for(groups, tokens):
    for g in groups:
        if any(any(t in a for t in tokens) for a in g["agents"]):
            return g
    for g in groups:
        if "*" in g["agents"]:
            return g
    return {"agents": [], "rules": [], "delay": None}


def allowed(group, path):
    best, verdict = -1, True
    for k, pat in group["rules"]:
        if pat == "":
            continue
        rx = "^" + re.escape(pat).replace(r"\*", ".*")
        if rx.endswith(r"\$"):
            rx = rx[:-2] + "$"
        if re.match(rx, path) and len(pat) > best:
            best, verdict = len(pat), (k == "allow")
    return verdict


def ai_named(groups):
    out = {}
    for g in groups:
        full_block = any(k == "disallow" and v == "/" for k, v in g["rules"])
        for a in g["agents"]:
            for name in AI_AGENT_NAMES:
                if name in a:
                    out[a] = "disallow_all" if full_block else "partial"
    return out


def text_of(fragment):
    s = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def unwrap(href):
    href = html.unescape(href)
    try:
        u = urllib.parse.urlsplit(href)
    except ValueError:
        return href, None
    q = urllib.parse.parse_qs(u.query)
    for key in ("url", "qurl", "target"):
        if key in q and q[key][0].startswith("http"):
            inner = q[key][0]
            return href, urllib.parse.urlsplit(inner).netloc.lower()
    return href, u.netloc.lower()


ITEM_RX = re.compile(r'<div class="az-item">(.*?)(?=<div class="az-item">|<div id="s-lg-az-name-|\Z)', re.S)


def parse_items(fragment, host):
    items = []
    for m in ITEM_RX.finditer(fragment):
        block = m.group(1)
        a = re.search(r'<a\s+href="([^"]+)"[^>]*class="az-title"[^>]*>(.*?)</a>', block, re.S) or \
            re.search(r'<a[^>]*class="az-title"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not a:
            continue
        href, link_host = unwrap(a.group(1))
        flags_html = " ".join(re.findall(r'<div class="az-flags">(.*?)</div>', block, re.S))
        flags = sorted(set(x.strip() for x in re.findall(r'(?:title|alt|aria-label)="([^"]+)"', flags_html) if x.strip()) |
                       set(x for x in [text_of(flags_html)] if x))
        fields = {}
        for lab, val in re.findall(r'az-configured-fields-label[^>]*>(.*?)</span>\s*<span class="az-configured-fields-value[^"]*">(.*?)</span>', block, re.S):
            fields[text_of(lab).rstrip(":").strip()] = text_of(val)
        desc = re.search(r'<div class="az-description(?:-full|-short)?">(.*?)</div>', block, re.S)
        badges = sorted(set(text_of(b) for b in re.findall(r'<span class="[^"]*badge[^"]*"[^>]*>(.*?)</span>', block, re.S) if text_of(b)))
        items.append({
            "title": text_of(a.group(2)),
            "href": href,
            "link_host": link_host,
            "via_library_redirect": link_host == host,
            "description": text_of(desc.group(1))[:600] if desc else "",
            "fields": fields,
            "flags": flags,
            "badges": badges,
        })
    return items


def collect(lib):
    host = lib["host"]
    out = {"library": lib, "collected_at": now(), "user_agent": USER_AGENT, "status": None, "items": []}
    last = {"t": 0.0, "delay": MIN_DELAY}
    st, _, robots = get(f"https://{host}/robots.txt", last)
    (RAW / f"{host}.robots.txt").write_text(robots if st == 200 else f"# HTTP {st}\n")
    groups = parse_robots(robots) if st == 200 else []
    ours = group_for(groups, OUR_TOKENS)
    out["robots"] = {"http_status": st, "ai_agents_named": ai_named(groups),
                     "crawl_delay": ours.get("delay"), "group_applied": ours.get("agents")}
    last["delay"] = max(MIN_DELAY, ours.get("delay") or 0)
    page_path = "/az/databases"
    for p in ("/az/databases", "/az.php"):
        if not allowed(ours, p):
            out["status"] = f"excluded: robots disallows {p}"
            return out
    if not allowed(ours, "/process/az/render-list"):
        out["status"] = "excluded: robots disallows the list endpoint"
        return out
    st, final, page = get(f"https://{host}{page_path}", last)
    if st != 200 or "az" not in final:
        page_path = "/az.php"
        st, final, page = get(f"https://{host}{page_path}", last)
    if st != 200:
        out["status"] = f"failed: A-Z page HTTP {st}"
        return out
    def site_id_of(text):
        return re.search(r"lazyLoad\(\s*\d+\s*,\s*(\d+)\s*\)", text) or re.search(r"site_id[\"']?\s*[:=]\s*[\"']?(\d+)", text)
    m = site_id_of(page)
    if not m and page_path != "/az.php":
        st, final, page = get(f"https://{host}/az.php", last)
        m = site_id_of(page) if st == 200 else None
    if not m:
        out["status"] = "failed: not a LibGuides A-Z page (no site id)"
        return out
    site_id = m.group(1)
    out["site_id"] = site_id
    t = re.search(r"<title>(.*?)</title>", page, re.S)
    og = re.search(r'<meta[^>]+property="og:site_name"[^>]+content="([^"]*)"', page)
    bc = re.search(r'<ol[^>]*class="breadcrumb"[^>]*>(.*?)</ol>', page, re.S) or re.search(r'id="s-lib-bc"[^>]*>(.*?)</(?:div|nav)>', page, re.S)
    out["site_identity"] = {"title": text_of(t.group(1)) if t else None, "og_site_name": html.unescape(og.group(1)) if og else None,
                            "breadcrumb": text_of(bc.group(1))[:300] if bc else None}
    out["az_url"] = final
    seen, page_no, reported = set(), 1, None
    while True:
        q = urllib.parse.urlencode({"search": "", "subject_id": "", "type_id": "", "vendor_id": "", "access_mode_id": "",
                                    "page": page_no, "site_id": site_id, "content_id": 0, "is_widget": 0, "bootstrap5": "true",
                                    "page_size": 0, "preview": "", "sublist_id": 0, "alpha": ""})
        st, _, body = get(f"https://{host}/process/az/render-list?{q}", last)
        if st != 200:
            out["status"] = f"partial: list page {page_no} HTTP {st}" if out["items"] else f"failed: list HTTP {st}"
            break
        try:
            data = json.loads(body)["data"]
        except (ValueError, KeyError, TypeError):
            out["status"] = "partial: unparseable list page" if out["items"] else "failed: unparseable list"
            break
        reported = data.get("count", reported)
        new = [it for it in parse_items(data.get("html", ""), host) if (it["title"], it["href"]) not in seen]
        for it in new:
            seen.add((it["title"], it["href"]))
        out["items"].extend(new)
        if not new or (reported and len(out["items"]) >= reported) or page_no >= 20:
            break
        page_no += 1
    out["count_reported"] = reported
    out["pages_read"] = page_no
    if out["status"] is None:
        out["status"] = "collected" if not reported or len(out["items"]) >= reported else f"partial: {len(out['items'])} of {reported}"
    return out


def main():
    args = sys.argv[1:]
    sample = json.loads(Path(args[0]).read_text())
    only = set(args[args.index("--only") + 1:]) if "--only" in args else None
    if "--shard" in args:  # --shard K/N: every Nth library starting at K, so N processes split the sample by host
        k, n = map(int, args[args.index("--shard") + 1].split("/"))
        sample["libraries"] = sample["libraries"][k::n]
    RAW.mkdir(parents=True, exist_ok=True)
    for lib in sample["libraries"]:
        if only and lib["host"] not in only:
            continue
        target = RAW / f"{lib['host']}.json"
        if target.exists() and str(json.loads(target.read_text()).get("status", "")).startswith(("collected", "partial")):
            print(f"skip {lib['host']} (already collected)", flush=True)
            continue
        try:
            res = collect(lib)
        except Exception as e:  # record and move on; one library never stops the run
            res = {"library": lib, "collected_at": now(), "status": f"failed: {type(e).__name__}: {e}", "items": []}
        target.write_text(json.dumps(res, indent=1, ensure_ascii=False))
        print(f"{lib['host']}: {res['status']} ({len(res['items'])} items)", flush=True)


if __name__ == "__main__":
    main()
