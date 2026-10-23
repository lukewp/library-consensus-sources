#!/usr/bin/env python3
"""resolve_links: find the platform domain for union entries whose library links are library redirects.

  python3 scripts/resolve_links.py [--min-libraries 2]

For each union entry with no domain yet, it picks up to three libraries' redirect links and asks
one of them where it points (a single GET with redirects NOT followed, reading the Location header).
It skips any link whose path the library's robots.txt disallows for us (LibGuides disallows
/go.php and /friendly.php, so those are never requested), and waits the host's crawl delay.
Writes data/resolved.json: {key: {"location": ..., "domain": ..., "via": host}}.
"""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_libguides import USER_AGENT, MIN_DELAY, parse_robots, group_for, allowed, OUR_TOKENS, unwrap  # noqa: E402
from build_union import registrable, PROXY_HOST  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "resolved.json"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def location(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with OPENER.open(req, timeout=30) as r:
            return r.status, r.headers.get("Location")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location")
    except Exception as e:  # network errors: record nothing
        return None, None


def main():
    args = sys.argv[1:]
    min_libs = int(args[args.index("--min-libraries") + 1]) if "--min-libraries" in args else 2
    union = json.loads((ROOT / "data" / "union.json").read_text())["entries"]
    done = json.loads(OUT.read_text()) if OUT.exists() else {}
    robots = {}
    for f in (ROOT / "data" / "raw").glob("*.robots.txt"):
        host = f.name[: -len(".robots.txt")]
        robots[host] = group_for(parse_robots(f.read_text()), OUR_TOKENS)
    jobs = {}  # host -> list of (key, url)
    for e in union:
        if e["n_libraries"] < min_libs or e["domains"] or e["key"] in done:
            continue
        options = []
        for host, href in e["sample_links"].items():
            u = urllib.parse.urlsplit(href)
            if u.netloc != host or not allowed(robots.get(host, {"rules": []}), u.path + ("?" + u.query if u.query else "")):
                continue
            options.append((len(jobs.get(host, [])), host, href))
        if options:  # spread the load: ask the library with the fewest queued requests
            _, host, href = min(options)
            jobs.setdefault(host, []).append((e["key"], href))
    print(f"{sum(len(v) for v in jobs.values())} links to resolve across {len(jobs)} hosts", flush=True)

    def run_host(host):
        delay = max(MIN_DELAY, robots.get(host, {}).get("delay") or 0)
        res = {}
        for key, href in jobs[host]:
            st, loc = location(href)
            if loc:
                loc = urllib.parse.urljoin(href, loc)
                _, inner = unwrap(loc)
                if inner and not PROXY_HOST.search(inner) and inner != host:
                    res[key] = {"location": loc, "domain": registrable(inner), "host": inner, "via": host}
            time.sleep(delay)
        return res

    with ThreadPoolExecutor(max_workers=24) as ex:
        for res in ex.map(run_host, list(jobs)):
            done.update(res)
            OUT.write_text(json.dumps(done, indent=1, ensure_ascii=False))
    print(f"resolved {len(done)} entries", flush=True)


if __name__ == "__main__":
    main()
