from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import requests


def _count_hashtags(text: str) -> int:
    return len(re.findall(r"(?<!\w)#\w+", text or ""))


def _hashtag_limits(platform: str) -> tuple[int, int]:
    limits = {
        "linkedin": (3, 6),
        "instagram": (5, 10),
        "facebook": (3, 6),
    }
    return limits[platform]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run golden smoke checks against the posts API.")
    parser.add_argument("--api", default="http://127.0.0.1:8000/api/v1/posts", help="API endpoint URL")
    parser.add_argument(
        "--cases",
        default=str(Path("tests") / "golden_requests.json"),
        help="Path to golden request file",
    )
    parser.add_argument("--timeout", type=int, default=360, help="Request timeout seconds")
    args = parser.parse_args()

    case_path = Path(args.cases)
    if not case_path.exists():
        print(f"Case file not found: {case_path}")
        return 1

    cases = json.loads(case_path.read_text(encoding="utf-8"))
    failures = 0
    for case in cases:
        name = case["name"]
        payload = case["payload"]
        try:
            resp = requests.post(args.api, json=payload, timeout=args.timeout)
        except requests.RequestException as exc:
            print(f"[FAIL] {name}: request error: {exc}")
            failures += 1
            continue

        if resp.status_code != 200:
            print(f"[FAIL] {name}: status={resp.status_code} body={resp.text[:300]}")
            failures += 1
            continue

        body = resp.json()
        caption = (body.get("caption") or "").strip()
        headline = (body.get("headline") or "").strip()
        qa = body.get("qa") or {}
        platform = payload["platform"]
        tag_count = _count_hashtags(caption)
        min_tags, max_tags = _hashtag_limits(platform)

        case_failures: list[str] = []
        if not caption:
            case_failures.append("empty caption")
        if not headline:
            case_failures.append("empty headline")
        if not (min_tags <= tag_count <= max_tags):
            case_failures.append(f"hashtags={tag_count} outside {min_tags}-{max_tags}")
        if "openai_image" not in body:
            case_failures.append("missing openai_image")
        if "trace" not in body:
            case_failures.append("missing trace")
        if not isinstance(qa, dict):
            case_failures.append("qa not object")

        if case_failures:
            print(f"[FAIL] {name}: " + "; ".join(case_failures))
            failures += 1
        else:
            print(f"[PASS] {name}: hashtags={tag_count}, headline='{headline}'")

    total = len(cases)
    passed = total - failures
    print(f"\nSummary: passed={passed}/{total}, failed={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
