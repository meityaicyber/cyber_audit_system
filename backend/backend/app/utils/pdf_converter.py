"""
PDF Conversion Utility
----------------------
Converts .docx and .txt files to PDF using LibreOffice headless.
PDF files pass through unchanged.
"""

import io
import os
import subprocess
import tempfile
import logging

logger = logging.getLogger(__name__)


def convert_to_pdf(file_bytes: bytes, extension: str, original_filename: str) -> bytes:
    """
    Convert a file to PDF format.
    
    - .pdf files: returned as-is
    - .docx / .txt files: converted using LibreOffice headless
    
    Returns the PDF file bytes.
    Raises ValueError if conversion fails.
    """
    if extension == ".pdf":
        return file_bytes

    if extension not in (".docx", ".txt"):
        raise ValueError(f"Unsupported extension for PDF conversion: {extension}")

    return _convert_with_libreoffice(file_bytes, extension, original_filename)


def _convert_with_libreoffice(file_bytes: bytes, extension: str, original_filename: str) -> bytes:
    """
    Use LibreOffice headless to convert a file to PDF.
    Works for .docx, .txt, and many other formats.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write the input file
        input_filename = f"input{extension}"
        input_path = os.path.join(tmpdir, input_filename)
        with open(input_path, "wb") as f:
            f.write(file_bytes)

        # Run LibreOffice conversion
        try:
            result = subprocess.run(
                [
                    "libreoffice",
                    "--headless",
                    "--norestore",
                    "--convert-to", "pdf",
                    "--outdir", tmpdir,
                    input_path,
                ],
                capture_output=True,
                text=True,
                timeout=60,  # 60 second timeout
            )

            if result.returncode != 0:
                logger.error(
                    f"LibreOffice conversion failed for '{original_filename}': "
                    f"stderr={result.stderr}, stdout={result.stdout}"
                )
                raise ValueError(
                    f"PDF conversion failed for '{original_filename}': {result.stderr or 'Unknown error'}"
                )

        except subprocess.TimeoutExpired:
            raise ValueError(
                f"PDF conversion timed out for '{original_filename}'"
            )

        # Read the output PDF
        output_path = os.path.join(tmpdir, "input.pdf")
        if not os.path.exists(output_path):
            # LibreOffice might name it differently
            pdf_files = [f for f in os.listdir(tmpdir) if f.endswith(".pdf")]
            if not pdf_files:
                raise ValueError(
                    f"PDF conversion produced no output for '{original_filename}'"
                )
            output_path = os.path.join(tmpdir, pdf_files[0])

        with open(output_path, "rb") as f:
            pdf_bytes = f.read()

        if len(pdf_bytes) == 0:
            raise ValueError(
                f"PDF conversion produced empty file for '{original_filename}'"
            )

        logger.info(
            f"Converted '{original_filename}' ({extension}) to PDF: "
            f"{len(file_bytes)} bytes -> {len(pdf_bytes)} bytes"
        )
        return pdf_bytes
