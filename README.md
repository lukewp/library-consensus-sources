# Library-consensus research sources

**Which research sources do university libraries agree on, and how may an agent use each one?**

This repo builds the answer from public data, and can rebuild it at any time:

1. **Collect** the public A–Z database lists of university libraries worldwide (Springshare LibGuides), politely and under each site's robots.txt.
2. **Union** the lists and count how many libraries, and how many regions, recommend each title. That count is the consensus.
3. **Read** each platform's robots.txt, TDM-reservation signals and terms of use. Classify its owner type (commercial, nonprofit, educational, government, intergovernmental) and its access model (free, account, subscription, institutional, pay per use).
4. **Add the open web.** A–Z lists miss Wikipedia, wire services, newspapers, statistics portals and platforms. A separate **open-web tier** measures them by:
   - the references in the 200 most-read articles of each of 20 Wikipedia language editions;
   - the news, free-web, data and government guides of the same libraries;
   - a seed list of widely used general sources, so none is left unassessed.
5. **Rate** each platform: a consensus tier (core / common / recognized / local), and an automation rating for AI agents (allowed / human-pace / manual-only), under two readings of robots.txt, the letter and the spirit.

- **`METHOD.md`:** the heuristic, step by step, and its limits.
- **`RESULTS.md`:** the numbers from the current run.
- **`data/catalog.csv`:** one row per platform, with its library tier and open-web tier.
- **`data/openweb.json`:** the open-web signals per domain: Wikipedia languages and articles citing it, guide libraries and regions, seed group.
- **`data/catalog.json`:** the same, with each platform's titles, terms URLs and the sentences each reading rests on.
- **`data/site-catalog.json`:** the core, common and open-web platforms in the format the [strategic-research skill](https://github.com/lukewp/research-agent-skill) reads.

## Using the ratings

| Rating | An agent may |
|---|---|
| allowed | query and read the site |
| human-pace | read the pages a person would open for the task, one at a time; never crawl, bulk-download or export |
| manual-only | suggest searches; the person runs them |

These are readings of public text by published rules, not legal advice. A user's own licence or agreement with a platform governs, and institutional licences, which are rarely public, often say more than a site's public terms.

## Re-running

See `METHOD.md` § Re-running. The scripts use only the Python 3 standard library. The collection waits each library's crawl delay, so a full run takes a few hours. Raw collections are not committed: they hold each library's own list text.

## License

Code is MIT-licensed. Data and documentation are CC BY 4.0. See `LICENSE`.

## Provenance

Built on 2026-10-23 by Luke Peterson with Claude (Anthropic), as a research run of the strategic-research skill. The run's brief and request are in `research/`.
