from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .optimizer import Combination
from .value import minimum_acceptable_odds


@dataclass(frozen=True)
class DailyReport:
    report_date: str
    generated_at: datetime
    best_2x: Combination | None
    best_3x: Combination | None
    scanned_matches: int
    scanned_markets: int
    valid_candidates: int


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    text: str
    html: str


def _combo_view(combo: Combination | None) -> dict | None:
    if combo is None:
        return None
    min_odds = minimum_acceptable_odds(combo.joint_probability, 0.05)
    return {
        "legs": [
            {
                "selection": leg.selection,
                "fixture": leg.fixture_key,
                "odds": leg.decimal_odds,
                "probability": leg.model_probability,
                "pattern_strength": leg.pattern_strength,
                "data_quality": leg.data_quality,
                "uncertainty": leg.uncertainty,
                "ev": leg.ev,
                "fair_odds": 1.0 / leg.model_probability,
            }
            for leg in combo.legs
        ],
        "total_odds": combo.total_odds,
        "joint_probability": combo.joint_probability,
        "risk": 1.0 - combo.joint_probability,
        "safety_rating": combo.safety_rating,
        "ev": combo.expected_value,
        "minimum_odds": min_odds,
        "avg_data_quality": sum(x.data_quality for x in combo.legs) / len(combo.legs),
        "avg_pattern_strength": sum(x.pattern_strength for x in combo.legs) / len(combo.legs),
        "avg_uncertainty": sum(x.uncertainty for x in combo.legs) / len(combo.legs),
    }


def render_daily_report(report: DailyReport) -> RenderedEmail:
    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    context = {
        "report": report,
        "two": _combo_view(report.best_2x),
        "three": _combo_view(report.best_3x),
    }
    text = env.get_template("daily_email.txt.j2").render(**context)
    html = env.get_template("daily_email.html.j2").render(**context)
    return RenderedEmail(
        subject=f"Daily Model Picks — {report.report_date}",
        text=text.strip() + "\n",
        html=html,
    )
