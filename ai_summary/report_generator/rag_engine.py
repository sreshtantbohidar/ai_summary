"""
RAG Engine v3 — chunked processing for large datasets, direct enumeration output.
"""

import json
import time
import textwrap
import re
import math
import requests as req_lib

from config import (
    ES_HOST, ES_PORT, ES_SCHEME, ES_USER, ES_PASS, ES_VERIFY,
    OLLAMA_URL, EMBED_MODEL, LLM_MODEL,
    VECTOR_INDEX, MAX_CONTEXT_CHARS, TOP_K_RESULTS, MAX_SOURCES_IN_REPORT,
    MODES, logger,
)

# ── Elasticsearch client ──────────────────────────────────────────────

def get_es():
    from elasticsearch import Elasticsearch
    return Elasticsearch(
        [{"host": ES_HOST, "port": ES_PORT, "scheme": ES_SCHEME}],
        basic_auth=(ES_USER, ES_PASS),
        verify_certs=ES_VERIFY,
        ssl_show_warn=False,
    )


# ── Ollama helpers ─────────────────────────────────────────────────────

def embed_query(text: str) -> list:
    """Embed a query string using Ollama nomic-embed-text."""
    resp = req_lib.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]


def call_llm(prompt: str, max_tokens: int = 4096) -> str:
    """Call Ollama /api/generate and return the generated text.
    Handles both single JSON response and NDJSON streaming fallback."""
    try:
        resp = req_lib.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": max_tokens,
                },
            },
            timeout=900,
        )
        resp.raise_for_status()
        content = resp.text.strip()

        # Try standard single JSON first
        try:
            return resp.json()["response"]
        except Exception:
            pass

        # Fallback: NDJSON — each line is a JSON object with a "response" field
        # Ollama sometimes sends NDJSON even with stream:false for large outputs
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        response_parts = []
        for line in reversed(lines):
            try:
                chunk = json.loads(line)
                if "response" in chunk:
                    response_parts.insert(0, chunk["response"])
            except json.JSONDecodeError:
                continue

        if response_parts:
            full = "".join(response_parts)
            logger.info(f"LLM response assembled from {len(response_parts)} NDJSON chunks, {len(full)} chars")
            return full

        # Last resort: try to find "response" key in first line
        logger.warning(f"Could not parse Ollama response, returning raw content (first 200 chars): {content[:200]}")
        return content or "Error: LLM returned empty response."

    except req_lib.exceptions.Timeout:
        raise RuntimeError(f"Ollama LLM request timed out after 900s. The model ({LLM_MODEL}) may be overloaded or the prompt too long.")
    except req_lib.exceptions.ConnectionError:
        raise RuntimeError(f"Cannot connect to Ollama at {OLLAMA_URL}. Is it running?")
    except Exception as e:
        raise RuntimeError(f"LLM call failed: {str(e)}")



# ── Mode-specific system prompts ──────────────────────────────────────

def get_mode_prompt(mode: str) -> str:
    """Return the system prompt for the given report mode."""
    prompts = {
        "answer": textwrap.dedent("""\
            You are an expert analyst. Answer the user's question using ONLY the provided document passages and aggregation data.
            Rules:
            - Be factual and precise. Cite specific passages like [Source 1], [Source 2].
            - If the documents don't contain enough information, say so clearly.
            - If aggregation data is provided (e.g., a list of all distinct values), you MUST include the COMPLETE list of all values in your report. Do NOT summarize or truncate the list. Every single value must be listed.
            - For "list all X" queries, your primary output should be the complete enumeration from the aggregation data.
            - Organize your answer with clear sections: Executive Summary, Complete List, Key Findings, Detailed Analysis.
            - Use bullet points for the complete list of values.
            - Include a "Sources Cited" section at the end listing which passages support your answer.
            - If data completeness warnings are provided, you MUST mention them in your report.
            - Write in a professional, clear tone. Avoid speculation."""),

        "analyze": textwrap.dedent("""\
            You are an expert analyst performing deep thematic analysis.
            Rules:
            - Identify key themes, patterns, and relationships across the provided passages.
            - Analyze underlying assumptions, strengths/weaknesses of arguments.
            - Compare and contrast different perspectives found in the documents.
            - Structure your report: Overview, Theme Analysis, Patterns & Relationships, Critical Assessment.
            - Use specific examples from the passages with citations like [Source 1].
            - Highlight any contradictions or gaps in the information.
            - If data completeness warnings are provided, you MUST mention them.
            - Write in an analytical, objective tone."""),

        "predict": textwrap.dedent("""\
            You are a strategic analyst making predictions based on the provided documents.
            Rules:
            - Clearly distinguish between what the documents state directly and your extrapolations.
            - Identify current trends and project them forward.
            - Develop multiple scenarios: best case, most likely case, worst case.
            - Consider potential risks, opportunities, and implications.
            - Structure your report: Current State, Trend Analysis, Scenarios, Recommendations.
            - Cite supporting evidence from passages like [Source 1] for each prediction.
            - If data completeness warnings are provided, you MUST mention them.
            - Write in a strategic, forward-looking tone. Be honest about uncertainty."""),

        "summarize": textwrap.dedent("""\
            You are an expert summarizer. Create a comprehensive summary from the provided documents.
            Rules:
            - Cover all main ideas, key points, and important details.
            - Preserve the logical structure and flow of the original content.
            - Include specific data points, names, dates where available.
            - Structure your report: Executive Summary, Main Points, Key Details, Conclusions.
            - Be comprehensive but concise. Every sentence should add value.
            - Cite sources like [Source 1] for key claims.
            - If data completeness warnings are provided, you MUST mention them.
            - Write in a clear, neutral, professional tone."""),
    }
    return prompts.get(mode, prompts["answer"])


# ── Intent classification ──────────────────────────────────────────────
# Comprehensive keyword-based intent detection for routing queries to
# the optimal processing pipeline.

