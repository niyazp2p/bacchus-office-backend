import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from app.models.office_lead import OfficeLead
from app.models.office_operations import OfficeOperationsClearance

def generate_operations_manifest_pdf(lead: OfficeLead, clearance: OfficeOperationsClearance) -> bytes:
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
    primary = colors.HexColor("#14120E")
    gold = colors.HexColor("#8E7626")
    cream = colors.HexColor("#FAF7F2")
    border = colors.HexColor("#E5E0D8")

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=primary,
        textTransform="uppercase",
    )
    sub_style = ParagraphStyle(
        "DocSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=gold,
        textTransform="uppercase",
    )
    label_style = ParagraphStyle(
        "Label",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#7A7366"),
        textTransform="uppercase",
    )
    val_style = ParagraphStyle(
        "Value",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=primary,
    )
    badge_style = ParagraphStyle(
        "Badge",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.white,
        alignment=1,
    )

    elements = []

    # 1. Header Grid
    header_data = [
        [
            Paragraph("BACCHUS SPIRITS GLOBAL OPERATIONS DESK", title_style),
            Paragraph("DISPATCH CLEARED", badge_style),
        ],
        [
            Paragraph("OFFICIAL INSTITUTIONAL DISPATCH MANIFEST & COMPLIANCE SIGN-OFF", sub_style),
            Paragraph(f"PERMIT: {clearance.dispatch_permit_no or 'N/A'}", badge_style),
        ]
    ]
    header_tbl = Table(header_data, colWidths=[380, 160])
    header_tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor("#065F46")),  # Emerald
        ('BACKGROUND', (1, 1), (1, 1), primary),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(header_tbl)
    elements.append(Spacer(1, 15))

    # 2. Consignment & Institutional Profile
    specs = [
        [Paragraph("Lead Reference Code", label_style), Paragraph(lead.lead_code, val_style)],
        [Paragraph("Institutional Consignee", label_style), Paragraph(lead.company_name, val_style)],
        [Paragraph("Primary Liaison", label_style), Paragraph(f"{lead.contact_name} ({lead.email})", val_style)],
        [Paragraph("Destination Corridor", label_style), Paragraph(f"{lead.state + ', ' if lead.state else ''}{lead.country}", val_style)],
        [Paragraph("Commercial Engagement", label_style), Paragraph(lead.commercial_model.value, val_style)],
        [Paragraph("Locked Margin Floor", label_style), Paragraph(f"{clearance.locked_margin_pct or 0.0}% Gross Realization", val_style)],
        [Paragraph("Locked Allocation", label_style), Paragraph(f"{clearance.locked_annual_cases or 0} Cases / Year", val_style)],
        [Paragraph("Statutory Clearance Timestamp", label_style), Paragraph(clearance.cleared_at.strftime("%B %d, %Y - %H:%M UTC") if clearance.cleared_at else "N/A", val_style)],
    ]
    specs_tbl = Table(specs, colWidths=[180, 360])
    specs_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), cream),
        ('GRID', (0, 0), (-1, -1), 0.5, border),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(specs_tbl)
    elements.append(Spacer(1, 15))

    # 3. Logistics & Manifest Details
    elements.append(Paragraph("PHYSICAL DISPATCH & CARRIER ALLOCATION", sub_style))
    elements.append(Spacer(1, 5))

    logistics_data = [
        [Paragraph("Authorized Logistics Carrier", label_style), Paragraph(clearance.transporter_carrier or "N/A", val_style)],
        [Paragraph("Container / Vehicle Number", label_style), Paragraph(clearance.vehicle_container_no or "N/A", val_style)],
        [Paragraph("Customs Seal Number", label_style), Paragraph(clearance.customs_seal_no or "N/A", val_style)],
        [Paragraph("Scheduled Dispatch Date", label_style), Paragraph(clearance.estimated_dispatch_date.strftime("%B %d, %Y") if clearance.estimated_dispatch_date else "N/A", val_style)],
        [Paragraph("Excise License Number", label_style), Paragraph(clearance.excise_license_no or "Verified State Registry", val_style)],
        [Paragraph("Attestation Verification", label_style), Paragraph("COO, MSDS, Bonded Warehouse & Exclusivity Verified", val_style)],
    ]
    logistics_tbl = Table(logistics_data, colWidths=[180, 360])
    logistics_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, border),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(logistics_tbl)
    elements.append(Spacer(1, 15))

    # 4. Operations Clearance Remarks
    elements.append(Paragraph("OPERATIONS HEAD EXECUTIVE DIRECTIVE", sub_style))
    elements.append(Spacer(1, 5))
    notes_tbl = Table([[Paragraph(clearance.clearance_notes or "Consignment approved without conditions.", val_style)]], colWidths=[540])
    notes_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.5, border),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(notes_tbl)
    elements.append(Spacer(1, 25))

    # 5. Formal Legal Sign-Off Bar
    footer_text = Paragraph(
        "BACCHUS DISTILLERY CENTRAL DISPATCH GATEWAY • EXCISE STATUTORY ATTESTATION • STRICT CHAIN OF CUSTODY",
        ParagraphStyle("Foot", fontName="Helvetica-Bold", fontSize=8, textColor=gold, alignment=1)
    )
    elements.append(footer_text)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()