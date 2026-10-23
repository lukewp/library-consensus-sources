#!/usr/bin/env python3
"""classify_terms: turn the fetched terms evidence into readings, by published rules.

  python3 scripts/classify_terms.py    # reads data/terms/raw/*.json, writes data/terms/readings.json

Readings per domain (each with the sentence or signal that decided it):
  automated_access: prohibited | restricted | permitted | silent | unknown
  ai_tdm:           prohibited (no use of content with AI tools) | training_prohibited (no training or mining)
                    | reserved (TDM rights reserved, incl. TDMRep) | permitted | silent | unknown
  robots_ai:        blocks_all_bots | blocks_ai_user_agents | blocks_ai_crawlers | no_ai_rules | unknown
                    (user agents fetch on a person's behalf, e.g. ChatGPT-User; crawlers gather data, e.g. GPTBot)
  bot_check:        true when the site answered our honest request with a bot challenge or refusal
  paywall_cues:     the sign-in and subscription words seen on the home page
"silent" means terms were read and say nothing on the point; "unknown" means they could not be read.
These are readings of text by pattern, to be spot-checked; they are not legal advice.
"""
import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_union import registrable  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "terms" / "raw"

NEG = r"(may not|must not|shall not|do not|are not (permitted|allowed|authori[sz]ed)|is not (permitted|allowed)|not (permitted|allowed|authori[sz]ed) to|agree not to|you (shall|will|may|must) not|prohibit\w*|forbid\w*|strictly prohibited|unauthori[sz]ed|without (the )?(express |prior )?(written )?(permission|consent|authori[sz]ation)|no (person|user|one|party) (may|shall))"
AUTO = r"(robot|spider|scrap\w*|crawl\w*|automat\w* (means|access|tools?|process|systems?|queries|retrieval|download\w*)|bots?\b|harvest\w*|bulk download\w*|systematic\w* (download|retriev|cop)\w*|data[- ]extraction)"
AI = r"(artificial intelligence|\bai\b|machine[- ]learning|large language|\bllms?\b|generative|train\w* (a |any |an )?(model|ai|algorithm|system)|text[- ]and[- ]data[- ]mining|text[- ]mining|data[- ]mining|\btdm\b)"
PERMIT = r"(may|are permitted to|is permitted|are allowed|allowed to|licen[cs]e[sd]? to|grant\w*)"
AI_USE = r"(\b(use|using|input|upload|submit|process|combin\w*)\b.{0,60}(artificial intelligence|\bai\b|machine[- ]learning|large language|\bllms?\b)\s*(tools?|systems?|agents?|services?|models?|applications?|technolog\w*)|(ai|artificial intelligence)\s*(agents?|bots?|crawlers?|tools?)\b.{0,40}(access|scrap|crawl|retriev|read))"
TERMS_LIKE = re.compile(r"(\bterms\b|terms[-_]?(of|and)[-_]?(use|service|conditions)|conditions[-_ ]of[-_ ]use|\btos\b|user[-_ ]agreement|licen[cs]e[-_ ]agreement|legal[-_ ]notice|disclaimer|copyright|acceptable[-_ ]use|nutzungsbedingungen|gebruiksvoorwaarden|condiciones[-_ ]de[-_ ]uso|mentions[-_ ]l[ée]gales|conditions[-_ ]g[ée]n[ée]rales|/legal\b)", re.I)
RESERVE = r"(reserv\w*.{0,80}(text and data mining|data mining|tdm|article 4)|(text and data mining|data mining|tdm).{0,80}reserv\w*|opt[- ]?out.{0,60}(mining|tdm))"
# Agents that fetch on a person's behalf, as opposed to crawlers that gather training or index data.
USER_AGENTS = ("chatgpt-user", "claude-user", "perplexity-user", "gemini-deep-research", "mistralai-user", "duckassistbot", "oai-searchbot", "claude-searchbot")
RATE = r"(rate limit|reasonable (number|volume|amount)|excessive|unreasonable load|burden|api (key|terms)|only through (the|our) api)"


# Privacy-notice language about automated decisions or tracking is not a use restriction.
PRIVACY = re.compile(r"(decision[- ]making|profiling|personal data|data subject|cookies?\b|ip address|browser characteristics|tracking technolog)", re.I)


def menu_like(s):
    """Navigation text scraped as one long 'sentence': mostly capitalized words, few verbs."""
    words = re.findall(r"[A-Za-z][\w'-]*", s)
    if len(words) < 12:
        return False
    caps = sum(1 for w in words if w[0].isupper())
    return caps / len(words) > 0.5


def has(rx, s):
    return re.search(rx, s, re.I) is not None


def near(a, b, s, gap=120):
    return re.search(f"{a}.{{0,{gap}}}{b}|{b}.{{0,{gap}}}{a}", s, re.I) is not None


