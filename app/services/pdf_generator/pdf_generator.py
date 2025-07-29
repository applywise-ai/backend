"""
PDF generation service using ReportLab
"""

import logging
import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import PageTemplate, Frame
import datetime

logger = logging.getLogger(__name__)


class PDFGenerator:
    """Service for generating PDF documents from text and other content"""
    
    @staticmethod
    def create_pdf_from_text(text: str, output_path: str, profile: dict) -> bool:
        """
        Create a PDF cover letter with a modern header (name + contact icons) and styled text.
        """
        try:
            styles = getSampleStyleSheet()
            normal_style = styles['Normal']

            # Modern cover letter body style
            body_style = ParagraphStyle(
                'Body',
                parent=normal_style,
                fontName='Helvetica',
                fontSize=12,
                leading=15,
                spaceAfter=12
            )

            # Build body content
            story = []

            # Add date
            today = datetime.date.today().strftime("%B %d, %Y")
            story.append(Spacer(1, 36))
            story.append(Paragraph(today, body_style))
            story.append(Spacer(1, 12))

            # Parse and add body content
            if 'Sincerely,' in text:
                body, _, _ = text.partition('Sincerely,')
                closing = "Sincerely,\n" + (profile.get('fullName') or '').strip()
            else:
                body = text
                closing = ''

            for para in body.strip().split('\n\n'):
                para = para.strip().replace('\n', ' ')
                if para:
                    story.append(Paragraph(para, body_style))
                    story.append(Spacer(1, 6))

            if closing:
                for line in closing.split('\n'):
                    story.append(Paragraph(line.strip(), body_style))

            # Create the document with a custom PageTemplate to draw the header
            doc = SimpleDocTemplate(output_path, pagesize=letter,
                                    rightMargin=72, leftMargin=72,
                                    topMargin=144, bottomMargin=72)

            def draw_header(canvas, doc):
                canvas.saveState()

                # Gray bar background
                canvas.setFillColor(colors.lightgrey)
                canvas.rect(0, letter[1] - 90, letter[0], 90, fill=1, stroke=0)

                # Centered name
                canvas.setFont("Helvetica-Bold", 20)
                name = profile.get('fullName')
                canvas.setFillColor(colors.black)
                canvas.drawCentredString(letter[0] / 2, letter[1] - 40, name)

                canvas.setFont("Helvetica", 10)

                icon_size = 12
                gap = 12  # space between icon-text pairs
                y = letter[1] - 65

                # Get the directory where this script is located
                current_dir = os.path.dirname(os.path.abspath(__file__))
                icons_dir = os.path.join(current_dir, 'icons')

                # List of (icon filename, profile key)
                contact_fields = [
                    ("envelope-solid.png", "email"),
                    ("linkedin-brands.png", "linkedin"),
                    ("phone-solid.png", "phoneNumber"),
                    ("location-dot-solid.png", "currentLocation")
                ]

                # First, measure total width of all items
                items = []
                for icon_file, profile_key in contact_fields:
                    value = profile.get(profile_key)
                    if value:
                        text_width = stringWidth(value, "Helvetica", 10)
                        total_width = icon_size + 4 + text_width  # icon + spacing + text
                        icon_path = os.path.join(icons_dir, icon_file)
                        items.append({
                            "icon": icon_path,
                            "text": value,
                            "width": total_width
                        })

                # Calculate total content width
                total_line_width = sum(item['width'] for item in items) + gap * (len(items) - 1)

                # Starting x to center the whole line
                start_x = (letter[0] - total_line_width) / 2

                # Draw each item
                x = start_x
                for item in items:
                    try:
                        canvas.drawImage(item['icon'], x, y - 3, width=icon_size-2, height=icon_size, mask='auto')
                    except Exception as e:
                        logger.warning(f"Failed to load icon {item['icon']}: {e}")
                    canvas.drawString(x + icon_size + 4, y, item['text'])
                    x += item['width'] + gap

                canvas.restoreState()

            # Add custom header to the page
            doc.addPageTemplates([PageTemplate(id='CoverLetter', onPage=draw_header, frames=[
                Frame(72, 72, letter[0] - 144, letter[1] - 144, id='normal')])])

            # Build the PDF
            doc.build(story)
            logger.info(f"PDF created successfully: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Error creating PDF: {e}")
            return False

# Create a global instance for easy import
pdf_generator = PDFGenerator() 