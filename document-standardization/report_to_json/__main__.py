import argparse
import sys
from pathlib import Path

from report_to_json.api import process_report, standardize_report, ModelPipelineFailed
import logging

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")
    parser = argparse.ArgumentParser(description="Convert a security audit report (PDF) into master-schema JSON.")
    parser.add_argument("input_pdf", type=Path, help="Path to the input PDF report.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Directory to save the JSON output (default: outputs/)")
    parser.add_argument("--strict", action="store_true", help="Fail if the model cannot process the document (do not fall back).")
    args = parser.parse_args()

    if not args.input_pdf.is_file():
        print(f"Error: Input file not found: {args.input_pdf}", file=sys.stderr)
        sys.exit(1)

    print(f"Processing {args.input_pdf}...", file=sys.stderr)
    try:
        json_output = standardize_report(args.input_pdf, args.output_dir, strict=args.strict)
        print("Success!", file=sys.stderr)
        # We can either just print it to stdout, or let standardize_report save the file.
        # standardize_report already saves to the file and returns the JSON string.
        # We will just print the path to where it was saved.
        out_dir = args.output_dir if args.output_dir else Path("outputs")
        stem = args.input_pdf.stem
        import re
        safe_stem = re.sub(r"[^\w.\-]+", "_", stem).strip("._ ") or "document"
        print(f"Saved JSON output to {out_dir / safe_stem}.json", file=sys.stderr)
    except ModelPipelineFailed as e:
        print(f"Model Pipeline Failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Pipeline Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
