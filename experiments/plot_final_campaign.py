"""Dependency-free SVG plots for condition-stratified final campaign summaries."""
from __future__ import annotations
import csv
import re
from pathlib import Path
from xml.sax.saxutils import escape


PALETTE = ("#386cb0", "#fdb462", "#7fc97f", "#beaed4", "#fdc086")


def _safe(value):
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value)).strip("_")


def write_bar_chart(rows, metric, title, path):
    values = [(row["policy"], float(row[f"{metric}_mean"]))
              for row in rows if row.get(f"{metric}_mean") not in ("", None)]
    if not values:
        return False
    width, height = 900, 520
    left, right, top, bottom = 90, 40, 80, 110
    plot_w, plot_h = width - left - right, height - top - bottom
    maximum = max(value for _, value in values) or 1.0
    scale_max = maximum * 1.15
    bar_gap = plot_w / len(values)
    bar_w = bar_gap * .55
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{width/2}" y="38" text-anchor="middle" font-size="22" font-family="sans-serif">{escape(title)}</text>',
        f'<line x1="{left}" y1="{top+plot_h}" x2="{left+plot_w}" y2="{top+plot_h}" stroke="#333"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_h}" stroke="#333"/>',
    ]
    for tick in range(5):
        value = scale_max * tick / 4
        y = top + plot_h - plot_h * tick / 4
        elements.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left+plot_w}" y2="{y:.1f}" stroke="#dddddd"/>')
        elements.append(f'<text x="{left-12}" y="{y+5:.1f}" text-anchor="end" font-size="12" fill="#333">{value:.2f}</text>')
    for index, (policy, value) in enumerate(values):
        x = left + index * bar_gap + (bar_gap - bar_w) / 2
        bar_h = plot_h * value / scale_max
        y = top + plot_h - bar_h
        color = PALETTE[index % len(PALETTE)]
        elements.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{color}"/>')
        elements.append(f'<text x="{x+bar_w/2:.1f}" y="{top+plot_h+24}" text-anchor="middle" font-size="12" fill="#222">{escape(policy)}</text>')
        elements.append(f'<text x="{x+bar_w/2:.1f}" y="{max(top+12,y-8):.1f}" text-anchor="middle" font-size="11" fill="#222">{value:.2f}</text>')
    elements.append('</svg>')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(elements), encoding="utf-8")
    return True


def plot_summary(summary_csv, output_dir):
    with Path(summary_csv).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    groups = {}
    for row in rows:
        key = (row["scenario"], row["condition"], row["initial_path"])
        groups.setdefault(key, []).append(row)
    output_dir = Path(output_dir)
    written = []
    for (scenario, condition, initial), items in groups.items():
        stem = "__".join(map(_safe, (scenario, condition, initial)))
        for metric, label in (
            ("tcp_app_rtt_p99_ms", "TCP application RTT p99 (ms)"),
            ("aggregate_goodput_mbps", "Aggregate goodput (Mbps)"),
            ("path_changes_per_minute", "Path changes per minute"),
            ("jain_fairness", "Jain fairness (concurrent windows)"),
        ):
            target = output_dir / f"{stem}__{metric}.svg"
            if write_bar_chart(items, metric, f"{scenario} / {condition} / {initial} — {label}", target):
                written.append(str(target))
    return written
