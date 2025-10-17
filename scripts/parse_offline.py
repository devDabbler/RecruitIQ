import argparse
import json
import os
import sys
from pathlib import Path
import traceback


def main():
    parser = argparse.ArgumentParser(description="Offline parse a resume PDF/DOCX/TXT and save JSON output.")
    parser.add_argument("file", help="Path to resume file")
    parser.add_argument("--out", dest="out", help="Output JSON path (default: <stem>_parsed.json)")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}")
        sys.exit(2)

    # Lazy import to speed CLI start
    from backend.utils.resume_parsing.nebius_ai_parser import NebiusAIParser
    import asyncio

    async def run():
        print("[parse_offline] Starting...", flush=True)
        print(f"[parse_offline] OPENROUTER_ENABLED={os.environ.get('OPENROUTER_ENABLED')} OPENROUTER_DEFAULT_MODEL={os.environ.get('OPENROUTER_DEFAULT_MODEL')}\n", flush=True)
        try:
            parser = NebiusAIParser(use_ocr=True)
            data = await parser.parse_file(str(file_path))
            out_path = Path(args.out) if args.out else Path(f"{file_path.stem.replace(' ', '_')}_parsed.json")
            out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            # Brief summary
            print(f"Saved: {out_path.resolve()}", flush=True)
            print(f"Name: {data.get('name')}", flush=True)
            print(f"Experience: {len(data.get('experience', []))}", flush=True)
            print(f"Education: {len(data.get('education', []))}", flush=True)
            print(f"Skills: {len(data.get('skills', []))}", flush=True)
        except Exception as e:
            print("[parse_offline] ERROR during parse:", str(e), flush=True)
            traceback.print_exc()
            sys.exit(1)

    asyncio.run(run())


if __name__ == "__main__":
    main()


