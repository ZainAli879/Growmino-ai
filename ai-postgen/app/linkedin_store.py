from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import RLock
from uuid import uuid4

from app.config import Settings
from app.schemas import LinkedInPostStatus

_LOCK = RLock()


@dataclass(frozen=True)
class LinkedInConnection:
    id: str
    user_id: str
    business_id: str
    linkedin_sub: str
    person_urn: str
    encrypted_access_token: str
    profile_name: str = ""
    email: str = ""
    expires_at: str = ""
    connected_at: str = ""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def insert_oauth_state(
    settings: Settings,
    *,
    state_hash: str,
    user_id: str,
    business_id: str,
    expires_at: str,
    redirect_after: str,
) -> None:
    with _LOCK:
        data = _load(settings)
        data["oauth_states"].append(
            {
                "id": str(uuid4()),
                "state_hash": state_hash,
                "user_id": user_id,
                "business_id": business_id,
                "redirect_after": redirect_after,
                "expires_at": expires_at,
                "used_at": "",
                "created_at": utc_now_iso(),
            }
        )
        _save(settings, data)


def consume_oauth_state(settings: Settings, *, state_hash: str) -> dict | None:
    with _LOCK:
        data = _load(settings)
        for state in data["oauth_states"]:
            if state.get("state_hash") != state_hash or state.get("used_at"):
                continue
            try:
                expires_at = datetime.fromisoformat(str(state.get("expires_at", "")).replace("Z", "+00:00"))
            except ValueError:
                return None
            if expires_at < datetime.now(timezone.utc):
                return None
            state["used_at"] = utc_now_iso()
            _save(settings, data)
            return dict(state)
    return None


def upsert_connection(
    settings: Settings,
    *,
    user_id: str,
    business_id: str,
    linkedin_sub: str,
    person_urn: str,
    encrypted_access_token: str,
    scopes: str,
    expires_at: str,
    profile: dict,
) -> LinkedInConnection:
    profile_name = " ".join(
        part for part in [str(profile.get("given_name") or ""), str(profile.get("family_name") or "")] if part
    ).strip() or str(profile.get("name") or "")
    email = str(profile.get("email") or "")
    with _LOCK:
        data = _load(settings)
        existing = None
        for row in data["connections"]:
            if row.get("user_id") == user_id and row.get("business_id") == business_id:
                existing = row
                break
        record = existing or {"id": str(uuid4()), "created_at": utc_now_iso()}
        record.update(
            {
                "user_id": user_id,
                "business_id": business_id,
                "linkedin_sub": linkedin_sub,
                "person_urn": person_urn,
                "encrypted_access_token": encrypted_access_token,
                "scopes": scopes,
                "expires_at": expires_at,
                "profile": profile,
                "profile_name": profile_name,
                "email": email,
                "disconnected_at": "",
                "updated_at": utc_now_iso(),
            }
        )
        if existing is None:
            data["connections"].append(record)
        _save(settings, data)
        return _connection_from_row(record)


def get_connection(settings: Settings, *, user_id: str, business_id: str) -> LinkedInConnection | None:
    with _LOCK:
        data = _load(settings)
        for row in data["connections"]:
            if row.get("user_id") == user_id and row.get("business_id") == business_id and not row.get("disconnected_at"):
                return _connection_from_row(row)
    return None


def disconnect_connection(settings: Settings, *, user_id: str, business_id: str) -> bool:
    with _LOCK:
        data = _load(settings)
        changed = False
        for row in data["connections"]:
            if row.get("user_id") == user_id and row.get("business_id") == business_id and not row.get("disconnected_at"):
                row["disconnected_at"] = utc_now_iso()
                row["updated_at"] = utc_now_iso()
                changed = True
        if changed:
            _save(settings, data)
        return changed


def create_publish_job(
    settings: Settings,
    *,
    user_id: str,
    business_id: str,
    post_type: str,
    caption: str,
    status: str,
    image_url: str = "",
    image_urns: list[str] | None = None,
    alt_texts: list[str] | None = None,
    scheduled_for_utc: str = "",
    display_timezone: str = "",
    idempotency_key: str = "",
) -> LinkedInPostStatus:
    with _LOCK:
        data = _load(settings)
        if idempotency_key:
            for row in data["jobs"]:
                if (
                    row.get("user_id") == user_id
                    and row.get("business_id") == business_id
                    and row.get("idempotency_key") == idempotency_key
                ):
                    return _job_from_row(row)
        record = {
            "id": str(uuid4()),
            "user_id": user_id,
            "business_id": business_id,
            "platform": "linkedin",
            "type": post_type,
            "caption": caption,
            "image_url": image_url,
            "image_urns": image_urns or [],
            "alt_texts": alt_texts or [],
            "status": status,
            "scheduled_for_utc": scheduled_for_utc,
            "display_timezone": display_timezone,
            "idempotency_key": idempotency_key or str(uuid4()),
            "linkedin_post_id": "",
            "error_message": "",
            "retry_count": 0,
            "claimed_at": "",
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
        }
        data["jobs"].append(record)
        _save(settings, data)
        return _job_from_row(record)


