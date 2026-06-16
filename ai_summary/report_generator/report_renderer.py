"""
HTML Report Renderer — converts report data into a beautiful standalone HTML page.
"""

from config import MODES


def render_report(report: dict) -> str:
    """Generate a complete, beautiful HTML report page from report data."""
    mode = report.get("mode", "answer")
    mode_info = MODES.get(mode, MODES["answer"])
    meta = report.get("metadata", {})
    sources = report.get("sources", [])
    answer_raw = report.get("answer", "")
    query = report.get("query", "")
    title = report.get("title", "AI Summary Report")
    completeness_notes = report.get("completeness_notes", [])
    aggregation = meta.get("aggregation")

    # Convert answer text to HTML sections (split by markdown-like headers)
    answer_html = _markdown_to_html(answer_raw)

    # Build sources table rows
    sources_rows = ""
    for s in sources:
        sources_rows += f"""
            <tr>
                <td><span class="source-num">[{s['idx']}]</span></td>
                <td class="score">{s['score']:.4f}</td>
                <td><strong>{_esc(s['title'])}</strong></td>
                <td>{_esc(s['description'][:150])}</td>
                <td><span class="tag">{_esc(s.get('type', ''))}</span></td>
                <td>{_esc(s.get('location', ''))}</td>
                <td>{_esc(s.get('activity', ''))}</td>
            </tr>"""

    # Build filter info
    filters = meta.get("filters", {})
    filter_html = ""
    if filters:
        filter_chips = "".join(
            f'<span class="filter-chip">{_esc(k)}: <strong>{_esc(str(v))}</strong></span>'
            for k, v in filters.items() if v
        )
        if filter_chips:
            filter_html = f'<div class="filters">{filter_chips}</div>'

    # Build completeness warnings HTML
    completeness_html = ""
    if completeness_notes:
        warnings_html = "".join(f"<li>{_esc(n)}</li>" for n in completeness_notes)
        completeness_html = f"""
  <div class="section" style="border-color:#f4433655;background:#f4433611">
    <div class="section-title" style="color:#f44336"><span class="icon">⚠️</span> Data Completeness Warning</div>
    <ul style="margin:8px 0 0 24px;color:#f44336;font-size:14px">
      {warnings_html}
    </ul>
  </div>"""

    # Build aggregation summary section
    agg_html = ""
    if aggregation and aggregation.get("field"):
        agg_field = aggregation["field"]
        agg_total = aggregation.get("total_unique", 0)
        agg_returned = aggregation.get("returned_values", 0)
        agg_complete = aggregation.get("is_complete", True)

        completeness_badge = f'<span class="agg-badge {"agg-complete" if agg_complete else "agg-partial"}">{"✓ Complete" if agg_complete else "⚠ Partial — showing top " + str(agg_returned)}</span>'

        agg_html = f"""
  <div class="section">
    <div class="section-title"><span class="icon">📊</span> Data Coverage: {_esc(agg_field)} {completeness_badge}</div>
    <p style="color:var(--text-dim);font-size:14px;margin-bottom:12px">
      Found <strong style="color:var(--accent)">{agg_total}</strong> distinct {_esc(agg_field)} values across <strong>{meta.get('index_total_docs', 'N/A')}</strong> indexed documents.
      {"All values retrieved." if agg_complete else f"Showing top {agg_returned} values. Some values may not appear in the report below."}
    </p>
    <div class="coverage-bar">
      <div class="coverage-fill" style="width:{"100" if agg_complete else f"{min(agg_returned/agg_total*100, 95):.0f}%"}"></div>
    </div>
  </div>"""

    # Build strategy info for meta bar
    strategy = meta.get("strategy", "knn_only")
    strategy_labels = {
        "aggregation_first": "Aggregation + kNN",
        "knn_then_aggregate": "kNN + Aggregation",
        "knn_only": "Semantic Search",
    }

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(title)}</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#0f1117;--surface:#1a1d27;--surface2:#242836;--border:#2e3348;
  --text:#e4e6f0;--text-dim:#8b8fa3;--accent:{mode_info['color']};--accent-dim:{mode_info['color']}33;
  --green:#4CAF50;--blue:#2196F3;--purple:#9C27B0;--orange:#FF9800;
  --red:#f44336;--radius:12px;--font:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  --mono:'SF Mono','Fira Code',monospace;
}}
body{{background:var(--bg);color:var(--text);font-family:var(--font);font-size:15px;line-height:1.7;padding:0}}
.container{{max-width:1000px;margin:0 auto;padding:40px 24px}}

