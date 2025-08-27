import argparse
import json
import os
import sys
from pathlib import Path

try:
    import requests  # type: ignore
except Exception:
    print("ERROR: The 'requests' package is not installed.\n"
          "Install it with: poetry add requests\n"
          "Then re-run this script.")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Submit a resume to ResumeProcessingAgent and print analysis results.")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Base URL of the backend API (default: http://127.0.0.1:8000)")
    parser.add_argument("--file", required=True, help="Path to resume PDF/DOCX/TXT")
    parser.add_argument("--title", required=True, help="Target job title, e.g. 'Software Development Engineer'")
    args = parser.parse_args()

    base = args.url.rstrip("/")
    endpoint = f"{base}/api/assistant/agent-task"

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"ERROR: File not found: {file_path}")
        sys.exit(2)

    task_details = {"target_job_title": args.title}

    files = [
        (
            "files",
            (
                file_path.name,
                open(file_path, "rb"),
                "application/pdf" if file_path.suffix.lower() == ".pdf" else "application/octet-stream",
            ),
        )
    ]

    data = {
        "agent_name": "ResumeProcessingAgent",
        "task_details_json": json.dumps(task_details),
    }

    print(f"POST {endpoint}")
    try:
        resp = requests.post(endpoint, data=data, files=files, timeout=180)
    finally:
        # close file handle
        try:
            files[0][1][1].close()
        except Exception:
            pass

    if resp.status_code != 200:
        print(f"HTTP {resp.status_code}: {resp.text[:500]}")
        sys.exit(3)

    try:
        result = resp.json()
    except Exception:
        print(resp.text)
        sys.exit(0)

    # Pretty summary
    job_fit = result.get("job_fit_score")
    rec = (result.get("hiring_recommendation") or {}).copy()
    quality = (result.get("quality_assessment") or {}).copy()
    market = (result.get("market_alignment") or {}).copy()

    print("\n=== ResumeProcessingAgent Result ===")
    print(f"Status: {result.get('status')}  File: {result.get('filename')}")
    print(f"Target: {market.get('target_job_title') or args.title}")
    print(f"Job Fit Score: {job_fit}/10  Recommendation: {rec.get('recommendation')} ({rec.get('decision')})")

    overlap = market.get("overlap_ratio")
    if overlap is not None:
        print(f"Skills Overlap (Jaccard): {overlap*100:.1f}%")

    ms = market.get("matching_skills") or []
    miss = market.get("missing_skills") or []
    print(f"Matching skills ({len(ms)}): {', '.join(ms[:25])}{' ...' if len(ms) > 25 else ''}")
    print(f"Missing skills  ({len(miss)}): {', '.join(miss[:25])}{' ...' if len(miss) > 25 else ''}")

    if quality:
        c = quality.get("clarity_score"); i = quality.get("impact_score"); r = quality.get("skills_relevance_score")
        print(f"Quality — clarity: {c}/10, impact: {i}/10, relevance: {r}/10")

    # Save full JSON to file for inspection (derive name from input file)
    safe_stem = file_path.stem.replace(' ', '_').replace('/', '_')
    out_path = Path(f"{safe_stem}_parsed.json")
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nFull JSON saved to: {out_path.resolve()}")

    # Extra diagnostics
    parsed = result.get("data") or {}
    parsed_skills = parsed.get("skills") or []
    print(f"Parsed skills count: {len(parsed_skills)}")
    cand_from_align = (market.get("candidate_skills") or [])
    print(f"Candidate skills used for overlap ({len(cand_from_align)}): {', '.join(cand_from_align[:25])}{' ...' if len(cand_from_align) > 25 else ''}")


if __name__ == "__main__":
    main()
