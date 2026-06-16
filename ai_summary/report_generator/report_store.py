"""
Report Store — save and load generated reports as JSON for history & download.
"""

import os
import json
import uuid
import time

from config import REPORT_DIR, logger


def save_report(report_data: dict) -> str:
    """Save a report to disk. Returns the report_id."""
    report_id = str(uuid.uuid4())[:8]
    filename = f"report_{report_id}.json"
    filepath = os.path.join(REPORT_DIR, filename)

    report_data["report_id"] = report_id
    report_data["saved_at"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    logger.info(f"Report saved: {filename} ({report_id})")
    return report_id


def load_report(report_id: str) -> dict:
    """Load a report from disk by ID."""
    filename = f"report_{report_id}.json"
    filepath = os.path.join(REPORT_DIR, filename)
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def list_reports(limit: int = 20) -> list:
    """List recent reports (newest first)."""
    files = []
    for f in os.listdir(REPORT_DIR):
        if f.startswith("report_") and f.endswith(".json"):
            fp = os.path.join(REPORT_DIR, f)
            files.append((fp, os.path.getmtime(fp)))
    files.sort(key=lambda x: x[1], reverse=True)

    reports = []
    for fp, _ in files[:limit]:
        try:
            with open(fp, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            reports.append({
                "report_id": data.get("report_id", ""),
                "title": data.get("title", "Untitled"),
                "mode": data.get("mode", ""),
                "query": data.get("query", "")[:80],
                "timestamp": data.get("timestamp", ""),
                "saved_at": data.get("saved_at", ""),
                "generation_time": data.get("metadata", {}).get("generation_time", 0),
                "total_hits": data.get("metadata", {}).get("total_hits", 0),
            })
        except Exception:
            continue
    return reports
