#!/usr/bin/env python3
"""build_openweb: combine the open-web signals into candidate domains for the open-web tier.

  python3 scripts/build_openweb.py    # -> data/openweb.json (signals per domain) and data/openweb_domains.json (for fetch_terms)

Signals per registrable domain:
  wikipedia: in how many of the 20 languages' most-read articles it is cited, and in how many articles
  guides:    how many libraries' news / free-web / data / government guides link to it, in how many regions
  seed:      the hand seed group, if any (data/openweb_seed.json)
Open-web tier rule (published in METHOD.md):
  open-web          cited in the most-read articles of >= 15 of 20 languages,
                    or among the 10 domains most cited by one language's most-read articles,
                    or linked from the guides of >= 10% of the libraries that have such guides, in >= 3 regions
  open-web-curated  on the seed list but below both thresholds
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIKI_LANG_MIN = 15
GUIDE_SHARE_MIN, GUIDE_REGION_MIN = 0.10, 3
CANDIDATE_WIKI_MIN, CANDIDATE_GUIDE_MIN = 10, 5   # wider net: domains worth assessing (terms, owner)


def main():
    wiki = json.loads((ROOT / "data" / "wikipedia" / "domains.json").read_text())
    guides = json.loads((ROOT / "data" / "guides" / "domains.json").read_text())
    seed = {s["domain"]: s["group"] for s in json.loads((ROOT / "data" / "openweb_seed.json").read_text())["seeds"]}
    n_g = guides["n_libraries_with_guides"]
    sig = {}
    for r in wiki["domains"]:
        if r["n_languages"] >= 2:
            sig.setdefault(r["domain"], {})["wikipedia"] = {"n_languages": r["n_languages"], "n_articles": r["n_articles"], "citations": r["citations"],
                                                         "top_in_languages": r.get("top_in_languages", [])}
        elif r.get("top_in_languages"):
            sig.setdefault(r["domain"], {})["wikipedia"] = {"n_languages": r["n_languages"], "n_articles": r["n_articles"], "citations": r["citations"],
                                                         "top_in_languages": r["top_in_languages"]}
    for r in guides["domains"]:
        if r["n_libraries"] >= 2:
            sig.setdefault(r["domain"], {})["guides"] = {"n_libraries": r["n_libraries"], "share": round(r["n_libraries"] / n_g, 4),
                                                        "n_regions": r["n_regions"], "kinds": r["kinds"]}
    for d, g in seed.items():
        sig.setdefault(d, {})["seed"] = g
    rows = []
    for d, s in sig.items():
        w, g = s.get("wikipedia", {}), s.get("guides", {})
        consensus = (w.get("n_languages", 0) >= WIKI_LANG_MIN or bool(w.get("top_in_languages"))
                     or (g.get("share", 0) >= GUIDE_SHARE_MIN and g.get("n_regions", 0) >= GUIDE_REGION_MIN))
        tier = "open-web" if consensus else ("open-web-curated" if "seed" in s else None)
        candidate = tier or w.get("n_languages", 0) >= CANDIDATE_WIKI_MIN or g.get("n_libraries", 0) >= CANDIDATE_GUIDE_MIN
        if candidate:
            rows.append({"domain": d, "open_web_tier": tier, **s})
    rows.sort(key=lambda r: (r["open_web_tier"] is None, r["open_web_tier"] or "", -r.get("wikipedia", {}).get("n_languages", 0),
                             -r.get("guides", {}).get("n_libraries", 0)))
    out = {"rule": {"wikipedia_languages_min": WIKI_LANG_MIN, "of_languages": 20, "guide_share_min": GUIDE_SHARE_MIN,
                    "guide_regions_min": GUIDE_REGION_MIN, "libraries_with_guides": n_g,
                    "wikipedia_articles": wiki["n_articles"], "top_per_language": 10}, "domains": rows}
    (ROOT / "data" / "openweb.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    (ROOT / "data" / "openweb_domains.json").write_text(json.dumps({"domains": [{"domain": r["domain"], "max_libraries": 99,
        "titles": [], "vendors": []} for r in rows]}, indent=1))
    from collections import Counter
    print(len(rows), "candidates", dict(Counter(r["open_web_tier"] for r in rows)))


if __name__ == "__main__":
    main()