# Intent types:
#   enumeration   → "list all X", "show all Y" → ES aggregation only, direct output
#   lookup        → "what is X", "find Y"     → kNN + single LLM call
#   analytical    → "analyze", "summarize"    → kNN + chunked LLM
#   comparison    → "compare X and Y"         → kNN + chunked LLM
#   trend         → "trends in X", "over time"→ kNN + chunked LLM
#   prediction    → "predict", "will X"        → kNN + chunked LLM
#   count         → "how many X", "count of"   → ES aggregation only, direct output
#   search        → "find X", "search for"     → kNN + single LLM call
#   detail        → "details of X", "info on"  → kNN + single LLM call
#   summary       → "summarize X", "overview"  → kNN + chunked LLM
#   distribution  → "distribution of X"        → ES aggregation + single LLM
#   top_n         → "top X", "most common"     → ES aggregation only, direct output
#   recent        → "recent X", "latest"       → kNN (sorted by date) + single LLM
#   related       → "related to X", "similar"  → kNN + single LLM
#   unknown       → fallback                   → kNN + single LLM

INTENT_PATTERNS = {
    "enumeration": [
        r"list\s+(all|every|the)",
        r"show\s+(all|every)",
        r"display\s+(all|every)",
        r"enumerate",
        r"complete\s+list",
        r"full\s+list",
        r"all\s+(the\s+)?\w+s",
        r"every\s+\w+",
        r"names?\s+of\s+(all|the)",
        r"types?\s+of",
        r"distinct\s+\w+s",
        r"unique\s+\w+s",
        r"give\s+me\s+(a\s+)?list",
        r"tell\s+me\s+(all|every)",
        r"what\s+(are|were|is)\s+(the|all|every)",
        r"which\s+\w+s",
        r"where\s+(are|were|is)\s+(the|all)",
        r"who\s+(are|were|is)\s+(the|all)",
        r"get\s+(all|every|the)",
        r"fetch\s+(all|every)",
        r"pull\s+(all|every)",
        r"dump\s+(all|every)",
        r"export\s+(all|every)",
    ],
    "count": [
        r"how\s+many",
        r"count\s+of",
        r"number\s+of",
        r"total\s+(number|count)",
        r"what\s+(is|was|are)\s+the\s+(count|number|total)",
        r"quantity\s+of",
        r"amount\s+of",
        r"size\s+of",
        r"how\s+much",
    ],
    "top_n": [
        r"top\s+\d+",
        r"most\s+(common|frequent|popular|used)",
        r"least\s+(common|frequent|popular|used)",
        r"highest\s+\w+",
        r"lowest\s+\w+",
        r"best\s+\w+",
        r"worst\s+\w+",
        r"largest\s+\w+",
        r"smallest\s+\w+",
        r"maximum\s+\w+",
        r"minimum\s+\w+",
        r"rank(?:ed|ing)?\s+(of|by|for)",
        r"first\s+\d+",
        r"last\s+\d+",
    ],
    "distribution": [
        r"distribution\s+of",
        r"breakdown\s+(of|by)",
        r"split\s+(of|by)",
        r"proportion\s+of",
        r"percentage\s+of",
        r"ratio\s+of",
        r"share\s+of",
        r"composition\s+of",
        r"spread\s+of",
        r"frequency\s+of",
        r"histogram\s+of",
        r"by\s+(category|type|group|class)",
        r"grouped\s+by",
        r"categorized\s+by",
        r"segmented\s+by",
    ],
    "analytical": [
        r"analyz[ei]",
        r"analysis\s+of",
        r"examin[ei]",
        r"investigat[ei]",
        r"explor[ei]",
        r"stud[yi]",
        r"review\s+(of|the)",
        r"assess(?:ment)?\s+of",
        r"evaluat[ei]",
        r"inspect[ei]",
        r"scrutin[yi]",
        r"survey\s+of",
        r"research\s+(on|about|into)",
        r"deep\s+dive\s+into",
        r"look\s+into",
        r"dig\s+into",
        r"break\s+down",
        r"make\s+sense\s+of",
        r"understand\s+(the|how|why)",
        r"interpret(?:ation)?\s+of",
    ],
    "comparison": [
        r"compar[ei]",
        r"versus",
        r"vs\.?",
        r"difference\s+between",
        r"contrast(?:ing)?",
        r"(dis)?similarit(?:y|ies)\s+between",
        r"better\s+than",
        r"worse\s+than",
        r"(more|less)\s+than",
        r"as\s+(compared|opposed)\s+to",
        r"in\s+comparison\s+(to|with)",
        r"relative\s+to",
        r"against",
        r"benchmark(?:ing)?\s+(of|against)",
        r"compet[ei]",
        r"match(?:ing)?\s+(up|against)",
    ],
    "trend": [
        r"trend(?:s|ing)?\s+(in|of|for|over)",
        r"over\s+time",
        r"(time\s+)?series",
        r"histor(?:y|ical|ic)\s+(of|data|trend)",
        r"pattern\s+(in|of|over)",
        r"evolution\s+of",
        r"development\s+of",
        r"progression\s+of",
        r"growth\s+(of|in|over)",
        r"decline\s+(of|in|over)",
        r"change\s+(in|over|of)",
        r"shift\s+(in|of|toward)",
        r"movement\s+(in|of|toward)",
        r"trajector(?:y|ies)\s+of",
        r"seasonal(?:ity)?\s+(in|of)",
        r"cycl(?:e|ical)\s+(in|of)",
        r"upward\s+trend",
        r"downward\s+trend",
        r"rising\s+\w+",
        r"falling\s+\w+",
        r"increas(?:e|ing)\s+\w+",
        r"decreas(?:e|ing)\s+\w+",
    ],
    "prediction": [
        r"predict(?:ion|ed|ing)?\s+(of|for)",
        r"forecast(?:ing)?\s+(of|for)",
        r"project(?:ed|ion|ing)?\s+(of|for)",
        r"futur[ei]\s+(of|for|trend)",
        r"will\s+\w+",
        r"going\s+to\s+\w+",
        r"expect(?:ed|ation)?\s+(of|for)",
        r"outlook\s+(of|for)",
        r"prospect(?:s)?\s+(of|for)",
        r"scenar(?:io|ios)\s+(of|for)",
        r"what\s+(will|would|might|could)\s+happen",
        r"what\s+(is|are)\s+(the\s+)?(?:future|next|upcoming)",
        r"plan(?:ning|ned|s)?\s+(for|of)",
        r"road\s*map\s+(for|of)",
        r"outlook",
    ],
    "lookup": [
        r"what\s+(is|are|was|were)",
        r"who\s+(is|are|was|were)",
        r"where\s+(is|are|was|were)",
        r"when\s+(is|are|was|were|did)",
        r"why\s+(is|are|was|were|did|does)",
        r"how\s+(is|are|was|were|did|does|do)",
        r"define",
        r"definition\s+of",
        r"meaning\s+of",
        r"explain",
        r"description\s+of",
        r"tell\s+me\s+(about|what|who|where|when|why|how)",
        r"describe",
        r"elaborate\s+on",
        r"clarif(?:y|ication)\s+(of|on|about)",
        r"identif(?:y|ication)\s+(of|for)",
        r"which\s+\w+",
    ],
    "search": [
        r"find\s+(all|the|any|every|a|an)?",
        r"search\s+(for|in|through)",
        r"look\s+(for|up|at)",
        r"locate",
        r"discover",
        r"retrieve",
        r"query\s+(for|about|on)",
        r"filter\s+(by|for|on)",
        r"fetch\s+(the|all|any)",
        r"get\s+(the|all|any|me)",
        r"pull\s+(the|all|any)",
        r"show\s+(me|the)",
        r"give\s+(me|the)",
    ],
    "detail": [
        r"detail(?:s|ed)?\s+(of|on|about|for)",
        r"information\s+(on|about|for)",
        r"info\s+(on|about|for)",
        r"data\s+(on|about|for)",
        r"record(?:s)?\s+(of|for|about|on)",
        r"specific(?:s)?\s+(of|about|on|for)",
        r"particular(?:s)?\s+(of|about|for)",
        r"in\s+detail",
        r"in\s+depth",
        r"comprehensive\s+(view|report|analysis|detail)",
        r"full\s+(detail|information|report|data)",
        r"complete\s+(detail|information|report|data)",
        r"thorough\s+(analysis|review|examination)",
        r"extensive\s+(analysis|review|report)",
    ],
    "summary": [
        r"summar(?:y|ize|ise|ization|isation)",
        r"overview\s+(of|on|for|about)",
        r"brief\s+(of|on|about|for|summary)",
        r"outline\s+(of|for)",
        r"recap\s+(of|on)",
        r"digest\s+(of|on)",
        r"synopsis\s+(of|for)",
        r"abstract\s+(of|for)",
        r"high[\s-]?lights?\s+(of|from|for)",
        r"key\s+points?\s+(of|from|for|about)",
        r"main\s+points?\s+(of|from|for|about)",
        r"takeaways?\s+(from|of|for)",
        r"tl;dr",
        r"in\s+(a\s+)?nutshell",
        r"at\s+a\s+glance",
        r"quick\s+(look|summary|overview|review)",
        r"short\s+(summary|overview|version|brief)",
    ],
    "recent": [
        r"recent(?:ly)?\s+\w+",
        r"latest\s+\w+",
        r"newest\s+\w+",
        r"last\s+(week|month|year|day|hour|minute)",
        r"past\s+(week|month|year|day|hour)",
        r"previous\s+(week|month|year|day)",
        r"current(?:ly)?\s+\w+",
        r"today'?s?\s+\w+",
        r"this\s+(week|month|year)",
        r"updat(?:e|ed|es)\s+(on|about|for|in)",
        r"fresh\s+\w+",
        r"modern\s+\w+",
        r"contemporary\s+\w+",
        r"present[\s-]day\s+\w+",
    ],
    "related": [
        r"relat(?:ed|ion)\s+(to|with|between)",
        r"similar\s+(to|as)",
        r"connected\s+(to|with)",
        r"associat(?:ed|ion)\s+(with|to)",
        r"linked\s+(to|with)",
        r"correlat(?:ed|ion)\s+(with|to|between)",
        r"affiliated\s+(with|to)",
        r"relevant\s+(to|for)",
        r"pertinent\s+(to|for)",
        r"applicable\s+(to|for)",
        r"pertain(?:s|ing)?\s+to",
        r"in\s+relation\s+to",
        r"with\s+respect\s+to",
        r"in\s+the\s+context\s+of",
        r"around\s+(the\s+)?topic\s+of",
        r"concerning",
        r"regarding",
        r"about",
    ],
}

