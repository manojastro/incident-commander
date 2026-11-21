"""Synthetic Acme Retail Ltd incident catalogue (offline, mock-first).

5 scenarios used by the agent, the fixed-workflow baseline, and evals.
Ground truth root causes live here so evals can score RCA correctness.
"""

from __future__ import annotations

SCENARIOS: dict[str, dict[str, object]] = {
    "INC001": {
        "title": "Checkout 500s — DB connection pool exhausted",
        "description": "Checkout API returns HTTP 500, 'connection pool exhausted' in logs.",
        "service": "checkout-api",
        "ground_truth": "db pool exhausted after deploy chg-101 raised max connections demand",
        "category": "database",
        "logs": [
            "2026-09-18T10:02:11Z ERROR checkout-api connection pool exhausted (128/128) at incident time",  # noqa: E501
            "2026-09-18T10:02:12Z ERROR checkout-api timeout waiting for idle connection",
            "2026-09-18T09:58:00Z INFO checkout-api deploy chg-101 finished",
        ],
        "changes": [
            {
                "id": "chg-101",
                "ci": "checkout-api",
                "summary": "raise checkout concurrency",
                "age_min": 25,
            },
        ],
        "blast_radius": ["checkout-api", "orders-db", "payments-svc"],
        "kedb": [
            {
                "id": "KE-014",
                "title": "DB pool exhaustion after concurrency increase",
                "similarity": 0.92,
            },
        ],
    },
    "INC002": {
        "title": "Checkout latency — red-herring deploy",
        "description": "Checkout p99 latency 4s. A frontend deploy finished 10 min ago.",
        "service": "checkout-api",
        "ground_truth": "core switch packet loss (network), frontend deploy chg-102 is a red herring",  # noqa: E501
        "category": "network",
        "logs": [
            "2026-09-18T11:20:00Z ERROR checkout-api upstream timeout at incident time",
            "2026-09-18T11:19:30Z WARN core-sw-01 packet loss 8% interface eth1/1",
            "2026-09-18T11:10:00Z INFO web-frontend deploy chg-102 css bundle finished",
        ],
        "changes": [
            {"id": "chg-102", "ci": "web-frontend", "summary": "css bundle update", "age_min": 10},
        ],
        "blast_radius": ["checkout-api", "core-sw-01", "edge-lb-02"],
        "kedb": [
            {
                "id": "KE-031",
                "title": "p99 latency from core switch packet loss",
                "similarity": 0.88,
            },
            {"id": "KE-002", "title": "slow css deploys cause render delay", "similarity": 0.41},
        ],
    },
    "INC003": {
        "title": "Orders API crashloop — OOM after config change",
        "description": "orders-api pods crashloop with OOMKilled after heap limit lowered.",
        "service": "orders-api",
        "ground_truth": "oom crashloop after config chg-103 lowered heap limit",
        "category": "application",
        "logs": [
            "2026-09-18T12:00:05Z ERROR orders-api OOMKilled heap limit 512Mi at incident time",
            "2026-09-18T12:00:06Z ERROR orders-api crashloop backoff restart count 7",
        ],
        "changes": [
            {
                "id": "chg-103",
                "ci": "orders-api",
                "summary": "lower heap limit 1Gi->512Mi",
                "age_min": 40,
            },
        ],
        "blast_radius": ["orders-api", "orders-db"],
        "kedb": [
            {"id": "KE-022", "title": "OOMKilled after heap limit reduction", "similarity": 0.95},
        ],
    },
    "INC004": {
        "title": "Search slow — missing DB index",
        "description": "Catalog search p95 6s, full table scan in slow-query log.",
        "service": "search-api",
        "ground_truth": "missing index on catalog_items after schema migration chg-104",
        "category": "database",
        "logs": [
            "2026-09-18T13:15:00Z ERROR search-api slow query 6.1s full table scan catalog_items at incident time",  # noqa: E501
            "2026-09-18T13:00:00Z INFO search-api schema migration chg-104 finished",
        ],
        "changes": [
            {
                "id": "chg-104",
                "ci": "search-api",
                "summary": "schema migration dropped index",
                "age_min": 55,
            },
        ],
        "blast_radius": ["search-api", "catalog-db"],
        "kedb": [
            {
                "id": "KE-040",
                "title": "full table scan after index dropped by migration",
                "similarity": 0.90,
            },
        ],
    },
    "INC005": {
        "title": "Login failures — external DNS, no related change",
        "description": "Login fails with DNS NXDOMAIN for auth.acme.example. No recent changes.",
        "service": "login-api",
        "ground_truth": "external dns provider outage, no related change exists",
        "category": "network",
        "logs": [
            "2026-09-18T14:00:01Z ERROR login-api dns NXDOMAIN auth.acme.example at incident time",
            "2026-09-18T14:00:02Z WARN login-api upstream dns provider timeout",
        ],
        "changes": [],
        "blast_radius": ["login-api", "ext-dns-provider"],
        "kedb": [
            {
                "id": "KE-055",
                "title": "login NXDOMAIN during external DNS outage",
                "similarity": 0.86,
            },
        ],
    },
}

SCENARIO_IDS: list[str] = ["INC001", "INC002", "INC003", "INC004", "INC005"]
