# Inventory

This run followed the strategic-research method (v0.4.0), with one adaptation. The collection was large and structured (130 library lists, 4,469 platform domains), so its tasks ran as scripts on the requester's machine rather than one sub-agent per task. Discovery and classification ran as sub-agents. The scripts and their outputs are the corpus.

| Stage | Output |
|---|---|
| P0 Intake | `request.md`, `brief.md` |
| 1 Plan | candidates found by four regional discovery sub-agents (web search) → `../../data/sample.json` (130 candidates) |
| 2 Collect | `scripts/collect_libguides.py` → 119 lists collected (11 not: see `RESULTS.md`); `scripts/resolve_links.py` → 988 titles' platforms resolved; `scripts/fetch_terms.py` → 4,464 domains' robots.txt, home page and terms |
| 3 Inventory | `data/union.json` (31,338 titles), `data/domains.json`, `data/terms/readings.json`, `data/owner/out-*.jsonl` |
| 5 Analyze / 6 Synthesize | `scripts/rate.py` → `data/catalog.json`, `data/catalog.csv`; `RESULTS.md` |
| 8 Review | independent reviewer sub-agent over the 237 core and common platforms → `data/overrides.json` (corrections, each with a reason) |

## Retrieval status

| Item | Status |
|---|---|
| Union list with consensus counts | delivered: `data/union.json` |
| Platform owner type and access model | delivered for all 4,469 domains (model classification, with confidence) |
| Terms readings | read for 1,340 domains. The rest are `unknown`: home page refused or bot check (1,032), no terms link or page found (1,361), unreachable (494), robots.txt disallows the home page (126), or a terms page that could not be read |
| robots.txt AI rules | read for 3,970 domains |
| Discipline tags | delivered (keyword rules) |
| Skill catalog | delivered: `data/site-catalog.json` (237 consensus platforms + 43 curated) |

## Gaps

- **Thin regions.** Continental Europe (7 libraries) and Latin America (6) are thin: most libraries there don't run their A–Z list on LibGuides.
- **Unread terms for core platforms.** The terms of many core platforms are behind bot checks (Elsevier, Wiley, ACM and others) and stay `unknown`. Their rating falls to human-pace by rule. A follow-up pass with a different, honest fetcher could read them.
- **No library subject tags.** LibGuides' robots.txt disallows filtered A–Z views, so no library subject tags were collected. The disciplines are inferred.