# Fields that are commonly enumerated — maps keyword → ES field name
ENUMERABLE_FIELDS = {
    "location":       "location_name",
    "locations":      "location_name",
    "site":           "location_name",
    "sites":          "location_name",
    "place":          "location_name",
    "places":         "location_name",
    "area":           "location_name",
    "areas":          "location_name",
    "region":         "location_name",
    "regions":        "location_name",
    "zone":           "location_name",
    "zones":          "location_name",
    "city":           "location_name",
    "cities":         "location_name",
    "country":        "location_name",
    "countries":      "location_name",
    "address":        "location_name",
    "addresses":      "location_name",
    "venue":          "location_name",
    "venues":         "location_name",
    "destination":    "location_name",
    "destinations":   "location_name",
    "origin":         "location_name",
    "origins":        "location_name",
    "activity":       "activity_name",
    "activities":     "activity_name",
    "activity_type":  "activity_type",
    "activity_types": "activity_type",
    "action":         "activity_name",
    "actions":        "activity_name",
    "task":           "activity_name",
    "tasks":          "activity_name",
    "operation":      "activity_name",
    "operations":     "activity_name",
    "mission":        "activity_name",
    "missions":       "activity_name",
    "event":          "activity_name",
    "events":         "activity_name",
    "type":           "form_type",
    "types":          "form_type",
    "form_type":      "form_type",
    "form_types":     "form_type",
    "category":       "form_type",
    "categories":     "form_type",
    "class":          "form_type",
    "classes":        "form_type",
    "kind":           "form_type",
    "kinds":          "form_type",
    "source":         "source_type",
    "sources":        "source_type",
    "source_type":    "source_type",
    "source_types":   "source_type",
    "origin_type":    "source_type",
    "equipment":      "equipment_name",
    "equipments":     "equipment_name",
    "equipment_type": "equipment_type",
    "equipment_types":"equipment_type",
    "device":         "equipment_name",
    "devices":        "equipment_name",
    "tool":           "equipment_name",
    "tools":          "equipment_name",
    "asset":          "equipment_name",
    "assets":         "equipment_name",
    "name":           "name",
    "names":          "name",
    "title":          "form_title",
    "titles":         "form_title",
    "form":           "form_title",
    "forms":          "form_title",
    "form_title":     "form_title",
    "status":         "status",
    "statuses":       "status",
    "state":          "status",
    "states":         "status",
    "phase":          "status",
    "phases":         "status",
    "stage":          "status",
    "stages":         "status",
    "priority":       "status",
    "priorities":     "status",
    "level":          "status",
    "levels":         "status",
    "severity":       "status",
    "severities":     "status",
    "impact":         "status",
    "impacts":        "status",
    "risk":           "status",
    "risks":          "status",
    "issue":          "status",
    "issues":         "status",
    "problem":        "status",
    "problems":       "status",
    "incident":       "status",
    "incidents":      "status",
}


