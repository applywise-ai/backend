"""
PDF Generator service for creating PDF documents.
"""

from .pdf_generator import PDFGenerator, pdf_generator

# Convenience function for backward compatibility
def create_pdf_from_text(text: str, output_path: str, profile: dict) -> bool:
    """Create a PDF from text using the PDFGenerator."""
    return PDFGenerator.create_pdf_from_text(text, output_path, profile)

__all__ = ['PDFGenerator', 'pdf_generator', 'create_pdf_from_text'] 