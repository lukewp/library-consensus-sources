# Method: library consensus as a sourcing heuristic

**Question.** Which research sources should a person or an agent know about, and how may each one be used?

**Idea.** University libraries already curate research sources for every discipline, and publish the lists. A source that many libraries recommend, across regions, has passed many independent professional judgements. Each source's own terms of use and robots.txt say what kind of use it accepts. Both are public, so the answer can be recomputed by anyone, at any time.

The pipeline has five steps. Each is a script in `scripts/`, uses only the Python standard library, and writes a file in `data/`.

## 1. Sample libraries — `data/sample.json`

The sampling frame is university libraries whose A–Z database list is public on Springshare LibGuides. LibGuides is the most widely used platform for these lists, and its list format is uniform, which makes the collection comparable and repeatable.

Candidates were found by web search, with regional quotas: North America, the UK and Ireland, the Netherlands, continental Europe, Oceania, East Asia, South and Southeast Asia, the Middle East and North Africa, sub-Saharan Africa, and Latin America and the Caribbean. Comprehensive research universities were preferred. Every candidate is kept in the file, with how it was found.

**Bias.** LibGuides adoption is highest in Anglophone countries, and many continental European and East Asian libraries keep their lists elsewhere. Regional quotas and the region count in the consensus rule (step 5) offset this, but don't remove it. `RESULTS.md` reports the regional mix.

## 2. Collect the lists — `scripts/collect_libguides.py`

For each library, the collector:

- reads `robots.txt` first, and skips the library if the A–Z page or the list endpoint is disallowed for its user agent or for `*`;
- records every AI agent the file names, and waits the stated crawl delay (at least 10 seconds) between requests;
- identifies itself honestly as an AI-assisted research collector with a link to this repo, and never imitates a browser;
- reads only the unfiltered list, page by page, the same way the page's own "load more" does. LibGuides' robots.txt disallows filtered A–Z views (subject, type, search), so subjects are not taken from the libraries (see step 3).

**On AI agents.** Springshare's standard robots.txt blocks several named AI agents (for example ChatGPT-User, GPTBot and Gemini-Deep-Research), and sets rules for everyone else under `*`. This collection followed the letter of those files. Its own agent is not named, so it applied the `*` rules. Some readers will hold that a block on named AI agents expresses an intent that covers all of them. `RESULTS.md` lists, for every library, which AI agents its robots.txt names, so the sample can be filtered on that basis. The same distinction drives the two automation readings in step 5.

## 3. Build the union — `scripts/build_union.py`, `scripts/tag_disciplines.py`

- **Titles are matched after normalization:** case, accents, punctuation, `&`, a leading "The", screen-reader text such as "opens in a new window", and vendor qualifiers like "(ProQuest)".
- **Each entry records:** how many libraries list it, in how many regions and countries, which platform domains the libraries link to, and how many libraries flag it as free or open access.
- **Proxy domains are dropped.** A library's own proxy or portal domain shows up for one library across very many titles, and is removed by that pattern.
- **Disciplines are tagged by keyword rules** over the title, the libraries' descriptions and their type labels. An entry can carry several. "multidisciplinary" is used when four or more match, or when the text says so.
- **Some links can't be read directly.** When every library links to a title through its own redirect, `scripts/resolve_links.py` asks one library's redirect where it points, without following it. It only does this for titles at least two libraries list, and only on paths robots.txt allows. LibGuides disallows `/go.php` and `/friendly.php`, so those are never requested.

## 4. Read terms and access — `scripts/fetch_terms.py`, `scripts/classify_terms.py`, owner classification

For every platform domain:

- **robots.txt:** the AI agents it names, split into agents that fetch on a person's behalf (ChatGPT-User, Claude-User, Perplexity-User, Gemini-Deep-Research) and crawlers that gather data (GPTBot, CCBot, Google-Extended, ClaudeBot and others), plus whether it lets us fetch the home page at all.
- **The TDM Reservation Protocol:** `/.well-known/tdmrep.json` and a `tdm-reservation` meta tag. This is how EU rights holders reserve text-and-data-mining rights under Article 4 of the DSM Directive.
- **The home page:** whether an honest request met a bot check, and which sign-in or subscription cues appear.
- **The terms page or pages linked from the home page,** and the sentences in them that mention automated access, scraping, crawling, robots, bulk or systematic downloading, text and data mining, or AI. If the home page links none, the usual paths (`/terms`, `/terms-of-use` and the like) are tried, where robots.txt allows.

A linked page counts as the domain's terms only when it is on the same registrable domain, and its URL or link text names it as terms, conditions of use, a licence or user agreement, a legal notice, a disclaimer or a copyright page. Another site's terms are recorded as `terms_offsite` and aren't read as governing the domain.

