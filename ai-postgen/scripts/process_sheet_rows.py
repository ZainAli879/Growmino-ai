from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def _require(value: str, env_name: str) -> str:
    if value.strip():
        return value.strip()
    raise RuntimeError(f"{env_name} is required for Google Sheets/Drive sync.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Process pending rows from Google Sheet, generate post, upload image to Drive.")
    parser.add_argument("--max-rows", type=int, default=5, help="Maximum pending rows to process in this run.")
    parser.add_argument(
        "--debug-skip-reasons",
        action="store_true",
        help="Print diagnostics for skipped rows when no pending rows are found.",
    )
    args = parser.parse_args()

    from app.api import _run_generation
    from app.config import get_settings
    from app.google_workspace import GoogleWorkspaceClient

    settings = get_settings()
    google_auth_mode = (settings.google_auth_mode or "service_account").strip().lower()
    sheets_auth_mode = (settings.google_sheets_auth_mode or google_auth_mode).strip().lower()
    drive_auth_mode = (settings.google_drive_auth_mode or google_auth_mode).strip().lower()

    credentials_json_path = ""
    if sheets_auth_mode == "service_account" or drive_auth_mode == "service_account":
        credentials_json_path = _require(settings.google_credentials_json_path, "GOOGLE_CREDENTIALS_JSON_PATH")

    oauth_client_json_path = settings.google_oauth_client_json_path
    oauth_token_path = settings.google_oauth_token_path
    sheets_oauth_client_json_path = settings.google_sheets_oauth_client_json_path or oauth_client_json_path
    drive_oauth_client_json_path = settings.google_drive_oauth_client_json_path or oauth_client_json_path
    sheets_oauth_token_path = settings.google_sheets_oauth_token_path
    drive_oauth_token_path = settings.google_drive_oauth_token_path

    if sheets_auth_mode == "oauth_user":
        sheets_oauth_client_json_path = _require(sheets_oauth_client_json_path, "GOOGLE_SHEETS_OAUTH_CLIENT_JSON_PATH or GOOGLE_OAUTH_CLIENT_JSON_PATH")
    if drive_auth_mode == "oauth_user":
        drive_oauth_client_json_path = _require(drive_oauth_client_json_path, "GOOGLE_DRIVE_OAUTH_CLIENT_JSON_PATH or GOOGLE_OAUTH_CLIENT_JSON_PATH")

    spreadsheet_id = _require(settings.google_spreadsheet_id, "GOOGLE_SPREADSHEET_ID")
    sheet_name = _require(settings.google_sheet_name, "GOOGLE_SHEET_NAME")
    drive_folder_id = _require(settings.google_drive_folder_id, "GOOGLE_DRIVE_FOLDER_ID")

    gw = GoogleWorkspaceClient(
        credentials_json_path=credentials_json_path,
        spreadsheet_id=spreadsheet_id,
        sheet_name=sheet_name,
        drive_folder_id=drive_folder_id,
        auth_mode=google_auth_mode,
        oauth_client_json_path=oauth_client_json_path,
        oauth_token_path=oauth_token_path,
        sheets_auth_mode=sheets_auth_mode,
        drive_auth_mode=drive_auth_mode,
        sheets_oauth_client_json_path=sheets_oauth_client_json_path,
        drive_oauth_client_json_path=drive_oauth_client_json_path,
        sheets_oauth_token_path=sheets_oauth_token_path,
        drive_oauth_token_path=drive_oauth_token_path,
    )

    rows = gw.get_pending_rows(max_rows=max(1, args.max_rows))
    if not rows:
        print("No pending rows found.")
        if args.debug_skip_reasons:
            print("Diagnostics:")
            for line in gw.diagnose_skipped_rows(max_rows=100):
                print(f"- {line}")
        return 0

    success = 0
    failed = 0
    for row in rows:
        print(f"Processing row {row.row_number}...")
        row_platform_errors: dict[str, str] = {}
        row_had_success = False
        try:
            gw.write_processing(row.row_number)
            for request in row.requests:
                platform = request.platform.value
                try:
                    if (
                        not (request.company_logo_url or "").strip()
                        and (settings.default_company_logo_path or "").strip()
                    ):
                        request = request.model_copy(
                            update={"company_logo_url": settings.default_company_logo_path.strip()}
                        )
                    generated = asyncio.run(_run_generation(request, settings))
                    drive_url = gw.upload_image_to_drive(generated.openai_image.file_path)
                    gw.write_platform_success(
                        row_number=row.row_number,
                        platform=platform,
                        caption=generated.caption,
                        headline=generated.headline,
                        image_file_path=generated.openai_image.file_path,
                        drive_image_url=drive_url,
                        trace_id=generated.trace.trace_id if generated.trace else "",
                    )
                    row_had_success = True
                    row_platform_errors[platform] = ""
                    print(f"Row {row.row_number} platform {platform} done.")
                except Exception as platform_exc:
                    row_platform_errors[platform] = str(platform_exc)
                    print(f"Row {row.row_number} platform {platform} failed: {platform_exc}")

            gw.write_row_outcome(row.row_number, row_platform_errors)
            if row_had_success and any(msg for msg in row_platform_errors.values()):
                failed += 1
                print(f"Row {row.row_number} completed with partial failures.")
            elif row_had_success:
                success += 1
                print(f"Row {row.row_number} done for all requested platforms.")
            else:
                failed += 1
                print(f"Row {row.row_number} failed for all requested platforms.")
        except Exception as exc:
            failed += 1
            gw.write_failure(row.row_number, str(exc))
            print(f"Row {row.row_number} failed: {exc}")

    print(f"Completed. Success={success}, Failed={failed}, Total={len(rows)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
