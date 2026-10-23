#!/usr/bin/env python3
"""to_skill_catalog: turn data/catalog.json into the strategic-research skill's site-catalog.json.

  python3 scripts/to_skill_catalog.py [--curated path/to/previous/site-catalog.json] [--tiers core,common]

Includes every platform in the chosen consensus tiers. Hand-curated entries from a previous catalog
are kept when the libraries did not surface that domain (official sources libraries rarely list, and
entries that point to a dedicated source skill), marked "source": "curated".
`automation` is the spirit reading (the stricter one); `automation_letter` is kept alongside.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACCESS = {"free": "free", "free_with_account": "account", "freemium": "account", "subscription": "subscription",
          "institutional": "institutional", "pay_per_use": "account", "mixed": "subscription", "unknown": "subscription"}


SEED_CAT = {"news": "news", "news_wire": "news", "fact_check": "news", "policy_news": "policy", "data_statistics": "data",
            "government_legal": "government", "platforms_social": "social", "reference": "academic", "open_scholarship": "academic"}


def category(p):
    if p.get("seed_group") and p["tier"] in ("local", "none", "recognized"):
        return SEED_CAT.get(p["seed_group"], "academic")
    c = p.get("category") or ""
    d = set(p.get("disciplines", []))
    if c == "legal" or d == {"law"}:
        return "legal"
    if c in ("news", "sports", "entertainment") or (c == "media_streaming" and p.get("open_web_tier")):
        return "news"
    if c == "social_platform":
        return "social"
    if c in ("search_engine",) and p.get("owner_type") == "commercial" and p.get("open_web_tier"):
        return "academic"
    if c == "government_official":
        return "government"
    if c == "data_statistics":
        return "markets" if "business_economics" in d else "data"
    if "business_economics" in d and c in ("aggregator", "index_abstract", "tool") and "law" not in d:
        return "markets" if c == "tool" else "academic"
    return "academic"


def region(domain):
    if re.search(r"\.gov$|\.mil$|\.fed\.us$", domain):
        return "us"
    if domain.endswith((".gov.uk", ".ac.uk", ".org.uk", ".co.uk", ".uk")):
        return "uk"
    if domain.endswith((".europa.eu", ".eu")):
        return "eu"
    if domain.endswith(".nl"):
        return "nl"
    return "global"


def slug(domain):
    return re.sub(r"[^a-z0-9]+", "-", domain.lower()).strip("-")


def main():
    args = sys.argv[1:]
    tiers = set((args[args.index("--tiers") + 1] if "--tiers" in args else "core,common").split(","))
    cat = json.loads((ROOT / "data" / "catalog.json").read_text())
    entries, seen = [], set()
    for p in cat["platforms"]:
        in_lib = p["tier"] in tiers
        in_ow = p.get("open_web_tier") in ("open-web", "open-web-curated")
        if not (in_lib or in_ow):
            continue
        access = ACCESS.get(p["access_model"], "subscription")
        e = {"id": slug(p["domain"]), "name": p["top_title"] if p["n_entries"] == 1 else (p.get("owner") or p["top_title"]),
             "domain": p["domain"], "category": category(p), "region": region(p["domain"]), "access": access,
             "automation": p["automation_spirit"], "automation_letter": p["automation_letter"],
             "useful_for": "; ".join(p["titles"][:5]) or (p.get("seed_group") or "open-web source").replace("_", " "),
             "owner_type": p["owner_type"],
             "library_consensus": {"tier": p["tier"], "max_libraries": p["max_libraries"], "of": cat["n_libraries"]},
             "open_web": ({"tier": p["open_web_tier"], "wikipedia_languages": (p.get("wikipedia") or {}).get("n_languages", 0),
                           "guide_libraries": (p.get("guides") or {}).get("n_libraries", 0)} if p.get("open_web_tier") else None),
             "terms": {"automated_access": p["automated_access"], "ai_tdm": p["ai_tdm"], "robots_ai": p["robots_ai"],
                       "urls": p["terms_urls"][:1]},
             "source": "library-consensus" if in_lib else p["open_web_tier"]}
        if access != "free":
            e["probe"] = f"https://{p['domain']}/"
        if p["access_model"] == "pay_per_use":
            e["notes"] = "Charges per use: an agent must not run up fees."
        entries.append(e)
        seen.add(p["domain"])
    if "--curated" in args:
        prev = json.loads(Path(args[args.index("--curated") + 1]).read_text())
        for e in prev.get("entries", []):
            dom = e["domain"]
            base = ".".join(dom.split(".")[-2:])
            if dom in seen or base in seen:
                continue
            e = dict(e)
            e["source"] = "curated"
            entries.append(e)
    for e in entries:
        if e.get("open_web") is None:
            e.pop("open_web", None)
    order = {"library-consensus": 0, "open-web": 1, "open-web-curated": 2, "curated": 3}
    entries.sort(key=lambda e: (order.get(e["source"], 9), e["category"], e["id"]))
    out = {"version": "2026-10-24",
           "about": ("Research sites for the built-in web source and the access scan (references/access-scan.md). "
                     "Entries marked library-consensus come from a union of the public A-Z database lists of "
                     f"{cat['n_libraries']} university libraries worldwide, kept when named by at least 10% of them in "
                     "3+ regions (tier common) or 25% in 5+ regions (tier core); access, owner type and terms readings "
                     "follow the published heuristic at https://github.com/lukewp/library-consensus-sources. "
                     "Entries marked open-web are cited in the most-read Wikipedia articles of 15+ of 20 languages, are among the 5 sources most cited in one language, or are linked from the news, free-web, data or government guides of 10%+ of libraries in 3+ regions; open-web-curated are seed-list sources below those thresholds, assessed the same way. Entries marked curated were added by hand. automation is the stricter (spirit) reading of "
                     "robots.txt and terms; automation_letter is the reading by the letter. Neither is legal advice: "
                     "the user's own agreements govern, and a profile can override any entry."),
           "categories": ["government", "legal", "policy", "news", "academic", "data", "markets", "social"],
           "regions": ["us", "eu", "uk", "nl", "global"],
           "entries": entries}
    (ROOT / "data" / "site-catalog.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    from collections import Counter
    print(len(entries), "entries", dict(Counter(e["source"] for e in entries)), dict(Counter(e["automation"] for e in entries)))


if __name__ == "__main__":
    main()