def classify_query(query: str) -> dict:
    """
    Classify the query intent to determine the optimal processing strategy.

    Returns:
        {
            "intent": str,               # one of the intent types above
            "enum_field": str or None,   # ES field to aggregate on (if applicable)
            "strategy": str,             # processing strategy
            "confidence": float,         # 0-1
        }

        Strategies:
            "direct_aggregation"  → enumeration/count/top_n: ES agg only, no LLM
            "aggregation_plus_llm" → distribution: ES agg + single LLM call
            "knn_single"          → lookup/search/detail/recent/related: kNN + single LLM
            "knn_chunked"         → analytical/comparison/trend/prediction/summary: kNN + chunked LLM
    """
    q_lower = query.lower().strip()

    # Detect intent by checking patterns in priority order
    detected_intent = "unknown"
    for intent, patterns in INTENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, q_lower):
                detected_intent = intent
                break
        if detected_intent != "unknown":
            break

    # Detect which field the user is asking about
    enum_field = None
    for keyword, es_field in ENUMERABLE_FIELDS.items():
        if re.search(rf"\b{re.escape(keyword)}\b", q_lower):
            enum_field = es_field
            break

    # Also check the mode selector (Answer/Analyze/Predict/Summarize)
    # This can override or refine the intent

    # Route to strategy
    if detected_intent in ("enumeration", "count", "top_n") and enum_field:
        strategy = "direct_aggregation"
        confidence = 0.95
    elif detected_intent == "distribution" and enum_field:
        strategy = "aggregation_plus_llm"
        confidence = 0.9
    elif detected_intent in ("lookup", "search", "detail", "recent", "related"):
        strategy = "knn_single"
        confidence = 0.85
    elif detected_intent in ("analytical", "comparison", "trend", "prediction", "summary"):
        strategy = "knn_chunked"
        confidence = 0.9
    elif detected_intent == "unknown" and enum_field:
        # Has a field but no clear intent — default to lookup
        strategy = "knn_single"
        confidence = 0.5
    else:
        strategy = "knn_single"
        confidence = 0.4

    result = {
        "intent": detected_intent,
        "enum_field": enum_field,
        "strategy": strategy,
        "confidence": confidence,
    }
    logger.info(f"Intent: {detected_intent} | strategy: {strategy} | field: {enum_field} | confidence: {confidence}")
    return result


# ── Elasticsearch aggregations ─────────────────────────────────────────

def get_aggregation_values(field: str, max_buckets: int = 200, filters: dict = None) -> dict:
    """
    Get ALL distinct values for a field using ES terms aggregation.
    Tries `.keyword` subfield first, then falls back to direct field name.
    """
    es = get_es()

    # Try field variants: .keyword first, then raw field name
    field_variants = [f"{field}.keyword", field]

    for field_name in field_variants:
        agg_body = {
            "size": 0,
            "aggs": {
                "distinct_values": {
                    "terms": {
                        "field": field_name,
                        "size": max_buckets,
                        "order": {"_count": "desc"},
                    }
                },
                "unique_count": {
                    "cardinality": {"field": field_name}
                }
            }
        }

        if filters:
            filter_clauses = []
            for fn, fv in filters.items():
                if fv and str(fv).strip():
                    # Also try .keyword for filter fields
                    filter_clauses.append({"term": {f"{fn}.keyword": str(fv).strip()}})
            if filter_clauses:
                agg_body["query"] = {"bool": {"filter": filter_clauses}}

        try:
            result = es.search(index=VECTOR_INDEX, body=agg_body, timeout="30s")
            buckets = result["aggregations"]["distinct_values"]["buckets"]
            unique_count = result["aggregations"]["unique_count"]["value"]

            values = [{"value": b["key"], "count": b["doc_count"]} for b in buckets]
            is_complete = len(buckets) < max_buckets

            logger.info(f"Aggregation '{field_name}': {len(values)} values, {unique_count} unique, complete={is_complete}")
            return {
                "values": values,
                "total_unique": unique_count,
                "returned": len(values),
                "is_complete": is_complete,
                "field": field,
            }
        except Exception as e:
            logger.warning(f"Aggregation failed for '{field_name}': {e}")
            continue

    # All variants failed
    logger.error(f"All aggregation variants failed for field '{field}'")
    return {"values": [], "total_unique": 0, "returned": 0, "is_complete": True, "field": field}


