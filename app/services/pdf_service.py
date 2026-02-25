import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm, mm
from reportlab.lib.colors import HexColor, white, Color
from datetime import datetime
from flask import current_app


class PDFService:
    # ── Brand Colors ────────────────────────────────────
    PRIMARY    = HexColor("#0F8C55")
    PRIMARY_BG = HexColor("#F0FDF4")
    DARK       = HexColor("#111827")
    GRAY       = HexColor("#6B7280")
    LIGHT_GRAY = HexColor("#9CA3AF")
    BORDER     = HexColor("#E5E7EB")
    PAGE_BG    = HexColor("#FAFAFA")
    ACCENT     = HexColor("#065F46")

    @staticmethod
    def generate_invoice_pdf(invoice_data):
        """Generate a premium-branded PDF invoice."""
        static_folder = os.path.join(current_app.root_path, 'static', 'invoices')
        os.makedirs(static_folder, exist_ok=True)

        filename = f"{invoice_data['reference']}.pdf"
        filepath = os.path.join(static_folder, filename)
        S = PDFService  # shorthand for colors

        c = canvas.Canvas(filepath, pagesize=A4)
        c.setTitle(f"Invoice {invoice_data['reference']}")
        w, h = A4  # 595.28, 841.89

        merchant = invoice_data.get('merchant', {})
        customer = invoice_data.get('customer', {})
        items    = invoice_data.get('items', [])

        # ── Page background ─────────────────────────────
        c.setFillColor(white)
        c.rect(0, 0, w, h, fill=1, stroke=0)

        # ── Top accent strip ────────────────────────────
        c.setFillColor(S.PRIMARY)
        c.rect(0, h - 8*mm, w, 8*mm, fill=1, stroke=0)

        # ── Header stripe (dark green area) ─────────────
        c.setFillColor(S.ACCENT)
        c.rect(0, h - 8*mm - 3.5*cm, w, 3.5*cm, fill=1, stroke=0)

        # Logo or Business name (inside the dark area)
        logo_url = merchant.get('logo_url')
        has_logo = False
        temp_logo_path = None

        if logo_url:
            try:
                if logo_url.startswith('http'):
                    import requests
                    import tempfile
                    response = requests.get(logo_url, stream=True, timeout=10)
                    if response.status_code == 200:
                        ext = '.png' if 'png' in logo_url.lower() else '.jpg'
                        fd, temp_logo_path = tempfile.mkstemp(suffix=ext)
                        with os.fdopen(fd, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=1024):
                                f.write(chunk)
                        c.drawImage(temp_logo_path, 2*cm, h - 8*mm - 3.0*cm,
                                    width=2.5*cm, height=2.5*cm,
                                    preserveAspectRatio=True, mask='auto')
                        has_logo = True
            except Exception as e:
                print(f"Logo error: {e}")

        # Business name
        name_x = 5*cm if has_logo else 2*cm
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 20)
        c.drawString(name_x, h - 8*mm - 1.8*cm, merchant.get('business_name', 'INVOICE'))

        # Business contact info below name
        c.setFont("Helvetica", 8)
        c.setFillColor(HexColor("#A7F3D0"))  # light green for contrast
        info_y = h - 8*mm - 2.5*cm
        contact_parts = []
        if merchant.get('phone'):
            contact_parts.append(merchant['phone'])
        if merchant.get('address'):
            contact_parts.append(merchant['address'])
        if contact_parts:
            c.drawString(name_x, info_y, "  |  ".join(contact_parts))

        # "INVOICE" badge (right side)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 28)
        c.drawRightString(w - 2*cm, h - 8*mm - 1.8*cm, "INVOICE")

        # ── Reference / Date strip ──────────────────────
        strip_y = h - 8*mm - 3.5*cm - 1.2*cm
        c.setFillColor(S.PRIMARY_BG)
        c.rect(0, strip_y - 0.3*cm, w, 1.5*cm, fill=1, stroke=0)

        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(S.PRIMARY)
        c.drawString(2*cm, strip_y + 0.5*cm, f"REF: {invoice_data['reference']}")

        c.setFont("Helvetica", 8)
        c.setFillColor(S.GRAY)
        c.drawString(8*cm, strip_y + 0.5*cm, f"Issued: {invoice_data['date_issued']}")
        c.drawString(13*cm, strip_y + 0.5*cm, f"Due: {invoice_data['due_date']}")

        # Status badge
        c.setFillColor(S.PRIMARY)
        badge_x = w - 4*cm
        c.roundRect(badge_x, strip_y + 0.2*cm, 2*cm, 0.8*cm, 4, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(badge_x + 1*cm, strip_y + 0.45*cm, "PENDING")

        # ── Bill To / From section ──────────────────────
        section_y = strip_y - 2.2*cm

        # FROM
        c.setFillColor(S.LIGHT_GRAY)
        c.setFont("Helvetica", 7)
        c.drawString(2*cm, section_y + 1.2*cm, "FROM")
        c.setFillColor(S.DARK)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(2*cm, section_y + 0.5*cm, merchant.get('business_name', ''))
        c.setFont("Helvetica", 8)
        c.setFillColor(S.GRAY)
        fy = section_y
        if merchant.get('address'):
            c.drawString(2*cm, fy, merchant['address'])
            fy -= 0.4*cm
        if merchant.get('phone'):
            c.drawString(2*cm, fy, merchant['phone'])

        # BILL TO
        c.setFillColor(S.LIGHT_GRAY)
        c.setFont("Helvetica", 7)
        c.drawString(11*cm, section_y + 1.2*cm, "BILL TO")
        c.setFillColor(S.DARK)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(11*cm, section_y + 0.5*cm, customer.get('name', 'Customer'))
        c.setFont("Helvetica", 8)
        c.setFillColor(S.GRAY)
        cy = section_y
        if customer.get('phone'):
            c.drawString(11*cm, cy, customer['phone'])
            cy -= 0.4*cm
        if customer.get('email'):
            c.drawString(11*cm, cy, customer['email'])

        # ── Separator line ──────────────────────────────
        sep_y = section_y - 1.2*cm
        c.setStrokeColor(S.BORDER)
        c.setLineWidth(0.5)
        c.line(2*cm, sep_y, w - 2*cm, sep_y)

        # ── Items Table ─────────────────────────────────
        table_y = sep_y - 0.8*cm

        # Table header
        c.setFillColor(S.PRIMARY)
        c.roundRect(2*cm, table_y - 0.1*cm, w - 4*cm, 0.9*cm, 4, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(2.5*cm, table_y + 0.15*cm, "ITEM DESCRIPTION")
        c.drawCentredString(11.5*cm, table_y + 0.15*cm, "QTY")
        c.drawCentredString(14*cm, table_y + 0.15*cm, "UNIT PRICE")
        c.drawRightString(w - 2.5*cm, table_y + 0.15*cm, "AMOUNT")

        # Table rows
        row_y = table_y - 1.2*cm
        c.setFont("Helvetica", 9)
        subtotal = 0

        for i, item in enumerate(items):
            item_total = item.get('total_price', item['quantity'] * item['unit_price'])
            subtotal += item_total

            # Alternate row background
            if i % 2 == 0:
                c.setFillColor(HexColor("#F9FAFB"))
                c.rect(2*cm, row_y - 0.3*cm, w - 4*cm, 0.9*cm, fill=1, stroke=0)

            c.setFillColor(S.DARK)
            c.setFont("Helvetica", 9)
            c.drawString(2.5*cm, row_y, item['description'])

            c.setFillColor(S.GRAY)
            c.drawCentredString(11.5*cm, row_y, str(item['quantity']))
            c.drawCentredString(14*cm, row_y, f"\u20a6{item['unit_price']:,.2f}")

            c.setFillColor(S.DARK)
            c.setFont("Helvetica-Bold", 9)
            c.drawRightString(w - 2.5*cm, row_y, f"\u20a6{item_total:,.2f}")

            row_y -= 1*cm
            if row_y < 6*cm:
                c.showPage()
                row_y = h - 3*cm

        # ── Totals Section ──────────────────────────────
        totals_y = row_y - 0.8*cm

        # Divider
        c.setStrokeColor(S.BORDER)
        c.setLineWidth(0.5)
        c.line(11*cm, totals_y + 0.5*cm, w - 2*cm, totals_y + 0.5*cm)

        # Subtotal
        c.setFont("Helvetica", 9)
        c.setFillColor(S.GRAY)
        c.drawString(11*cm, totals_y - 0.2*cm, "Subtotal")
        c.setFillColor(S.DARK)
        c.drawRightString(w - 2.5*cm, totals_y - 0.2*cm, f"\u20a6{subtotal:,.2f}")

        # Tax
        tax = subtotal * 0.075
        c.setFillColor(S.GRAY)
        c.drawString(11*cm, totals_y - 0.9*cm, "VAT (7.5%)")
        c.setFillColor(S.DARK)
        c.drawRightString(w - 2.5*cm, totals_y - 0.9*cm, f"\u20a6{tax:,.2f}")

        # Divider before total
        c.setStrokeColor(S.BORDER)
        c.line(11*cm, totals_y - 1.3*cm, w - 2*cm, totals_y - 1.3*cm)

        # Grand Total (green pill)
        grand_total = subtotal + tax
        gt_y = totals_y - 2.2*cm
        c.setFillColor(S.PRIMARY)
        c.roundRect(10.5*cm, gt_y - 0.15*cm, w - 10.5*cm - 2*cm, 1.1*cm, 6, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(11*cm, gt_y + 0.2*cm, "TOTAL DUE")
        c.setFont("Helvetica-Bold", 14)
        c.drawRightString(w - 2.5*cm, gt_y + 0.15*cm, f"\u20a6{grand_total:,.2f}")

        # ── Payment Details Box (bottom left) ───────────
        if merchant.get('bank_name') and merchant.get('account_number'):
            pay_y = 3.5*cm
            # Box background
            c.setFillColor(S.PRIMARY_BG)
            c.roundRect(2*cm, pay_y, 8*cm, 3*cm, 6, fill=1, stroke=0)
            # Left accent bar
            c.setFillColor(S.PRIMARY)
            c.roundRect(2*cm, pay_y, 0.3*cm, 3*cm, 2, fill=1, stroke=0)

            c.setFillColor(S.PRIMARY)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(2.8*cm, pay_y + 2.3*cm, "PAYMENT DETAILS")

            c.setFillColor(S.DARK)
            c.setFont("Helvetica", 8)
            c.drawString(2.8*cm, pay_y + 1.6*cm, f"Bank:  {merchant['bank_name']}")
            c.drawString(2.8*cm, pay_y + 1.0*cm, f"Account No:  {merchant['account_number']}")
            if merchant.get('account_name'):
                c.drawString(2.8*cm, pay_y + 0.4*cm, f"Account Name:  {merchant['account_name']}")

        # ── Thank you note (bottom right) ───────────────
        c.setFillColor(S.GRAY)
        c.setFont("Helvetica-Oblique", 9)
        c.drawRightString(w - 2*cm, 4.5*cm, "Thank you for your business!")

        # ── Footer ──────────────────────────────────────
        # Bottom accent bar
        c.setFillColor(S.PRIMARY)
        c.rect(0, 0, w, 5*mm, fill=1, stroke=0)

        # Powered by
        c.setFillColor(S.LIGHT_GRAY)
        c.setFont("Helvetica", 7)
        c.drawCentredString(w / 2, 8*mm, "Generated by BizFlow  \u2022  bizflow.app")

        # ── Save ────────────────────────────────────────
        try:
            c.save()
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise e

        # Cleanup temp logo
        if temp_logo_path and os.path.exists(temp_logo_path):
            try:
                os.remove(temp_logo_path)
            except:
                pass

        return f"/static/invoices/{filename}"
