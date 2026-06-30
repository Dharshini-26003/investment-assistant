from __future__ import annotations
from datetime import datetime
from pathlib import Path
from fpdf import FPDF
from app.config import DISCLAIMER, REPORTS_DIR

def generate_pdf_report(summary: dict, period: str = "Monthly") -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{period.lower()}_report_{datetime.now():%Y%m%d_%H%M%S}.pdf"
    pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", "B", 16); pdf.cell(0, 10, "Investment Assistant Report", ln=True)
    pdf.set_font("Arial", size=11); pdf.cell(0, 8, f"Period: {period}", ln=True)
    for k in ["total_invested","current_value","unrealized_pl","return_pct","xirr","cagr","fund_count","diversification_score"]:
        pdf.cell(0, 8, f"{k.replace('_',' ').title()}: {summary.get(k, 0):,.2f}" if isinstance(summary.get(k,0),(int,float)) else f"{k}: {summary.get(k)}", ln=True)
    pdf.multi_cell(0, 8, f"Suggestions: Keep investing according to your plan, review diversification, costs, and risk yearly. {DISCLAIMER}")
    pdf.output(str(path)); return path