def get_multi_field_aggregations(fields: list, filters: dict = None) -> dict:
    """Get aggregations for multiple fields in a single ES call."""
    es = get_es()

    aggs = {}
    for f in fields:
        aggs[f"distinct_{f}"] = {
            "terms": {"field": f"{f}.keyword", "size": 200, "order": {"_count": "desc"}}
        }
        aggs[f"unique_{f}"] = {
            "cardinality": {"field": f"{f}.keyword"}
        }

    agg_body = {"size": 0, "aggs": aggs}

    if filters:
        filter_clauses = []
        for fn, fv in filters.items():
            if fv and str(fv).strip():
                filter_clauses.append({"term": {f"{fn}.keyword": str(fv).strip()}})
        if filter_clauses:
            agg_body["query"] = {"bool": {"filter": filter_clauses}}

    try:
        result = es.search(index=VECTOR_INDEX, body=agg_body)
        output = {}
        for f in fields:
            buckets = result["aggregations"][f"distinct_{f}"]["buckets"]
            unique = result["aggregations"][f"unique_{f}"]["value"]
            output[f] = {
                "values": [{"value": b["key"], "count": b["doc_count"]} for b in buckets],
                "total_unique": unique,
                "returned": len(buckets),
                "is_complete": len(buckets) < 200,
            }
        return output
    except Exception as e:
        logger.error(f"Multi-aggregation failed: {e}")
        return {}


# ── Search & context building ─────────────────────────────────────────

def search_index(query: str, k: int = TOP_K_RESULTS, filters: dict = None,
                 min_score: float = None) -> list:
    """
    Search vec_fatboy_data using kNN vector search.
    Returns a list of hit dicts with _score, _source, _id.
    """
    es = get_es()
    query_vec = embed_query(query)

    knn_clause = {
        "field": "embedding",
        "query_vector": query_vec,
        "k": k,
        "num_candidates": max(k * 4, 50),
    }

    if filters:
        filter_clauses = []
        for field_name, value in filters.items():
            if value and str(value).strip():
                filter_clauses.append({"term": {field_name: str(value).strip()}})
        if filter_clauses:
            knn_clause["filter"] = {"bool": {"filter": filter_clauses}}

    search_body = {
        "knn": knn_clause,
        "size": k,
        "_source": True,
    }

    result = es.search(index=VECTOR_INDEX, body=search_body)
    hits = result["hits"]["hits"]

    if min_score:
        hits = [h for h in hits if h["_score"] >= min_score]

    logger.info(f"kNN search returned {len(hits)} results (from {result['hits']['total']['value']} total)")
    return hits


def search_with_scroll(query: str, batch_size: int = 50, max_docs: int = 200,
                       filters: dict = None) -> list:
    """
    Multi-pass retrieval: use scroll API to fetch many more docs than kNN top-k.
    For enumeration queries, this ensures we see documents covering all values.
    Falls back to match_all if query embedding is generic.
    """
    es = get_es()

    body = {"size": batch_size, "_source": True}

    if filters:
        filter_clauses = []
        for fn, fv in filters.items():
            if fv and str(fv).strip():
                filter_clauses.append({"term": {fn: str(fv).strip()}})
        body["query"] = {"bool": {"filter": filter_clauses}} if filter_clauses else {"match_all": {}}
    else:
        # Use the query text for a broad match
        body["query"] = {
            "multi_match": {
                "query": query,
                "fields": ["description", "title", "location_name", "activity_name",
                           "form_title", "form_data_search", "source_data", "paragraph"],
                "operator": "or",
                "minimum_should_match": 1,
            }
        }

    try:
        result = es.search(index=VECTOR_INDEX, scroll="5m", body=body)
        scroll_id = result["_scroll_id"]
        hits = result["hits"]["hits"]
        all_hits = list(hits)
        fetched = len(hits)

        while fetched < max_docs and hits:
            result = es.scroll(scroll_id=scroll_id, scroll="5m")
            scroll_id = result["_scroll_id"]
            hits = result["hits"]["hits"]
            all_hits.extend(hits)
            fetched += len(hits)

        try:
            es.clear_scroll(scroll_id=scroll_id)
        except Exception:
            pass

        logger.info(f"Scroll retrieval fetched {len(all_hits)} docs")
        return all_hits
    except Exception as e:
        logger.error(f"Scroll retrieval failed: {e}")
        return []


def deduplicate_hits(hits: list, field: str = None) -> list:
    """
    Deduplicate hits by a key field. If no field specified, deduplicate by
    content similarity (same title + description prefix).
    """
    seen = set()
    unique = []

    for hit in hits:
        src = hit["_source"]
        if field:
            key_val = src.get(field, "")
            if isinstance(key_val, str):
                key_val = key_val.strip().lower()
            key = (field, str(key_val))
        else:
            # Deduplicate by content fingerprint
            title = src.get("title", src.get("form_title", src.get("name", "")))
            desc = src.get("description", src.get("orignal_description", ""))[:100]
            key = (str(title).strip().lower(), str(desc).strip().lower())

        if key not in seen:
            seen.add(key)
            unique.append(hit)

    logger.info(f"Deduplication: {len(hits)} → {len(unique)} unique hits")
    return unique


