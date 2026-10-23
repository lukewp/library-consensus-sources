#!/usr/bin/env python3
"""report: write RESULTS.md from the data files (no network)."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def table(rows, head):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def main():
    libs = json.loads((ROOT / "data" / "libraries.json").read_text())["libraries"]
    cat = json.loads((ROOT / "data" / "catalog.json").read_text())
    union = json.loads((ROOT / "data" / "union.json").read_text())
    N = cat["n_libraries"]
    ok = [l for l in libs if str(l["status"]).startswith(("collected", "partial")) and l["items"]]
    plats = cat["platforms"]
    ranked = [p for p in plats if p["tier"] in ("core", "common")]
    ents = cat["entries"]
    md = ["# Results", "", f"Collected 2026-10-23. {N} libraries in {len({l['country'] for l in ok})} countries; "
          f"{union['n_entries']:,} distinct titles; {len(plats):,} platform domains.", ""]
    md += ["## Sample", "", table(sorted(Counter(l["region"] for l in ok).items(), key=lambda x: -x[1]), ["Region", "Libraries"]), ""]
    excluded = [l for l in libs if l not in ok]
    def why(l):
        st = str(l["status"])
        if st.startswith(("collected", "partial")):
            return "A-Z list empty on LibGuides"
        if "no site id" in st:
            return "A-Z list not on LibGuides"
        if "CERTIFICATE" in st:
            return "TLS certificate does not match the host"
        return st[:60]
    md += [f"Not collected ({len(excluded)}): " + "; ".join(f"{l['university']} ({why(l)})" for l in excluded) + ".", "",
           "Partial lists (a few items short of the reported count, usually duplicate entries) were kept.", ""]
    named = Counter(a for l in ok for a in l.get("robots_ai_agents_named", []))
    md += [f"robots.txt of the libraries' own list sites: {sum(1 for l in ok if l.get('robots_ai_agents_named'))} of {len(ok)} name at least one AI agent. "
           "Most often named: " + ", ".join(f"{a} ({c})" for a, c in named.most_common(10)) + ".", ""]
    tiers = Counter(e["tier"] for e in ents)
    md += ["## Consensus", "", table([(t, tiers.get(t, 0), Counter(p["tier"] for p in plats).get(t, 0)) for t in ("core", "common", "recognized", "local")],
                                     ["Tier", "Titles", "Platforms"]), ""]
    top = sorted(ents, key=lambda e: (-e["n_libraries"], -e["n_regions"]))[:40]
    md += ["### The 40 most widely listed titles", "", table([(e["title"], e["n_libraries"], f"{e['share']:.0%}", e["n_regions"], e["domain"] or "") for e in top],
                                                             ["Title", "Libraries", "Share", "Regions", "Domain"]), ""]
    md += ["## Platforms in the core and common tiers", ""]
    for k in ("owner_type", "access_model", "automated_access", "ai_tdm", "robots_ai", "automation_letter", "automation_spirit"):
        c = Counter(p[k] for p in ranked)
        md += [f"**{k}**: " + ", ".join(f"{v} {n}" for v, n in c.most_common()), ""]
    md += [f"Bot check answered an honest request: {sum(1 for p in ranked if p['bot_check'])} of {len(ranked)}.", ""]
    cross = Counter((p["owner_type"], p["automation_spirit"]) for p in ranked)
    owners = ["commercial", "nonprofit", "educational", "government", "intergovernmental", "individual", "unknown"]
    md += ["### Owner type × automation (spirit reading)", "",
           table([(o, cross.get((o, "allowed"), 0), cross.get((o, "human-pace"), 0), cross.get((o, "manual-only"), 0)) for o in owners],
                 ["Owner type", "allowed", "human-pace", "manual-only"]), ""]
    md += ["### Core and common platforms", "",
           table([(p["domain"], p["top_title"][:48], p["max_libraries"], p["owner_type"], p["access_model"], p["automated_access"], p["ai_tdm"],
                   p["robots_ai"], p["automation_letter"], p["automation_spirit"]) for p in ranked],
                 ["Domain", "Top title", "Libraries", "Owner", "Access", "Automated", "AI/TDM", "robots AI", "Letter", "Spirit"]), ""]
    (ROOT / "RESULTS.md").write_text("\n".join(md) + "\n")
    print("RESULTS.md written:", len(ranked), "ranked platforms")


if __name__ == "__main__":
    main()
