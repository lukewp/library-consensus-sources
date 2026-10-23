#!/usr/bin/env python3
"""make_domains: list every platform domain the union points to, with how much the libraries use it.

  python3 scripts/make_domains.py      # reads data/union.json and data/resolved.json, writes data/domains.json

An entry contributes its plurality domain (the one most libraries link to), plus any other domain
at least two libraries link to for it. Domains resolved from library redirects count as well.
"""
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    union = json.loads((ROOT / "data" / "union.json").read_text())
    resolved = json.loads((ROOT / "data" / "resolved.json").read_text()) if (ROOT / "data" / "resolved.json").exists() else {}
    local = set(json.loads((ROOT / "data" / "local_domains.json").read_text()))
    agg = defaultdict(lambda: {"entries": 0, "max_libraries": 0, "library_mentions": 0, "titles": [], "vendors": defaultdict(int)})
    for e in union["entries"]:
        doms = dict(e["domains"])
        r = resolved.get(e["key"])
        if r and r["domain"] not in local:
            doms[r["domain"]] = doms.get(r["domain"], 0) + 1
        if not doms:
            continue
        top = max(doms, key=doms.get)
        chosen = {top} | {d for d, c in doms.items() if c >= 2}
        for d in chosen:
            a = agg[d]
            a["entries"] += 1
            a["max_libraries"] = max(a["max_libraries"], e["n_libraries"])
            a["library_mentions"] += e["n_libraries"]
            if len(a["titles"]) < 8:
                a["titles"].append(e["title"])
            for v in e.get("vendors", {}):
                a["vendors"][v] += 1
    out = [{"domain": d, "entries": a["entries"], "max_libraries": a["max_libraries"], "library_mentions": a["library_mentions"],
            "titles": a["titles"], "vendors": sorted(a["vendors"], key=a["vendors"].get, reverse=True)[:3]}
           for d, a in agg.items()]
    out.sort(key=lambda x: (-x["library_mentions"], x["domain"]))
    (ROOT / "data" / "domains.json").write_text(json.dumps({"n_domains": len(out), "domains": out}, indent=1, ensure_ascii=False))
    print(f"{len(out)} domains; with an entry named by 3+ libraries: {sum(1 for x in out if x['max_libraries'] >= 3)}")


if __name__ == "__main__":
    main()