def build_context(hits: list, max_chars: int = MAX_CONTEXT_CHARS,
                  enum_field: str = None, enum_values: list = None) -> str:
    """
    Build context string from search hits with smart allocation.

    For enumeration queries: ensures each enumerated value has at least
    one representative document in the context.
    """
    parts = []
    total_chars = 0

    # Track which enum values we've covered
    covered_values = set()

    # First pass: for each hit, extract text and track enum coverage
    hit_entries = []
    for i, hit in enumerate(hits):
        source = hit["_source"]
        score = hit["_score"]

        text_parts = []
        for field in ["description", "title", "orignal_description", "paragraph",
                       "form_data_search", "source_data", "activity_name",
                       "location_name", "form_title", "form_type", "activity_type",
                       "equipment_name", "equipment_type", "name", "remark", "remarks"]:
            val = source.get(field)
            if val and isinstance(val, str) and val.strip():
                text_parts.append(f"{field}: {val.strip()}")

        if not text_parts:
            embedded = source.get("embedded_text", "")
            if embedded:
                text_parts.append(embedded[:500])

        passage = " | ".join(text_parts)
        if not passage.strip():
            continue

        # Track enum value coverage
        enum_val = None
        if enum_field:
            ev = source.get(enum_field, "")
            if ev and isinstance(ev, str):
                enum_val = ev.strip()
                covered_values.add(enum_val.lower())

        entry = f"[Source {i+1}] (score: {score:.4f})\n{passage}"
        hit_entries.append((entry, enum_val, score))

    # Second pass: prioritize entries that cover uncovered enum values
    if enum_values and len(enum_values) > len(covered_values):
        # There are enum values not covered by any hit — note this
        uncovered = [v for v in enum_values if v["value"].lower() not in covered_values]
        if uncovered:
            logger.warning(f"{len(uncovered)} enum values not found in retrieved docs")

    # Build final context, allocating chars evenly
    per_hit_budget = max_chars // max(len(hit_entries), 1)

    for entry, enum_val, score in hit_entries:
        if total_chars >= max_chars:
            break

        remaining = max_chars - total_chars
        if len(entry) > per_hit_budget and remaining > 100:
            # Smart truncation: try to cut at a field boundary
            truncated = entry[:min(per_hit_budget, remaining)]
            # Cut at last complete field
            last_pipe = truncated.rfind(" | ")
            if last_pipe > len(truncated) * 0.5:
                truncated = truncated[:last_pipe]
            entry = truncated + "\n...[truncated]"

        if total_chars + len(entry) <= max_chars:
            parts.append(entry)
            total_chars += len(entry)
        elif remaining > 50:
            parts.append(entry[:remaining] + "...[truncated]")
            break

    return "\n\n".join(parts)


def build_aggregation_context(agg_data: dict, enum_field: str) -> str:
    """
    Build context from aggregation results for enumeration queries.
    This gives the LLM a structured list of ALL distinct values.
    """
    values = agg_data.get("values", [])
    total_unique = agg_data.get("total_unique", 0)
    is_complete = agg_data.get("is_complete", True)

    parts = [f"Complete list of {total_unique} distinct {enum_field} values found in the index:\n"]

    for i, v in enumerate(values):
        count_info = f"({v['count']} documents)" if v.get('count', 0) > 1 else "(1 document)"
        parts.append(f"  {i+1}. {v['value']} {count_info}")

    if not is_complete:
        parts.append(f"\n[NOTE: Showing top {len(values)} of {total_unique} total unique values. List may be incomplete.]")

    return "\n".join(parts)


# ── Report generation ─────────────────────────────────────────────────

def _chunk_list(lst, chunk_size):
    """Split a list into chunks of chunk_size."""
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]


def _build_enumeration_report(query, agg_data, enum_field, completeness_notes, sources, metadata_extra):
    """
    For enumeration queries ('list all X'), build the report DIRECTLY from
    aggregation data — no LLM needed. This guarantees every value is listed.
    """
    values = agg_data.get("values", [])
    total_unique = agg_data.get("total_unique", 0)
    is_complete = agg_data.get("is_complete", True)

    lines = []
    lines.append(f"## Complete List of {enum_field}\n")
    lines.append(f"**Total: {total_unique} distinct values**\n")

    for i, v in enumerate(values):
        count_info = f" — {v['count']} documents" if v.get("count", 0) > 1 else " — 1 document"
        lines.append(f"{i+1}. **{v['value']}**{count_info}")

    if not is_complete:
        lines.append(f"\n⚠ Showing top {len(values)} of {total_unique} total values. Some values may be missing.")

    if completeness_notes:
        lines.append("\n## Data Quality Notes\n")
        for note in completeness_notes:
            lines.append(f"- {note}")

    # Info about data source
    total_docs = metadata_extra.get("index_total_docs", 0)
    if total_docs > 0:
        lines.append(f"\n_Searched {total_docs:,} documents in index '{metadata_extra.get('index', VECTOR_INDEX)}'_")

    # Add source summary
    if sources:
        lines.append(f"\n## Supporting Sources ({len(sources)} documents sampled)\n")
        for s in sources[:8]:
            loc = f" | {s['location']}" if s.get("location") else ""
            lines.append(f"- [{s['idx']}] {s['title']}{loc}")

    answer = "\n".join(lines)

    return {
        "title": f"📋 Enumeration: {enum_field} ({total_unique} values)",
        "mode": "answer",
        "mode_label": "Enumeration",
        "mode_icon": "📋",
        "mode_color": "#4CAF50",
        "query": query,
        "answer": answer,
        "sources": sources,
        "completeness_notes": completeness_notes,
        "metadata": {
            "total_hits": metadata_extra.get("total_hits", 0),
            "deduplicated_hits": metadata_extra.get("deduplicated_hits", 0),
            "selected_hits": len(sources),
            "context_chars": 0,
            "generation_time": 0,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "model": "direct-enumeration",
            "embed_model": EMBED_MODEL,
            "index": VECTOR_INDEX,
            "index_total_docs": metadata_extra.get("index_total_docs", 0),
            "strategy": "direct_enumeration",
            "is_enumeration": True,
            "enumeration_field": enum_field,
            "aggregation": {
                "field": enum_field,
                "total_unique": total_unique,
                "returned_values": len(values),
                "is_complete": is_complete,
            },
            "filters": metadata_extra.get("filters", {}),
        },
    }