def find_job_by_idempotency_key(
    settings: Settings,
    *,
    user_id: str,
    business_id: str,
    idempotency_key: str,
) -> LinkedInPostStatus | None:
    if not idempotency_key:
        return None
    with _LOCK:
        data = _load(settings)
        for row in data["jobs"]:
            if (
                row.get("user_id") == user_id
                and row.get("business_id") == business_id
                and row.get("idempotency_key") == idempotency_key
            ):
                return _job_from_row(row)
    return None


def get_publish_job(settings: Settings, *, post_id: str, user_id: str = "", business_id: str = "") -> LinkedInPostStatus | None:
    with _LOCK:
        data = _load(settings)
        for row in data["jobs"]:
            if row.get("id") != post_id:
                continue
            if user_id and row.get("user_id") != user_id:
                continue
            if business_id and row.get("business_id") != business_id:
                continue
            return _job_from_row(row)
    return None


def list_publish_jobs(settings: Settings, *, user_id: str, business_id: str, limit: int = 25) -> list[LinkedInPostStatus]:
    with _LOCK:
        data = _load(settings)
        jobs = [
            _job_from_row(row)
            for row in data["jobs"]
            if row.get("user_id") == user_id and row.get("business_id") == business_id
        ]
    jobs.sort(key=lambda job: job.created_at, reverse=True)
    return jobs[: max(1, min(limit, 100))]


def update_publish_job(settings: Settings, *, post_id: str, values: dict) -> LinkedInPostStatus | None:
    with _LOCK:
        data = _load(settings)
        for row in data["jobs"]:
            if row.get("id") == post_id:
                row.update(values)
                row["updated_at"] = utc_now_iso()
                _save(settings, data)
                return _job_from_row(row)
    return None


def claim_due_publish_jobs(settings: Settings, *, limit: int = 5) -> list[LinkedInPostStatus]:
    now = datetime.now(timezone.utc)
    claimed: list[LinkedInPostStatus] = []
    with _LOCK:
        data = _load(settings)
        due_rows = []
        for row in data["jobs"]:
            if row.get("status") != "scheduled" or not row.get("scheduled_for_utc"):
                continue
            try:
                scheduled = datetime.fromisoformat(str(row["scheduled_for_utc"]).replace("Z", "+00:00"))
            except ValueError:
                continue
            if scheduled <= now:
                due_rows.append(row)
        due_rows.sort(key=lambda row: row.get("scheduled_for_utc", ""))
        for row in due_rows[: max(1, min(limit, 25))]:
            row["status"] = "publishing"
            row["claimed_at"] = utc_now_iso()
            row["updated_at"] = utc_now_iso()
            claimed.append(_job_from_row(row))
        if claimed:
            _save(settings, data)
    return claimed


def _store_path(settings: Settings) -> Path:
    return Path(settings.linkedin_store_file).expanduser()


def _load(settings: Settings) -> dict:
    path = _store_path(settings)
    if not path.exists():
        return {"oauth_states": [], "connections": [], "jobs": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"oauth_states": [], "connections": [], "jobs": []}
    return {
        "oauth_states": list(data.get("oauth_states") or []),
        "connections": list(data.get("connections") or []),
        "jobs": list(data.get("jobs") or []),
    }


def _save(settings: Settings, data: dict) -> None:
    path = _store_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temp_path.replace(path)


def _connection_from_row(row: dict) -> LinkedInConnection:
    return LinkedInConnection(
        id=str(row.get("id", "") or ""),
        user_id=str(row.get("user_id", "") or ""),
        business_id=str(row.get("business_id", "") or ""),
        linkedin_sub=str(row.get("linkedin_sub", "") or ""),
        person_urn=str(row.get("person_urn", "") or ""),
        encrypted_access_token=str(row.get("encrypted_access_token", "") or ""),
        profile_name=str(row.get("profile_name", "") or ""),
        email=str(row.get("email", "") or ""),
        expires_at=str(row.get("expires_at", "") or ""),
        connected_at=str(row.get("created_at", "") or ""),
    )


def _job_from_row(row: dict) -> LinkedInPostStatus:
    return LinkedInPostStatus(
        id=str(row.get("id", "") or ""),
        user_id=str(row.get("user_id", "") or ""),
        business_id=str(row.get("business_id", "") or ""),
        platform=str(row.get("platform", "linkedin") or "linkedin"),
        type=str(row.get("type", "text") or "text"),
        status=str(row.get("status", "") or ""),
        caption=str(row.get("caption", "") or ""),
        image_url=str(row.get("image_url", "") or ""),
        image_urns=[str(value or "") for value in list(row.get("image_urns") or [])],
        alt_texts=[str(value or "") for value in list(row.get("alt_texts") or [])],
        scheduled_for_utc=str(row.get("scheduled_for_utc", "") or ""),
        display_timezone=str(row.get("display_timezone", "") or ""),
        linkedin_post_id=str(row.get("linkedin_post_id", "") or ""),
        error_message=str(row.get("error_message", "") or ""),
        retry_count=int(row.get("retry_count", 0) or 0),
        created_at=str(row.get("created_at", "") or ""),
        updated_at=str(row.get("updated_at", "") or ""),
    )
