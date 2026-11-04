"""Report-to-JSON: convert security audit reports (PDF/DOCX) into master-schema JSON.

Integration entry point::

    from report_to_json import standardize_report
    response = standardize_report("report.pdf")   # the standardised JSON, as text
"""

__version__ = "4.0.0"

_API = ("standardize_report", "process_report", "ModelPipelineFailed", "close")
__all__ = ["__version__", *_API]


def __getattr__(name):
    # Loaded on first use so importing the package stays light (the GUI launcher and
    # the DOCX conversion subprocess import it without needing the whole pipeline).
    if name in _API:
        from . import api

        return getattr(api, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
