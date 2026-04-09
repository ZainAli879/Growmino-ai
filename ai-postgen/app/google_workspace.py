from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from app.schemas import GenerateRequest

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

SUPPORTED_PLATFORMS = ("linkedin", "instagram", "facebook")

INPUT_COLUMNS = [
    "business_name",
    "industry",
    "offer",
    "target_audience",
    "audience_pain_points",
    "weekly_focus_topic",
    "day",
    "content_type",
    "tone",
    "brand_personality",
    "cta_preference",
    "proof_assets",
    "company_logo_url",
    "platform",
]

LEGACY_OUTPUT_COLUMNS = [
    "status",
    "caption",
    "headline",
    "image_file_path",
    "drive_image_url",
    "error",
    "processed_at_utc",
    "trace_id",
]

PLATFORM_OUTPUT_BASES = ("caption", "headline", "image_file_path", "drive_image_url", "trace_id", "error")

OUTPUT_COLUMNS = list(LEGACY_OUTPUT_COLUMNS)
for platform in SUPPORTED_PLATFORMS:
    for base in PLATFORM_OUTPUT_BASES:
        OUTPUT_COLUMNS.append(f"{base}_{platform}")


@dataclass(frozen=True)
class SheetRow:
    row_number: int
    requests: list[GenerateRequest]
    platforms: list[str]