Rules then turn those sentences into readings:

- `automated_access`: prohibited / restricted / permitted / silent / unknown. A reading counts only when the sentence states an obligation: "may not", "must not", "shall not", "do not", "prohibited", "without permission" and the like.
- `ai_tdm`: one of
  - `prohibited`: no use of content with AI tools;
  - `training_prohibited`: no AI training or data mining;
  - `reserved`: text-and-data-mining rights reserved, including through TDMRep;
  - `permitted`, `silent` or `unknown`.

"Silent" means the terms were read and say nothing on the point. "Unknown" means they couldn't be read. Every reading keeps the sentence that decided it and the URL.

**Owner type and access model** come from a model's classification of each domain, using the titles and vendors the libraries gave, with a stated confidence:

- owner type: commercial, nonprofit, educational, government, intergovernmental, individual, or unknown;
- access model: free, free with account, freemium, subscription, institutional licence, pay per use, mixed, or unknown.

Libraries' own "free" and "open access" flags are kept alongside as an independent signal.

## 5. Rate — `scripts/rate.py`

**Consensus tier** of an entry, with N = the number of libraries collected:

| Tier | Rule |
|---|---|
| core | named by ≥ 25% of libraries, in ≥ 5 regions |
| common | named by ≥ 10% of libraries, in ≥ 3 regions |
| recognized | named by ≥ 3 libraries |
| local | otherwise |

A platform takes the best tier among its entries.

**Automation**, the use an agent may make of a platform:

| Rating | When |
|---|---|
| manual-only | terms prohibit automated access, or prohibit using content with AI tools; robots.txt blocks all bots for us; or the site charges per use |
| human-pace | terms prohibit AI training or data mining, or reserve TDM rights; automated access is restricted (rate limits, API only); robots.txt blocks named AI agents, or couldn't be read; a bot check answered an honest request; the terms couldn't be read; or access is by subscription, institutional licence, freemium, mixed or unknown |
| allowed | none of the above: the terms were read and permit or are silent on automated access, robots.txt was read and blocks no AI agent, and the site is free or free with an account |

There are two readings, and both are published:

- `automation_letter` holds a robots.txt block on named AI *user* agents to bind only those agents. Other agents get human-pace.
- `automation_spirit` holds such a block to bind every AI agent, which makes the site manual-only.

**What the ratings mean for an agent:**
- `allowed`: it may query and read.
- `human-pace`: it may read the pages a person would open for the task, one at a time, never crawling or exporting.
- `manual-only`: it suggests searches and the person runs them.

A ban on AI *training* leaves open what human-pace allows: reading the pages a person would open for a task. So it gives human-pace, not manual-only. A ban on *using content with AI tools* covers an agent reading for a person, so it gives manual-only.

**Review.** An independent reviewer checked the core and common tiers against the evidence. Its corrections are in `data/overrides.json`, each with its reason, and `rate.py` applies them. Platforms carry `corrected_on_review` where one applied.

These are readings of public text by stated rules. They are not legal advice, and a user's own agreement with a site governs.

## Re-running

```bash
python3 scripts/collect_libguides.py data/sample.json      # hours, at the crawl delay; resumable
python3 scripts/build_union.py && python3 scripts/tag_disciplines.py
python3 scripts/resolve_links.py --min-libraries 2
python3 scripts/make_domains.py
python3 scripts/fetch_terms.py                             # resumable
python3 scripts/classify_terms.py
# owner classification: data/owner/out-*.jsonl (see data/owner/README.md)
python3 scripts/rate.py && python3 scripts/report.py && python3 scripts/to_skill_catalog.py
```

Raw collections (`data/raw/`, `data/terms/raw/`) hold the libraries' own text and are not published. The scripts regenerate them.

## Limits

- **The sample:** one platform (LibGuides) and its adoption pattern, a point in time, and lists that include local and trial resources.
- **Matching** by normalized title merges editions and vendor versions of the same database, and can occasionally merge different works with the same name.
- **Terms readings** are pattern matches over sentences. They can miss clauses phrased unusually, or terms kept in PDFs and licence agreements that aren't linked from the home page. Licensed platforms' real terms are usually in the institution's licence, which isn't public.
- **Owner type and access model** are a model's classification from names, with confidence recorded. Low-confidence rows deserve checking.
- **Ratings are per domain.** A domain that hosts several services gets one rating, and its access model is taken from its best-known title. A university domain that hosts both free and membership resources is the typical case.
- **Bot checks.** Many large commercial platforms answer an honest automated request with a bot check, so their terms stay `unknown` and they rate human-pace by default. Reading those terms needs a person, or a fetcher those sites admit.
