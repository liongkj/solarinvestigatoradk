from io import BytesIO

from google.adk.agents.callback_context import CallbackContext
from google.genai import types
from xhtml2pdf import pisa


async def save_generated_report(callback_context: CallbackContext):
    """Saves generated PDF report bytes as an artifact.
    Parameters
    bytes report_bytes : the pdf report bytes
    """
    html_content = callback_context.state.get("final_html")

    try:
        # Convert HTML to PDF in memory
        pdf_bytes_io = BytesIO()
        error = pisa.CreatePDF(src=html_content, dest=pdf_bytes_io)

        if error:
            print("Error during PDF generation")
            return

        pdf_bytes = pdf_bytes_io.getvalue()
        callback_context.state["report_bytes"] = pdf_bytes

        report_artifact = types.Part.from_bytes(
            data=pdf_bytes, mime_type="application/pdf"
        )
        filename = "generated_report.pdf"

        try:
            version = await callback_context.save_artifact(
                filename=filename, artifact=report_artifact
            )
            print(
                f"Successfully saved Python artifact '{filename}' as version {version}."
            )
        except ValueError as e:
            print(
                f"Error saving Python artifact: {e}. Is ArtifactService configured in Runner?"
            )
        except Exception as e:
            print(f"An unexpected error occurred during Python artifact save: {e}")

    except Exception as e:
        print(f"PDF generation error: {e}")


def save_generated_report_local(callback_context: CallbackContext):
    """Saves generated PDF report bytes locally as a file."""
    html_content = callback_context.state.get("final_html")

    pdf_bytes_io = BytesIO()
    error = pisa.CreatePDF(src=html_content, dest=pdf_bytes_io)

    if error:
        print("Error during PDF generation")
    else:
        pdf_bytes = pdf_bytes_io.getvalue()

        # Write to file
        with open("generated_report.pdf", "wb") as f:
            f.write(pdf_bytes)
        print("PDF saved as 'generated_report.pdf'")