def _build_chunked_analytical_report(query, mode, full_context, selected_hits,
                                      completeness_notes, metadata_extra):
    """
    For analytical queries, chunk the context and process in multiple LLM calls,
    then merge the results. Handles arbitrarily large datasets.
    """
    CHUNK_SIZE = 3000  # chars per chunk — fits comfortably in context window
    MAX_CHUNKS = 8     # safety limit

    # Split context into chunks
    context_chunks = []
    if full_context:
        # Split on document boundaries ([Source N])
        passages = re.split(r'(?=\[Source \d+\] )', full_context)
        current_chunk = ""
        for p in passages:
            if len(current_chunk) + len(p) > CHUNK_SIZE and current_chunk:
                context_chunks.append(current_chunk)
                current_chunk = p
            else:
                current_chunk += p
        if current_chunk:
            context_chunks.append(current_chunk)

    if not context_chunks:
        context_chunks = ["No relevant document passages found."]

    # Cap chunks
    if len(context_chunks) > MAX_CHUNKS:
        logger.warning(f"Context split into {len(context_chunks)} chunks, capping to {MAX_CHUNKS}")
        context_chunks = context_chunks[:MAX_CHUNKS]

    mode_prompt = get_mode_prompt(mode)
    completeness_block = ""
    if completeness_notes:
        completeness_block = "\n\n=== DATA COMPLETENESS WARNINGS ===\n" + \
            "\n".join(f"- {n}" for n in completeness_notes) + \
            "\nYou MUST include these warnings in your report."

    # Process each chunk
    chunk_summaries = []
    for i, chunk in enumerate(context_chunks):
        logger.info(f"Processing chunk {i+1}/{len(context_chunks)} ({len(chunk)} chars)...")

        if len(context_chunks) == 1:
            # Single chunk — generate full report
            prompt = f"""{mode_prompt}{completeness_block}

=== DOCUMENT PASSAGES ===
{chunk}

=== USER QUESTION ===
{query}

=== YOUR REPORT ===
(Must include: Executive Summary, Key Findings, Detailed Analysis, Conclusions)"""
        else:
            # Multiple chunks — first chunks get "partial analysis", last gets "final synthesis"
            if i < len(context_chunks) - 1:
                prompt = f"""{mode_prompt}

This is PART {i+1} of {len(context_chunks)} of the document collection.

=== DOCUMENT PASSAGES (PART {i+1}/{len(context_chunks)}) ===
{chunk}

=== USER QUESTION ===
{query}

=== YOUR TASK ===
Analyze ONLY the passages in this part. Provide a partial analysis covering:
- Key findings from this section
- Important data points, names, dates
- Any patterns or notable information

Keep it concise — this will be combined with other parts later."""
            else:
                # Final chunk — synthesize everything
                prev_summaries = "\n\n".join(
                    f"--- Part {j+1} Summary ---\n{s}"
                    for j, s in enumerate(chunk_summaries)
                )
                prompt = f"""{mode_prompt}{completeness_block}

=== PREVIOUS ANALYSIS (Parts 1-{len(chunk_summaries)}) ===
{prev_summaries}

=== FINAL DOCUMENT PASSAGES (PART {i+1}/{len(context_chunks)}) ===
{chunk}

=== USER QUESTION ===
{query}

=== YOUR TASK ===
Synthesize ALL parts into a single comprehensive report. Include:
- Executive Summary
- Key Findings (from all parts)
- Detailed Analysis
- Conclusions
- Citations like [Source 1], [Source 2]"""

        summary = call_llm(prompt, max_tokens=2048)
        chunk_summaries.append(summary)
        logger.info(f"Chunk {i+1} done: {len(summary)} chars")

    # Merge: if single chunk, use directly; if multiple, the last one is the synthesis
    if len(chunk_summaries) == 1:
        answer = chunk_summaries[0]
    elif len(chunk_summaries) <= 3:
        # Few chunks — combine all
        answer = "\n\n---\n\n".join(chunk_summaries)
    else:
        # Many chunks — use the final synthesis (which already includes previous parts)
        answer = chunk_summaries[-1]

    return answer


