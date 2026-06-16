#!/usr/bin/env python3
"""
CLI script to generate an AI Summary Report from the command line.

Usage:
    python3 cli_generate.py "What are the key deployment activities?" --mode answer
    python3 cli_generate.py "Summarize all equipment records" --mode summarize --output report.html
    python3 cli_generate.py "Analyze patrolling patterns" --mode analyze --filter activity_type=Patrolling
"""

import sys
import os
import argparse
import textwrap

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import MODES, logger
from rag_engine import generate_report
from report_renderer import render_report
from report_store import save_report


def main():
    parser = argparse.ArgumentParser(
        description="Generate AI Summary Report from Elasticsearch data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python3 cli_generate.py "What are the main activities?" --mode answer
              python3 cli_generate.py "Summarize deployment data" --mode summarize -o report.html
              python3 cli_generate.py "Analyze equipment patterns" --mode analyze --filter activity_type=Equipment
        """),
    )
    parser.add_argument("query", help="Your question or prompt")
    parser.add_argument("--mode", "-m", default="answer",
                        choices=list(MODES.keys()),
                        help="Report mode (default: answer)")
    parser.add_argument("--output", "-o", default=None,
                        help="Output HTML file path (default: auto-generated)")
    parser.add_argument("--filter", "-f", action="append", default=[],
                        help="Filter as field=value (repeatable)")
    parser.add_argument("--no-save", action="store_true",
                        help="Don't save report to disk, just output HTML")
    parser.add_argument("--preview", "-p", action="store_true",
                        help="Print text preview to stdout instead of saving HTML")

    args = parser.parse_args()

    # Parse filters
    filters = {}
    for f in args.filter:
        if "=" in f:
            k, v = f.split("=", 1)
            filters[k] = v

    print(f"\n{'='*60}")
    print(f"  AI Summary Report Generator")
    print(f"  Mode: {MODES[args.mode]['icon']} {MODES[args.mode]['label']}")
    print(f"  Query: {args.query}")
    if filters:
        print(f"  Filters: {filters}")
    print(f"{'='*60}\n")

    print("⏳ Searching vec_fatboy_data and generating report...\n")

    try:
        report_data = generate_report(
            query=args.query,
            mode=args.mode,
            filters=filters if filters else None,
        )
    except Exception as e:
        print(f"❌ Generation failed: {e}", file=sys.stderr)
        sys.exit(1)

    gen_time = report_data["metadata"]["generation_time"]
    total_hits = report_data["metadata"]["total_hits"]
    print(f"✅ Report generated in {gen_time}s ({total_hits} documents retrieved)\n")

    if args.preview:
        # Print text preview
        print("=" * 60)
        print(report_data["answer"])
        print("=" * 60)
        print(f"\nSources: {len(report_data['sources'])} documents")
        for s in report_data["sources"]:
            print(f"  [{s['idx']}] {s['title']} (score: {s['score']})")
        return

    # Render HTML
    html = render_report(report_data)

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        safe_name = "".join(c if c.isalnum() else "_" for c in args.query[:40])
        output_path = f"report_{args.mode}_{safe_name}.html"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"📄 HTML report saved: {os.path.abspath(output_path)}")

    # Save to report store
    if not args.no_save:
        report_id = save_report(report_data)
        print(f"💾 Report stored with ID: {report_id}")
        print(f"   View at: http://localhost:5001/report/{report_id}")


if __name__ == "__main__":
    main()