/* ── Header ── */
.report-header{{background:linear-gradient(135deg,var(--surface) 0%,var(--surface2) 100%);border:1px solid var(--border);border-radius:var(--radius);padding:36px 40px;margin-bottom:24px;position:relative;overflow:hidden}}
.report-header::before{{content:'';position:absolute;top:0;left:0;right:0;height:4px;background:linear-gradient(90deg,var(--accent) 0%,var(--green) 33%,var(--blue) 66%,var(--purple) 100%)}}
.report-title{{font-size:28px;font-weight:700;margin-bottom:8px;letter-spacing:-0.5px}}
.mode-badge{{display:inline-flex;align-items:center;gap:6px;background:var(--accent-dim);color:var(--accent);border:1px solid {mode_info['color']}44;padding:4px 14px;border-radius:20px;font-size:13px;font-weight:600;margin-bottom:16px}}
.query-box{{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:16px 20px;margin-top:12px}}
.query-label{{font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:var(--text-dim);margin-bottom:4px}}
.query-text{{font-size:16px;font-weight:500;color:var(--text)}}

/* ── Meta bar ── */
.meta-bar{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:24px}}
.meta-chip{{background:var(--surface);border:1px solid var(--border);padding:6px 14px;border-radius:20px;font-size:12px;color:var(--text-dim);display:flex;align-items:center;gap:6px}}
.meta-chip .accent{{color:var(--accent);font-weight:600}}

/* ── Retrieval info ── */
.retrieval-info{{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:10px 16px;margin-bottom:16px;font-size:12px;color:var(--text-dim);display:flex;gap:16px;flex-wrap:wrap}}
.retrieval-info span{{display:flex;align-items:center;gap:4px}}

/* ── Content sections ── */
.section{{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:32px 36px;margin-bottom:20px}}
.section-title{{font-size:18px;font-weight:700;margin-bottom:16px;display:flex;align-items:center;gap:10px;padding-bottom:12px;border-bottom:1px solid var(--border)}}
.section-title .icon{{font-size:20px}}

/* ── Answer body ── */
.answer-body h1,.answer-body h2,.answer-body h3{{color:var(--text);margin:20px 0 10px;font-weight:700}}
.answer-body h1{{font-size:22px;color:var(--accent)}}
.answer-body h2{{font-size:18px}}
.answer-body h3{{font-size:16px}}
.answer-body p{{margin:10px 0;color:var(--text)}}
.answer-body ul,.answer-body ol{{margin:10px 0 10px 24px;color:var(--text)}}
.answer-body li{{margin:6px 0;line-height:1.6}}
.answer-body strong{{color:var(--text);font-weight:600}}
.answer-body blockquote{{border-left:3px solid var(--accent);padding:8px 16px;margin:12px 0;background:var(--accent-dim);border-radius:0 8px 8px 0;color:var(--text-dim)}}
.answer-body code{{background:var(--bg);padding:2px 6px;border-radius:4px;font-family:var(--mono);font-size:13px;color:var(--accent)}}
.answer-body hr{{border:none;border-top:1px solid var(--border);margin:24px 0}}

/* ── Sources table ── */
.sources-table{{width:100%;border-collapse:collapse;margin-top:8px;font-size:13px}}
.sources-table th{{background:var(--surface2);color:var(--text-dim);text-transform:uppercase;font-size:11px;letter-spacing:1px;padding:10px 12px;text-align:left;border-bottom:2px solid var(--border)}}
.sources-table td{{padding:10px 12px;border-bottom:1px solid var(--border);vertical-align:top}}
.sources-table tr:hover td{{background:var(--surface2)}}
.source-num{{background:var(--accent-dim);color:var(--accent);padding:2px 8px;border-radius:10px;font-weight:600;font-family:var(--mono);font-size:12px}}
.score{{font-family:var(--mono);color:var(--text-dim)}}
.tag{{background:var(--surface2);padding:2px 8px;border-radius:6px;font-size:11px;color:var(--text-dim)}}

/* ── Filters ── */
.filters{{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}}
.filter-chip{{background:var(--surface2);border:1px solid var(--border);padding:4px 12px;border-radius:16px;font-size:12px;color:var(--text-dim)}}

