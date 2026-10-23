# Brief: A library-consensus catalog of research sources, with access and terms

## Assumptions
- The sampling frame is university libraries whose A–Z database list runs on Springshare LibGuides. It is uniform, machine-readable and repeatable. Its Anglophone skew is disclosed and offset by regional quotas.
- Discipline tags come from classifying each union entry, not from the libraries' subject filters, because filtered A–Z views are disallowed by robots.txt.
- Terms are checked per platform or domain, not per database title: many titles share one vendor platform.
- The `automation` rating is a published rule applied to the recorded terms. It is a reading of terms, not legal advice.

## Request metadata
Requester: Luke Peterson
Delivery route: new public GitHub repo; research-agent-skill PR #1 (site catalog)
Render mode: report

## Deliverable contract
Type: retrieval (primary) + analytical (secondary: the consensus heuristic)
Primary artifact: a union dataset of library-recommended research sources, with consensus counts and per-platform access and terms fields, and the rebuilt `site-catalog.json`.
Complete means:
- every sampled library has a status (collected or excluded, with the reason);
- every union entry has a consensus count and a discipline tag;
- every platform or domain has an owner type, access model, paywall flag, automated-access and AI/text-and-data-mining clause readings (with the terms URL), and the robots AI-agent rules;
- the method is written down so anyone can re-run it.
Explicitly unavailable is acceptable for: terms pages that cannot be found or read (recorded as `unknown`, with the URL tried); libraries whose lists cannot be read (status and reason).

## Reader
Role: Luke, and anyone adopting the published heuristic (researchers, librarians, agent builders).
Decision faced: which research sites an agent should know about, and how it may use each one.
Span of action: the research skill's catalog and planning rules; public guidance for others.

## Key questions
1. Which research sources do university libraries recommend, and where is there consensus across libraries, regions and disciplines?
2. For each platform: who owns it (commercial, nonprofit, educational, government, intergovernmental), and how is it accessed (free, free with account, freemium, subscription, institutional, pay-per-use)?
3. What do each platform's terms and robots.txt say about automated access and AI or text-and-data-mining use?
4. What simple, repeatable rule turns those facts into catalog inclusion and an `automation` rating?

## Time window
As of: 2026-10-23
Window: current library lists and current terms, as fetched on 2026-10-23 to 2026-10-24.

## Success criteria
- The union and consensus counts can be recomputed from the committed raw data by one script.
- Each terms reading links to its source and can be challenged.
- The catalog update is traceable to the dataset.
