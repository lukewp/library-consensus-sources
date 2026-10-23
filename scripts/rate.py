#!/usr/bin/env python3
"""rate: apply the sourcing heuristic and write the catalog.

  python3 scripts/rate.py     # reads union, domains, owner and terms readings; writes data/catalog.json and data/catalog.csv

Consensus tier (per entry, then the best tier of a domain's entries), with N = libraries collected:
  core        named by >= 25% of libraries, in >= 5 regions
  common      named by >= 10% of libraries, in >= 3 regions
  recognized  named by >= 3 libraries
  local       otherwise

Automation (per domain), two readings of the same evidence:
  manual-only  terms prohibit automated access, or prohibit AI / text-and-data-mining use; or robots.txt
               blocks all bots for us; or the site charges per use
  human-pace   AI / TDM rights reserved; automated access restricted (rate limits, API only); robots.txt
               blocks AI crawlers; a bot check answered an honest request; the terms could not be read;
               or access is by subscription or institutional licence
  allowed      none of the above: the terms were read and permit or are silent on automated access, and
               nothing blocks AI agents
  automation_letter treats a robots.txt block on AI *user* agents (ChatGPT-User, Claude-User,
  Gemini-Deep-Research...) as binding only on the agents it names, so other agents get human-pace.
  automation_spirit treats any such block as binding on every AI agent, so it is manual-only.
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ORDER = {"core": 0, "common": 1, "recognized": 2, "local": 3}
STRICT = {"allowed": 0, "human-pace": 1, "manual-only": 2}


def tier(n, regions, total):
    share = n / total
    if share >= 0.25 and regions >= 5:
        return "core"
    if share >= 0.10 and regions >= 3:
        return "common"
    if n >= 3:
        return "recognized"
    return "local"


def automation(r, o, spirit):
    reasons = []
    if r is None:
        return "human-pace", ["terms not fetched"]
    aa, ai, rob, bc = r.get("automated_access"), r.get("ai_tdm"), r.get("robots_ai"), r.get("bot_check")
    am = (o or {}).get("access_model", "unknown")
    if aa == "prohibited":
        reasons.append("terms prohibit automated access")
    if ai == "prohibited":
        reasons.append("terms prohibit using content with AI tools")
    if rob == "blocks_all_bots":
        reasons.append("robots.txt blocks all bots")
    if am == "pay_per_use":
        reasons.append("charges per use")
    if spirit and rob == "blocks_ai_user_agents":
        reasons.append("robots.txt blocks AI agents acting for users")
    if reasons:
        return "manual-only", reasons
    if ai == "reserved":
        reasons.append("TDM rights reserved")
    if ai == "training_prohibited":
        reasons.append("terms prohibit AI training or data mining")
    if aa == "restricted":
        reasons.append("automated access restricted")
    if rob in ("blocks_ai_crawlers", "blocks_ai_user_agents"):
        reasons.append("robots.txt blocks named AI agents")
    if bc:
        reasons.append("bot check answered an honest request")
    if aa == "unknown":
        reasons.append("terms could not be read")
    if rob == "unknown":
        reasons.append("robots.txt could not be read")
    if am in ("subscription", "institutional", "mixed", "freemium", "unknown"):
        reasons.append(f"access: {am}")
    if reasons:
        return "human-pace", reasons
    return "allowed", ["terms read: permit or silent; no AI blocks"]


def main():
    union = json.loads((ROOT / "data" / "union.json").read_text())
    total = union["n_libraries"]
    resolved = json.loads((ROOT / "data" / "resolved.json").read_text()) if (ROOT / "data" / "resolved.json").exists() else {}
    owners = {}
    for f in sorted((ROOT / "data" / "owner").glob("out-*.jsonl")):
        for line in f.read_text().splitlines():
            if line.strip():
                o = json.loads(line)
                owners[o["domain"]] = o
    readings = {r["domain"]: r for r in json.loads((ROOT / "data" / "terms" / "readings.json").read_text())["readings"]}
    # Reviewed corrections, each with its reason: data/overrides.json {"owner": {domain: {field: {"to":..,"reason":..}}}, "readings": {...}}
    ov_path = ROOT / "data" / "overrides.json"
    overrides = json.loads(ov_path.read_text()) if ov_path.exists() else {"owner": {}, "readings": {}}
    for dom, fields in overrides.get("owner", {}).items():
        o = owners.setdefault(dom, {"domain": dom})
        for f, v in fields.items():
            o[f] = v["to"]
            o.setdefault("corrected", []).append(f)
    for dom, fields in overrides.get("readings", {}).items():
        r = readings.setdefault(dom, {"domain": dom})
        for f, v in fields.items():
            r[f] = v["to"]
            r.setdefault("evidence", {})[f] = f"corrected on review: {v['reason']}"
    by_domain = defaultdict(list)
    entries_out = []
    for e in union["entries"]:
        t = tier(e["n_libraries"], e["n_regions"], total)
        doms = dict(e["domains"])
        rr = resolved.get(e["key"])
        if rr:
            doms[rr["domain"]] = doms.get(rr["domain"], 0) + 1
        dom = max(doms, key=doms.get) if doms else None
        rec = {"title": e["title"], "key": e["key"], "tier": t, "n_libraries": e["n_libraries"], "share": e["share"],
               "n_regions": e["n_regions"], "n_countries": e["n_countries"], "domain": dom,
               "disciplines": e.get("disciplines", []), "resource_type": e.get("resource_type"),
               "free_flagged_by": e["free_flagged_by"], "restricted_flagged_by": e.get("restricted_flagged_by", 0),
               "vendors": list(e.get("vendors", {}))[:2]}
        entries_out.append(rec)
        if dom:
            by_domain[dom].append(rec)
    platforms = []
    for dom, recs in by_domain.items():
        best = min(recs, key=lambda r: ORDER[r["tier"]])
        r, o = readings.get(dom), owners.get(dom)
        letter, why_l = automation(r, o, spirit=False)
        spirit, why_s = automation(r, o, spirit=True)
        free_votes = sum(x["free_flagged_by"] for x in recs)
        platforms.append({
            "domain": dom, "tier": best["tier"], "top_title": best["title"], "max_libraries": best["n_libraries"],
            "max_share": best["share"], "regions_of_top": best["n_regions"],
            "n_entries": len(recs), "owner": (o or {}).get("owner"), "owner_type": (o or {}).get("owner_type", "unknown"),
            "access_model": (o or {}).get("access_model", "unknown"), "category": (o or {}).get("category"),
            "owner_confidence": (o or {}).get("confidence"), "libraries_flag_free": free_votes,
            "corrected_on_review": (o or {}).get("corrected", []) + [f for f in ((r or {}).get("evidence") or {}) if str(((r or {}).get("evidence") or {}).get(f, "")).startswith("corrected on review")],
            "automated_access": (r or {}).get("automated_access", "unknown"), "ai_tdm": (r or {}).get("ai_tdm", "unknown"),
            "robots_ai": (r or {}).get("robots_ai", "unknown"), "robots_ai_agents": (r or {}).get("robots_ai_agents", []),
            "bot_check": (r or {}).get("bot_check"), "paywall_cues": (r or {}).get("paywall_cues", []),
            "terms_urls": (r or {}).get("terms_urls", []), "evidence": (r or {}).get("evidence", {}),
            "automation_letter": letter, "automation_letter_reasons": why_l,
            "automation_spirit": spirit, "automation_spirit_reasons": why_s,
            "disciplines": sorted({d for x in recs for d in x["disciplines"] if d != "unclassified"}),
            "titles": [x["title"] for x in sorted(recs, key=lambda x: -x["n_libraries"])[:6]],
        })
    # Open-web signals and tier (data/openweb.json, from build_openweb.py)
    ow_path = ROOT / "data" / "openweb.json"
    ow = {r["domain"]: r for r in json.loads(ow_path.read_text())["domains"]} if ow_path.exists() else {}
    have = {p["domain"]: p for p in platforms}
    for dom, row in ow.items():
        p = have.get(dom)
        if p is None:
            r, o = readings.get(dom), owners.get(dom)
            letter, why_l = automation(r, o, spirit=False)
            spirit, why_s = automation(r, o, spirit=True)
            p = {"domain": dom, "tier": "none", "top_title": (o or {}).get("owner") or dom, "max_libraries": 0, "max_share": 0,
                 "regions_of_top": 0, "n_entries": 0, "owner": (o or {}).get("owner"), "owner_type": (o or {}).get("owner_type", "unknown"),
                 "access_model": (o or {}).get("access_model", "unknown"), "category": (o or {}).get("category"),
                 "owner_confidence": (o or {}).get("confidence"), "libraries_flag_free": 0,
                 "corrected_on_review": (o or {}).get("corrected", []),
                 "automated_access": (r or {}).get("automated_access", "unknown"), "ai_tdm": (r or {}).get("ai_tdm", "unknown"),
                 "robots_ai": (r or {}).get("robots_ai", "unknown"), "robots_ai_agents": (r or {}).get("robots_ai_agents", []),
                 "bot_check": (r or {}).get("bot_check"), "paywall_cues": (r or {}).get("paywall_cues", []),
                 "terms_urls": (r or {}).get("terms_urls", []), "evidence": (r or {}).get("evidence", {}),
                 "automation_letter": letter, "automation_letter_reasons": why_l,
                 "automation_spirit": spirit, "automation_spirit_reasons": why_s, "disciplines": [], "titles": []}
            platforms.append(p)
            have[dom] = p
        p["open_web_tier"] = row.get("open_web_tier")
        p["wikipedia"] = row.get("wikipedia")
        p["guides"] = row.get("guides")
        p["seed_group"] = row.get("seed")
    for p in platforms:
        p.setdefault("open_web_tier", None)
    ORDER["none"] = 4
    platforms.sort(key=lambda p: (ORDER[p["tier"]], -p["max_libraries"], p["domain"]))
    out = {"n_libraries": total, "n_entries": len(entries_out), "n_platforms": len(platforms),
           "platforms": platforms, "entries": entries_out}
    (ROOT / "data" / "catalog.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    cols = ["domain", "tier", "open_web_tier", "top_title", "max_libraries", "n_entries", "owner", "owner_type", "access_model", "category",
            "automated_access", "ai_tdm", "robots_ai", "bot_check", "automation_letter", "automation_spirit"]
    with open(ROOT / "data" / "catalog.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for p in platforms:
            w.writerow(p)
    from collections import Counter
    print("platforms:", len(platforms), dict(Counter(p["tier"] for p in platforms)))
    print("open-web:", dict(Counter(p["open_web_tier"] for p in platforms if p["open_web_tier"])))
    for k in ("owner_type", "access_model", "automation_letter", "automation_spirit"):
        print(k, dict(Counter(p[k] for p in platforms if p["tier"] not in ("local", "none"))))


if __name__ == "__main__":
    main()