/* ── Aggregation badges & coverage ── */
.agg-badge{{padding:3px 10px;border-radius:12px;font-size:11px;font-weight:600;margin-left:8px}}
.agg-complete{{background:#4CAF5033;color:#4CAF50}}
.agg-partial{{background:#f4433633;color:#f44336}}
.coverage-bar{{height:8px;background:var(--surface2);border-radius:4px;overflow:hidden}}
.coverage-fill{{height:100%;background:linear-gradient(90deg,var(--accent),var(--green));border-radius:4px;transition:width 0.5s}}

/* ── Footer ── */
.report-footer{{text-align:center;padding:24px;color:var(--text-dim);font-size:12px;border-top:1px solid var(--border);margin-top:8px}}
.report-footer a{{color:var(--accent);text-decoration:none}}

/* ── Print ── */
@media print{{
  body{{background:#fff;color:#000;font-size:12px}}
  .report-header,.section{{border:none;box-shadow:none;background:#fff;page-break-inside:avoid}}
  .section{{padding:16px 0}}
  .report-header::before{{display:none}}
}}

/* ── Animations ── */
@keyframes fadeIn{{
  from{{opacity:0;transform:translateY(8px)}}
  to{{opacity:1;transform:translateY(0)}}
}}
.section,.report-header,.meta-bar{{animation:fadeIn 0.3s ease-out}}
</style>
</head>
<body>
<div class="container">

  <div class="report-header">
    <h1 class="report-title">{_esc(title)}</h1>
    <div class="mode-badge">{mode_info['icon']} {mode_info['label']}</div>
    <div class="query-box">
      <div class="query-label">Query</div>
      <div class="query-text">{_esc(query)}</div>
      {filter_html}
    </div>
  </div>

  <div class="meta-bar">
    <div class="meta-chip">⏱️ Generated in <span class="accent">{meta.get('generation_time', 'N/A')}s</span></div>
    <div class="meta-chip">📄 <span class="accent">{meta.get('total_hits', 0)}</span> docs retrieved</div>
    <div class="meta-chip">🔍 <span class="accent">{meta.get('deduplicated_hits', 0)}</span> after dedup</div>
    <div class="meta-chip">📝 <span class="accent">{meta.get('context_chars', 0):,}</span> chars context</div>
    <div class="meta-chip">🤖 <span class="accent">{_esc(meta.get('model', 'N/A'))}</span></div>
    <div class="meta-chip">🕐 {_esc(meta.get('timestamp', 'N/A'))}</div>
    <div class="meta-chip">📊 Index: <span class="accent">{_esc(meta.get('index', 'N/A'))}</span></div>
  </div>

  <div class="retrieval-info">
    <span>🔧 Strategy: <strong>{strategy_labels.get(strategy, strategy)}</strong></span>
    <span>📦 Doc coverage: <strong>{meta.get('selected_hits', 0)}/{meta.get('total_hits', 0)}</strong> selected for context</span>
    {"<span style='color:#f44336'>⚠ Enumeration query — aggregation used</span>" if meta.get('is_enumeration') else ""}
  </div>

  {completeness_html}
  {agg_html}

  <div class="section">
    <div class="section-title"><span class="icon">{mode_info['icon']}</span> Report</div>
    <div class="answer-body">
      {answer_html}
    </div>
  </div>

  <div class="section">
    <div class="section-title"><span class="icon">📎</span> Sources ({len(sources)} cited)</div>
    <table class="sources-table">
      <thead>
        <tr>
          <th>#</th>
          <th>Score</th>
          <th>Title</th>
          <th>Description</th>
          <th>Type</th>
          <th>Location</th>
          <th>Activity</th>
        </tr>
      </thead>
      <tbody>
        {sources_rows if sources else '<tr><td colspan="7" style="text-align:center;color:var(--text-dim);padding:32px">No sources found</td></tr>'}
      </tbody>
    </table>
  </div>

  <div class="report-footer">
    AI Summary Report Generator &middot; Powered by {_esc(meta.get('model', 'LLM'))} + {_esc(meta.get('embed_model', 'nomic-embed-text'))} &middot;
    <a href="#" onclick="window.print();return false;">Print / Save as PDF</a>
  </div>

</div>
</body>
</html>"""


def _markdown_to_html(text: str) -> str:
    """Simple markdown-to-HTML conversion for report rendering."""
    import re
    html = text

    # Headers
    html = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)

    # Bold / italic
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)

    # Inline code
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)

    # Blockquotes
    html = re.sub(r'^&gt; (.+)$', r'<blockquote>\1</blockquote>', html, flags=re.MULTILINE)

    # Horizontal rules
    html = re.sub(r'^---+$', r'<hr>', html, flags=re.MULTILINE)

    # Unordered lists
    html = re.sub(r'(^[-*] .+\n?)+', lambda m: '<ul>' + re.sub(r'^[-*] (.+)$', r'<li>\1</li>', m.group(0), flags=re.MULTILINE) + '</ul>\n', html, flags=re.MULTILINE)

    # Ordered lists
    html = re.sub(r'(^\d+\. .+\n?)+', lambda m: '<ol>' + re.sub(r'^\d+\. (.+)$', r'<li>\1</li>', m.group(0), flags=re.MULTILINE) + '</ol>\n', html, flags=re.MULTILINE)

    # Wrap bare lines in <p>
    lines = html.split('\n')
    out = []
    in_list = False
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('<'):
            line = f'<p>{stripped}</p>'
        out.append(line)
    html = '\n'.join(out)

    # Clean up empty paragraphs
    re_empty = re.compile(r'<p>\s*</p>')
    html = re_empty.sub('', html)

    return html


def _esc(s: str) -> str:
    """Escape HTML entities."""
    if not s:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")