def generate_report(query: str, mode: str = "answer", filters: dict = None) -> dict:
    """
    Full pipeline with intent-based routing:
      - direct_aggregation:  enumeration/count/top_n → ES agg only, direct output, no LLM
      - aggregation_plus_llm: distribution → ES agg + single LLM call
      - knn_single:          lookup/search/detail/recent/related → kNN + single LLM
      - knn_chunked:         analytical/comparison/trend/prediction/summary → kNN + chunked LLM
    """
    logger.info(f"Generating report | mode={mode} | query='{query[:80]}'")
    start = time.time()

    # ── Step 1: Classify intent ──────────────────────────────────────
    classification = classify_query(query)
    intent = classification["intent"]
    enum_field = classification.get("enum_field")
    strategy = classification["strategy"]

    # ── Step 2: Execute based on strategy ────────────────────────────

    # === DIRECT AGGREGATION: enumeration, count, top_n ===
    # No LLM needed — output aggregation data directly
    if strategy == "direct_aggregation" and enum_field:
        agg_data = get_aggregation_values(enum_field, max_buckets=2000, filters=filters)

        # Still do a small kNN search for sample sources
        hits = search_index(query, k=10, filters=filters)
        selected_hits = hits[:10]

        completeness_notes = []
        if not agg_data.get("is_complete", True):
            completeness_notes.append(
                f"Showing top {agg_data['returned']} of {agg_data['total_unique']} values."
            )

        result = _build_enumeration_report(
            query=query, agg_data=agg_data, enum_field=enum_field,
            completeness_notes=completeness_notes, sources=[],
            metadata_extra={
                "total_hits": len(hits),
                "deduplicated_hits": len(hits),
                "index_total_docs": _safe_index_count(),
                "filters": filters or {},
            },
        )
        elapsed = time.time() - start
        result["metadata"]["generation_time"] = round(elapsed, 1)
        logger.info(f"Direct enumeration done in {elapsed:.1f}s | {agg_data.get('total_unique', 0)} values")
        return result

    # === AGGREGATION + LLM: distribution queries ===
    if strategy == "aggregation_plus_llm" and enum_field:
        agg_data = get_aggregation_values(enum_field, max_buckets=2000, filters=filters)

        # kNN for sample passages
        hits = search_index(query, k=10, filters=filters)
        selected_hits = hits[:10]

        # Build aggregation context only (no doc passages needed for distribution)
        agg_context = build_aggregation_context(agg_data, enum_field)

        mode_prompt = get_mode_prompt(mode)
        prompt = f"""{mode_prompt}

=== AGGREGATION DATA ===
{agg_context}

=== USER QUESTION ===
{query}

=== YOUR REPORT ===
Provide a clear analysis of the distribution. Include the complete list of values with their counts and percentages."""

        answer = call_llm(prompt, max_tokens=3000)

        sources = _build_sources_list(selected_hits)
        result = _build_result_dict(query, mode, answer, sources, agg_data, classification, start, filters)
        logger.info(f"Aggregation+LLM done in {result['metadata']['generation_time']}s")
        return result

    # === KNN + SINGLE LLM: lookup, search, detail, recent, related ===
    if strategy == "knn_single":
        hits = search_index(query, k=TOP_K_RESULTS, filters=filters)
        selected_hits = hits[:TOP_K_RESULTS]

        if not selected_hits:
            return _empty_result(query, mode, filters, start)

        doc_context = build_context(selected_hits, max_chars=MAX_CONTEXT_CHARS)

        mode_prompt = get_mode_prompt(mode)
        prompt = f"""{mode_prompt}

=== DOCUMENT PASSAGES ===
{doc_context}

=== USER QUESTION ===
{query}

=== YOUR REPORT ===
Provide a concise, focused answer based on the passages above. Cite sources like [Source 1]."""

        answer = call_llm(prompt, max_tokens=2048)

        sources = _build_sources_list(selected_hits)
        result = _build_result_dict(query, mode, answer, sources, None, classification, start, filters)
        logger.info(f"kNN+single done in {result['metadata']['generation_time']}s")
        return result

    # === KNN + CHUNKED LLM: analytical, comparison, trend, prediction, summary ===
    # Default fallback also goes here
    hits = search_index(query, k=TOP_K_RESULTS, filters=filters)

    # Also do scroll for broader coverage
    scroll_hits = search_with_scroll(query, batch_size=50, max_docs=200, filters=filters)

    all_hits = list(hits)
    seen_ids = {h["_id"] for h in hits}
    for h in scroll_hits:
        if h["_id"] not in seen_ids:
            all_hits.append(h)
            seen_ids.add(h["_id"])

    if not all_hits:
        return _empty_result(query, mode, filters, start)

    deduped_hits = deduplicate_hits(all_hits)
    deduped_hits.sort(key=lambda h: h["_score"], reverse=True)
    selected_hits = deduped_hits[:30]  # Take top 30 for chunking

    # Build full context and chunk it
    doc_context = build_context(selected_hits, max_chars=MAX_CONTEXT_CHARS * 4)  # Allow larger for chunking

    answer = _build_chunked_analytical_report(
        query=query, mode=mode, full_context=doc_context,
        selected_hits=selected_hits, completeness_notes=[], metadata_extra={},
    )

    sources = _build_sources_list(selected_hits[:MAX_SOURCES_IN_REPORT])
    result = _build_result_dict(query, mode, answer, sources, None, classification, start, filters)
    logger.info(f"kNN+chunked done in {result['metadata']['generation_time']}s")
    return result


# ── Helper functions ──────────────────────────────────────────────────

def _safe_index_count():
    try:
        return get_es().count(index=VECTOR_INDEX)["count"]
    except Exception:
        return 0


def _build_sources_list(selected_hits):
    sources = []
    for i, hit in enumerate(selected_hits):
        source = hit["_source"]
        sources.append({
            "idx": i + 1,
            "score": round(hit["_score"], 4),
            "id": hit["_id"],
            "title": source.get("title", source.get("form_title", source.get("name", "Untitled"))),
            "description": (source.get("description", source.get("orignal_description", "")))[:200],
            "activity": source.get("activity_name", ""),
            "location": source.get("location_name", ""),
            "type": source.get("form_type", source.get("source_type", "")),
        })
    return sources


def _empty_result(query, mode, filters, start):
    mode_info = MODES.get(mode, MODES["answer"])
    return {
        "title": f"{mode_info['icon']} {mode_info['label']} Report: {query[:60]}",
        "mode": mode,
        "query": query,
        "answer": "No relevant documents found in the index. Try a different query or broader terms.",
        "sources": [],
        "metadata": {
            "total_hits": 0,
            "generation_time": round(time.time() - start, 1),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "model": LLM_MODEL,
            "filters": filters or {},
        },
    }


def _build_result_dict(query, mode, answer, sources, agg_data, classification, start, filters):
    mode_info = MODES.get(mode, MODES["answer"])
    elapsed = time.time() - start
    return {
        "title": f"{mode_info['icon']} {mode_info['label']} Report: {query[:60]}{'...' if len(query) > 60 else ''}",
        "mode": mode,
        "mode_label": mode_info["label"],
        "mode_icon": mode_info["icon"],
        "mode_color": mode_info["color"],
        "query": query,
        "answer": answer,
        "sources": sources,
        "completeness_notes": [],
        "metadata": {
            "total_hits": 0,
            "deduplicated_hits": 0,
            "selected_hits": len(sources),
            "context_chars": 0,
            "generation_time": round(elapsed, 1),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "model": LLM_MODEL,
            "embed_model": EMBED_MODEL,
            "index": VECTOR_INDEX,
            "index_total_docs": _safe_index_count(),
            "strategy": classification["strategy"],
            "intent": classification["intent"],
            "is_enumeration": classification["intent"] in ("enumeration", "count", "top_n"),
            "enumeration_field": classification.get("enum_field"),
            "aggregation": {
                "field": classification.get("enum_field"),
                "total_unique": agg_data.get("total_unique", 0),
                "returned_values": agg_data.get("returned", 0),
                "is_complete": agg_data.get("is_complete", True),
            } if agg_data else None,
            "filters": filters or {},
        },
    }
