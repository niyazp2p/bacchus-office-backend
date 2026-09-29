import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from app.models.office_lead import OfficeLead

def generate_lead_dossier_pdf(lead: OfficeLead) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Custom Brand Typography
    primary_color = colors.HexColor("#14120E")
    gold_color = colors.HexColor("#8E7626")
    bg_light = colors.HexColor("#FAF7F2")
    border_color = colors.HexColor("#E5E0D8")

    title_style = ParagraphStyle(
        "BrandTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=primary_color,
        textTransform="uppercase",
    )
    subtitle_style = ParagraphStyle(
        "BrandSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=gold_color,
        textTransform="uppercase",
    )
    label_style = ParagraphStyle(
        "FieldLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#7A7366"),
        textTransform="uppercase",
    )
    val_style = ParagraphStyle(
        "FieldVal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor=primary_color,
    )
    badge_style = ParagraphStyle(
        "BadgeText",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        textColor=colors.white,
        alignment=1,
    )

    elements = []

    # 1. Header Grid
    header_data = [
        [
            Paragraph("BACCHUS SPIRITS GLOBAL OPERATIONS", title_style),
            Paragraph(f"{lead.tier.value} PRIORITY", badge_style),
        ],
        [
            Paragraph("CONFIDENTIAL INSTITUTIONAL LEAD DOSSIER", subtitle_style),
            Paragraph(f"SCORE: {lead.score}/100", badge_style),
        ]
    ]
    header_table = Table(header_data, colWidths=[380, 160])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (1, 0), (1, 0), gold_color),
        ('BACKGROUND', (1, 1), (1, 1), primary_color),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 15))

    # 2. Key-Value Specifications
    lead_specs = [
        [Paragraph("Lead Reference Code", label_style), Paragraph(lead.lead_code, val_style)],
        [Paragraph("Corporate Entity", label_style), Paragraph(lead.company_name, val_style)],
        [Paragraph("Primary Contact", label_style), Paragraph(lead.contact_name, val_style)],
        [Paragraph("Email Address", label_style), Paragraph(lead.email, val_style)],
        [Paragraph("Direct Phone", label_style), Paragraph(lead.phone or "N/A", val_style)],
        [Paragraph("Territory / Location", label_style), Paragraph(f"{lead.state + ', ' if lead.state else ''}{lead.country}", val_style)],
        [Paragraph("Commercial Model", label_style), Paragraph(lead.commercial_model.value, val_style)],
        [Paragraph("Volume Projection", label_style), Paragraph(lead.volume_estimate or "Not Specified", val_style)],
        [Paragraph("Lifecycle Stage", label_style), Paragraph(lead.status.value, val_style)],
        [Paragraph("Ingested At", label_style), Paragraph(lead.created_at.strftime("%B %d, %Y - %H:%M UTC"), val_style)],
    ]
    specs_table = Table(lead_specs, colWidths=[180, 360])
    specs_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg_light),
        ('GRID', (0, 0), (-1, -1), 0.5, border_color),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(specs_table)
    elements.append(Spacer(1, 15))

    # 3. Operational Remarks Dossier
    elements.append(Paragraph("TELECALLER & BDM OPERATIONAL NOTES", subtitle_style))
    elements.append(Spacer(1, 5))

    remarks_data = [
        [
            Paragraph("Telecaller Remarks", label_style),
            Paragraph(lead.caller_remarks or "No verification notes logged yet.", val_style)
        ],
        [
            Paragraph("BDM Assessment", label_style),
            Paragraph(lead.bdm_remarks or "No BDM remarks logged yet.", val_style)
        ]
    ]
    remarks_table = Table(remarks_data, colWidths=[180, 360])
    remarks_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, border_color),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(remarks_table)
    elements.append(Spacer(1, 30))

    # 4. Legal / Audit Footer
    footer_text = Paragraph(
        "CONFIDENTIAL • BACCHUS DISTILLERY OFFICE ENGINE • SYSTEM GENERATED DOCUMENT • LEGAL PROTECTED",
        ParagraphStyle(
            "FooterStyle",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=gold_color,
            alignment=1
        )
    )
    elements.append(footer_text)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()