class GoogleWorkspaceClient:
    def __init__(
        self,
        credentials_json_path: str,
        spreadsheet_id: str,
        sheet_name: str,
        drive_folder_id: str,
        auth_mode: str = "service_account",
        oauth_client_json_path: str = "",
        oauth_token_path: str = "oauth-token.json",
        sheets_auth_mode: str = "",
        drive_auth_mode: str = "",
        sheets_oauth_client_json_path: str = "",
        drive_oauth_client_json_path: str = "",
        sheets_oauth_token_path: str = "oauth-token-sheets.json",
        drive_oauth_token_path: str = "oauth-token-drive.json",
    ):
        self.credentials_json_path = credentials_json_path
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self.drive_folder_id = drive_folder_id
        self.auth_mode = (auth_mode or "service_account").strip().lower()
        self.oauth_client_json_path = oauth_client_json_path
        self.oauth_token_path = oauth_token_path
        self.sheets_auth_mode = (sheets_auth_mode or self.auth_mode).strip().lower()
        self.drive_auth_mode = (drive_auth_mode or self.auth_mode).strip().lower()
        self.sheets_oauth_client_json_path = sheets_oauth_client_json_path or oauth_client_json_path
        self.drive_oauth_client_json_path = drive_oauth_client_json_path or oauth_client_json_path
        self.sheets_oauth_token_path = sheets_oauth_token_path or "oauth-token-sheets.json"
        self.drive_oauth_token_path = drive_oauth_token_path or "oauth-token-drive.json"

        sheets_creds = self._build_credentials(
            mode=self.sheets_auth_mode,
            oauth_client_json_path=self.sheets_oauth_client_json_path,
            oauth_token_path=self.sheets_oauth_token_path,
            target="sheets",
        )
        drive_creds = self._build_credentials(
            mode=self.drive_auth_mode,
            oauth_client_json_path=self.drive_oauth_client_json_path,
            oauth_token_path=self.drive_oauth_token_path,
            target="drive",
        )
        self.sheets = build("sheets", "v4", credentials=sheets_creds)
        self.drive = build("drive", "v3", credentials=drive_creds)

    def _build_credentials(self, mode: str, oauth_client_json_path: str, oauth_token_path: str, target: str):
        if mode == "oauth_user":
            if not oauth_client_json_path.strip():
                raise RuntimeError(
                    f"OAuth client JSON path is required for {target} when auth mode is oauth_user."
                )

            client_path = Path(oauth_client_json_path)
            token_path = Path(oauth_token_path)
            creds: UserCredentials | None = None

            if token_path.exists():
                creds = UserCredentials.from_authorized_user_file(str(token_path), SCOPES)
                if creds and not creds.has_scopes(SCOPES):
                    creds = None

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(str(client_path), SCOPES)
                    creds = flow.run_local_server(port=0)
                token_path.write_text(creds.to_json(), encoding="utf-8")

            return creds

        if not self.credentials_json_path.strip():
            raise RuntimeError(
                f"GOOGLE_CREDENTIALS_JSON_PATH is required for {target} when auth mode is service_account."
            )
        return ServiceAccountCredentials.from_service_account_file(self.credentials_json_path, scopes=SCOPES)

    def _read_all_values(self) -> list[list[str]]:
        response = (
            self.sheets.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=self.sheet_name)
            .execute()
        )
        values = response.get("values", [])
        return values if isinstance(values, list) else []

    def _build_header_index(self, header_row: list[str]) -> dict[str, int]:
        normalized = [(col or "").strip().lower() for col in header_row]
        header_index: dict[str, int] = {}
        for i, col in enumerate(normalized):
            if col:
                header_index[col] = i
        return header_index

    def _get_cell(self, row: list[str], idx: int | None) -> str:
        if idx is None:
            return ""
        return (row[idx] if idx < len(row) else "").strip()

    def _parse_platforms(self, raw_value: str) -> list[str]:
        raw = (raw_value or "").strip().lower()
        if not raw:
            return ["linkedin"]
        if raw == "all":
            return list(SUPPORTED_PLATFORMS)

        normalized = raw.replace("|", ",").replace("/", ",")
        candidates = [x.strip().lower() for x in normalized.split(",") if x.strip()]
        unique: list[str] = []
        for candidate in candidates:
            if candidate not in SUPPORTED_PLATFORMS:
                raise ValueError(
                    f"Unsupported platform '{candidate}'. Use one of {', '.join(SUPPORTED_PLATFORMS)} or 'all'."
                )
            if candidate not in unique:
                unique.append(candidate)

        if not unique:
            raise ValueError("Platform value is empty after parsing.")
        return unique

    def _build_requests_for_row(self, row: list[str], header_index: dict[str, int]) -> tuple[list[GenerateRequest], list[str]]:
        payload: dict[str, Any] = {}
        for field in INPUT_COLUMNS:
            payload[field] = self._get_cell(row, header_index.get(field))

        platforms = self._parse_platforms(str(payload.get("platform", "")))
        requests: list[GenerateRequest] = []
        for platform in platforms:
            platform_payload = dict(payload)
            platform_payload["platform"] = platform
            requests.append(GenerateRequest.model_validate(platform_payload))
        return requests, platforms

    def get_pending_rows(self, max_rows: int = 10) -> list[SheetRow]:
        values = self._read_all_values()
        if not values:
            return []

        header = values[0]
        header_index = self._build_header_index(header)
        status_idx = header_index.get("status")

        pending: list[SheetRow] = []
        for i, row in enumerate(values[1:], start=2):
            status = self._get_cell(row, status_idx).lower()
            if status in {"done", "processing"}:
                continue

            try:
                requests, platforms = self._build_requests_for_row(row, header_index)
            except Exception:
                continue

            pending.append(SheetRow(row_number=i, requests=requests, platforms=platforms))
            if len(pending) >= max_rows:
                break
        return pending

    def diagnose_skipped_rows(self, max_rows: int = 50) -> list[str]:
        values = self._read_all_values()
        if not values:
            return ["Sheet is empty or could not be read."]

        header = values[0]
        header_index = self._build_header_index(header)
        status_idx = header_index.get("status")

        diagnostics: list[str] = []
        scanned = 0
        for i, row in enumerate(values[1:], start=2):
            status = self._get_cell(row, status_idx).lower()
            if status in {"done", "processing"}:
                diagnostics.append(f"Row {i}: skipped because status is '{status}'.")
                scanned += 1
                if scanned >= max_rows:
                    break
                continue

            try:
                _, platforms = self._build_requests_for_row(row, header_index)
                diagnostics.append(f"Row {i}: pending and valid for platforms={','.join(platforms)}.")
            except Exception as exc:
                diagnostics.append(f"Row {i}: skipped due to validation error: {exc}")

            scanned += 1
            if scanned >= max_rows:
                break

        if not diagnostics:
            diagnostics.append("No data rows found under header.")
        return diagnostics

    def _column_letter(self, one_based_index: int) -> str:
        n = one_based_index
        letters = []
        while n > 0:
            n, remainder = divmod(n - 1, 26)
            letters.append(chr(65 + remainder))
        return "".join(reversed(letters))

    def _ensure_output_columns(self) -> dict[str, int]:
        values = self._read_all_values()
        header = values[0] if values else []
        normalized = [(col or "").strip().lower() for col in header]
        existing_index: dict[str, int] = {col: idx for idx, col in enumerate(normalized) if col}

        updates: list[str] = []
        for column in OUTPUT_COLUMNS:
            if column not in existing_index:
                updates.append(column)

        if updates:
            new_header = list(header) + updates
            range_ref = f"{self.sheet_name}!1:1"
            (
                self.sheets.spreadsheets()
                .values()
                .update(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_ref,
                    valueInputOption="RAW",
                    body={"values": [new_header]},
                )
                .execute()
            )
            normalized = [(col or "").strip().lower() for col in new_header]
            existing_index = {col: idx for idx, col in enumerate(normalized) if col}

        return existing_index

    def _batch_write_row(self, row_number: int, payload: dict[str, str]) -> None:
        header_index = self._ensure_output_columns()
        updates: list[dict[str, Any]] = []
        for key, value in payload.items():
            col_letter = self._column_letter(header_index[key] + 1)
            range_ref = f"{self.sheet_name}!{col_letter}{row_number}"
            updates.append({"range": range_ref, "values": [[value]]})

        (
            self.sheets.spreadsheets()
            .values()
            .batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"valueInputOption": "RAW", "data": updates},
            )
            .execute()
        )

    def write_processing(self, row_number: int) -> None:
        self._batch_write_row(row_number, {"status": "processing"})

    def write_platform_success(
        self,
        row_number: int,
        platform: str,
        caption: str,
        headline: str,
        image_file_path: str,
        drive_image_url: str,
        trace_id: str,
    ) -> None:
        platform_name = platform.strip().lower()
        if platform_name not in SUPPORTED_PLATFORMS:
            raise ValueError(f"Unsupported platform '{platform}'.")

        payload = {
            f"caption_{platform_name}": caption,
            f"headline_{platform_name}": headline,
            f"image_file_path_{platform_name}": image_file_path,
            f"drive_image_url_{platform_name}": drive_image_url,
            f"trace_id_{platform_name}": trace_id,
            f"error_{platform_name}": "",
        }
        self._batch_write_row(row_number, payload)

    def write_row_outcome(self, row_number: int, platform_errors: dict[str, str]) -> None:
        failed_platforms = [p for p in SUPPORTED_PLATFORMS if platform_errors.get(p)]
        if not failed_platforms:
            status = "done"
            error_summary = ""
        elif len(failed_platforms) == len(SUPPORTED_PLATFORMS):
            status = "error"
            error_summary = "All platform generations failed."
        else:
            status = "partial"
            error_summary = f"Failed platforms: {', '.join(failed_platforms)}"

        payload: dict[str, str] = {
            "status": status,
            "processed_at_utc": datetime.now(timezone.utc).isoformat(),
            "error": error_summary[:500],
        }
        for platform, message in platform_errors.items():
            if platform in SUPPORTED_PLATFORMS:
                payload[f"error_{platform}"] = message[:500]
        self._batch_write_row(row_number, payload)

    # Backward-compatible single-platform writers.
    def write_success(
        self,
        row_number: int,
        caption: str,
        headline: str,
        image_file_path: str,
        drive_image_url: str,
        trace_id: str,
    ) -> None:
        payload = {
            "status": "done",
            "caption": caption,
            "headline": headline,
            "image_file_path": image_file_path,
            "drive_image_url": drive_image_url,
            "error": "",
            "processed_at_utc": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
        }
        self._batch_write_row(row_number, payload)

    def write_failure(self, row_number: int, error: str) -> None:
        payload = {
            "status": "error",
            "error": error[:500],
            "processed_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        self._batch_write_row(row_number, payload)

    def upload_image_to_drive(self, image_file_path: str) -> str:
        file_path = Path(image_file_path)
        if not file_path.exists():
            raise RuntimeError(f"Image file not found: {image_file_path}")

        metadata = {"name": file_path.name, "parents": [self.drive_folder_id]}
        media = MediaFileUpload(str(file_path), mimetype="image/png", resumable=False)
        created = (
            self.drive.files()
            .create(
                body=metadata,
                media_body=media,
                fields="id, webViewLink, webContentLink",
                supportsAllDrives=True,
            )
            .execute()
        )
        file_id = created.get("id", "")
        if not file_id:
            raise RuntimeError("Google Drive upload succeeded but no file id was returned.")

        self.drive.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
            supportsAllDrives=True,
        ).execute()
        return str(created.get("webViewLink") or f"https://drive.google.com/file/d/{file_id}/view")
