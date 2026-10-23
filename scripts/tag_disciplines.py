#!/usr/bin/env python3
"""tag_disciplines: tag each union entry with broad disciplines and a resource type, by keyword rules.

  python3 scripts/tag_disciplines.py    # updates data/union.json in place (adds "disciplines", "resource_type")

Rules read the title, the libraries' descriptions, and the library-supplied type labels. An entry can
have several disciplines; "multidisciplinary" is used when four or more match or the text says so.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = {
    "arts_humanities": r"histor|literat|philosoph|relig|theolog|classic|art\b|arts\b|music|film|theatre|theater|languag|linguist|poetry|archaeolog|humanit|medieval|renaissance|cultur|bible|manuscript",
    "social_sciences": r"sociolog|psycholog|politic|anthropolog|educat|geograph|communicat|social (work|science)|criminolog|gender|demograph|international relations|public policy|ethnic",
    "business_economics": r"business|econom|financ|market|compan|industr|account|management|trade\b|invest|stock|bank|tax\b|commerce",
    "law": r"\blaw\b|legal|legislat|statut|case law|court|jurisprud|treat(y|ies)|regulat|westlaw|lexis|hein",
    "health_medicine": r"medic|nurs|health|clinic|pharma|drug|dentist|veterin|patholog|disease|psychiatr|biomed|cochrane|pubmed|embase|cinahl|anatom",
    "life_sciences": r"biolog|agricult|ecolog|environment|zoolog|botan|genetic|genom|food science|forestr|marine|fisher|wildlife|life science",
    "physical_sciences_math": r"chemi|physic|mathemat|geolog|astronom|earth science|statistic(s|al) (science|methods)|materials science|crystal|spectr",
    "engineering_technology": r"engineer|comput|ieee|electr|mechanic|civil|software|technolog|patent|standards?\b|architect|aerospace|robot",
    "news_media": r"news|newspaper|magazine|periodical|press\b|broadcast|media|journalism|television|radio",
    "government_official": r"government|parliament|congress|official publication|federal|ministry|legislative|census|united nations|\bun\b|world bank|oecd|imf\b|eurostat|foreign relations",
    "data_statistics": r"\bdata\b|dataset|statistic|indicator|survey|census|microdata|time series",
    "reference": r"dictionar|encyclop|handbook|biograph|directory|thesaurus|atlas|almanac|reference",
}
TYPE = [
    ("news", r"news|newspaper|magazine"),
    ("data_statistics", r"\bdata\b|dataset|statistic"),
    ("legal", r"\blaw\b|legal|case law|statut"),
    ("ebooks", r"e-?books?\b"),
    ("primary_sources", r"primary source|archive|manuscript|historical (newspaper|record)"),
    ("index_abstract", r"index|abstract|bibliograph|citation"),
    ("reference", r"dictionar|encyclop|handbook|reference"),
    ("journals_articles", r"journal|article|full[- ]text"),
    ("media", r"video|audio|music|stream|image|film"),
]


def main():
    path = ROOT / "data" / "union.json"
    u = json.loads(path.read_text())
    dpath = ROOT / "data" / "descriptions.local.json"
    desc = json.loads(dpath.read_text()) if dpath.exists() else {}
    for e in u["entries"]:
        text = " ".join([e["title"], desc.get(e["key"], ""), " ".join(e.get("types", {})), " ".join(e.get("title_variants", [])[:2])]).lower()
        tags = [d for d, rx in D.items() if re.search(rx, text)]
        if re.search(r"multidisciplin|interdisciplin|all subjects|wide range of (subjects|disciplines)", text) or len(tags) >= 4:
            tags = ["multidisciplinary"] + tags
        e["disciplines"] = tags or ["unclassified"]
        typ = " ".join(e.get("types", {})).lower() + " " + text
        e["resource_type"] = next((t for t, rx in TYPE if re.search(rx, typ)), "other")
    path.write_text(json.dumps(u, indent=1, ensure_ascii=False))
    from collections import Counter
    c = Counter(t for e in u["entries"] if e["n_libraries"] >= 3 for t in e["disciplines"])
    print("disciplines among entries named by 3+ libraries:", dict(c.most_common()))


if __name__ == "__main__":
    main()
