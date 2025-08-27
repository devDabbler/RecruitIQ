import argparse
import json
import logging
import os
import sys

# Ensure the project root is in the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, project_root)

from backend.utils.resume_parsing.nebius_ai_parser import NebiusAIParser

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """
    Command-line tool to parse a single resume file and print the structured output.
    """
    parser = argparse.ArgumentParser(description='Parse a resume file and extract structured information.')
    parser.add_argument('--file', type=str, required=True, help='The absolute path to the resume file.')
    parser.add_argument('--use-ocr', action='store_true', help='Enable OCR for PDF files. Default is enabled.')
    parser.add_argument('--no-ocr', action='store_false', dest='use_ocr', help='Disable OCR for PDF files.')
    parser.set_defaults(use_ocr=True)

    args = parser.parse_args()

    if not os.path.exists(args.file):
        logger.error(f"File not found: {args.file}")
        sys.exit(1)

    logger.info(f"Initializing NebiusAIParser (OCR enabled: {args.use_ocr})")
    resume_parser = NebiusAIParser(use_ocr=args.use_ocr)

    logger.info(f"Parsing file: {args.file}")
    extracted_data = resume_parser.parse(args.file)

    # Pretty-print the JSON output
    print(json.dumps(extracted_data, indent=2))

if __name__ == '__main__':
    main()