def read(rec):
    out = {"domain": rec["domain"], "fetch_status": rec.get("status")}
    rob = rec.get("robots") or {}
    named = rob.get("ai_agents_named") or {}
    blocked = {a for a, v in named.items() if v == "disallow_all"}
    if not rob:
        out["robots_ai"] = "unknown"
    elif rob.get("root_allowed_for_us") is False:
        out["robots_ai"] = "blocks_all_bots"
    elif any(any(u in a for u in USER_AGENTS) for a in blocked):
        out["robots_ai"] = "blocks_ai_user_agents"
    elif blocked:
        out["robots_ai"] = "blocks_ai_crawlers"
    else:
        out["robots_ai"] = "no_ai_rules"
    out["robots_ai_agents"] = sorted(named)
    out["robots_root_allowed_for_us"] = rob.get("root_allowed_for_us")
    home = rec.get("home") or {}
    out["bot_check"] = bool(home.get("bot_check")) or any(t.get("bot_check") for t in rec.get("terms", []))
    out["paywall_cues"] = home.get("paywall_cues", [])
    out["home_title"] = home.get("title")
    clauses, urls = [], []
    offsite = []
    for t in rec.get("terms", []):
        if not (t.get("http_status") == 200 and not t.get("bot_check") and t.get("chars", 0) > 400):
            continue
        host = urllib.parse.urlsplit(t["url"]).netloc
        if registrable(host) != rec["domain"]:
            offsite.append(t["url"])  # another site's terms: not read as governing this domain
            continue
        if not (TERMS_LIKE.search(t["url"]) or TERMS_LIKE.search(t.get("label") or "")):
            continue  # a linked page that is not a terms page (news, statistics, a topic page)
        urls.append(t["url"])
        clauses += [c for c in t.get("clauses", []) if not menu_like(c) and not PRIVACY.search(c)]
    if offsite:
        out["terms_offsite"] = offsite
    out["terms_urls"] = urls
    tdm_signal = None
    if rec.get("tdmrep_json"):
        tdm_signal = f"TDMRep file: https://{rec['domain']}/.well-known/tdmrep.json"
    elif home.get("tdm_meta"):
        tdm_signal = f"tdm-reservation meta tag on {home.get('final_url')}: {home.get('tdm_meta')}"
    if not urls:
        out["automated_access"] = "unknown"
        out["ai_tdm"] = "reserved" if tdm_signal else "unknown"
        out["evidence"] = {"ai_tdm": tdm_signal} if tdm_signal else {}
        return out
    ev = {}
    auto_neg = [c for c in clauses if has(AUTO, c) and near(NEG, AUTO, c)]
    auto_rate = [c for c in clauses if has(AUTO, c) and has(RATE, c)]
    auto_perm = [c for c in clauses if has(AUTO, c) and near(PERMIT, AUTO, c) and not has(NEG, c)]
    if auto_neg:
        out["automated_access"], ev["automated_access"] = "prohibited", auto_neg[0][:400]
    elif auto_rate:
        out["automated_access"], ev["automated_access"] = "restricted", auto_rate[0][:400]
    elif auto_perm:
        out["automated_access"], ev["automated_access"] = "permitted", auto_perm[0][:400]
    else:
        out["automated_access"] = "silent"
    ai_use = [c for c in clauses if has(AI_USE, c) and has(NEG, c)]
    ai_neg = [c for c in clauses if has(AI, c) and near(NEG, AI, c)]
    ai_res = [c for c in clauses if has(RESERVE, c)]
    ai_perm = [c for c in clauses if has(AI, c) and near(PERMIT, AI, c) and not has(NEG, c)]
    if ai_use:
        out["ai_tdm"], ev["ai_tdm"] = "prohibited", ai_use[0][:400]
    elif ai_neg:
        out["ai_tdm"], ev["ai_tdm"] = "training_prohibited", ai_neg[0][:400]
    elif ai_res or tdm_signal:
        out["ai_tdm"], ev["ai_tdm"] = "reserved", (ai_res[0][:400] if ai_res else tdm_signal)
    elif ai_perm:
        out["ai_tdm"], ev["ai_tdm"] = "permitted", ai_perm[0][:400]
    else:
        out["ai_tdm"] = "silent"
    out["evidence"] = ev
    return out


def main():
    readings = [read(json.loads(f.read_text())) for f in sorted(RAW.glob("*.json"))]
    (ROOT / "data" / "terms" / "readings.json").write_text(json.dumps({"n": len(readings), "readings": readings}, indent=1, ensure_ascii=False))
    from collections import Counter
    for k in ("automated_access", "ai_tdm", "robots_ai"):
        print(k, dict(Counter(r[k] for r in readings)))
    print("bot_check", sum(r["bot_check"] for r in readings))


if __name__ == "__main__":
    main()
