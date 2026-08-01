"""Focused API contract tests for revision-bound calendar downloads."""

from datetime import date, datetime, timezone
import importlib
from types import SimpleNamespace

from studiosaas.calendar_export import build_schedule_document

api_v1 = importlib.import_module("studiosaas.api_v1")


def _document(**overrides):
    values = {
        "tenant_name": "PWE Studio",
        "tenant_slug": "pwe",
        "timezone_name": "Australia/Melbourne",
        "location": "Creative Quarter",
        "schedules": [
            {
                "id": "one",
                "label": "Creative Drawing",
                "weekday": 3,
                "start_time": "16:00",
                "duration_minutes": 60,
            }
        ],
        "today": date(2026, 7, 27),
        "generated_at": datetime(2026, 7, 29, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return build_schedule_document(**values)


def test_calendar_download_requires_valid_matching_revision(app):
    document = _document()
    with app.test_request_context("/calendar.ics"):
        response, status = api_v1._calendar_download_response(document)
        assert status == 400
        assert response.get_json()["error"] == "invalid_calendar_revision"

    with app.test_request_context("/calendar.ics?revision=not-a-hash"):
        response, status = api_v1._calendar_download_response(document)
        assert status == 400
        assert response.get_json()["error"] == "invalid_calendar_revision"

    with app.test_request_context(f"/calendar.ics?revision={'0' * 64}"):
        response, status = api_v1._calendar_download_response(document)
        assert status == 409
        assert response.get_json() == {
            "error": "calendar_revision_conflict",
            "message": "Calendar data changed after preview. Preview it again before downloading.",
        }


def test_calendar_download_success_headers_use_authoritative_safe_filename(app):
    document = _document(tenant_slug="pwe-画室")
    with app.test_request_context(f"/calendar.ics?revision={document.revision}"):
        response = api_v1._calendar_download_response(document)
    assert response.status_code == 200
    assert response.content_type == "text/calendar; charset=utf-8"
    assert response.headers["Cache-Control"] == "private, no-store"
    disposition = response.headers["Content-Disposition"]
    assert 'filename="pwe--weekly-classes.ics"' in disposition
    assert "filename*=UTF-8''pwe-%E7%94%BB%E5%AE%A4-weekly-classes.ics" in disposition
    assert response.data.startswith(b"BEGIN:VCALENDAR\r\n")


def test_cancelled_explicit_entry_removes_inherited_student_but_is_retained(monkeypatch):
    cancelled = {
        "id": "entry-1",
        "student_id": "student-1",
        "student_name": "Ruby",
        "source": "manual",
        "status": "cancelled",
        "note": "",
        "cancelled_at": None,
        "class_time": "16:00",
        "one_to_one": False,
        "created_at": datetime(2026, 7, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 7, 2, tzinfo=timezone.utc),
    }
    weekly = {
        "schedule_id": "schedule-1",
        "label": "Drawing",
        "start_time": "16:00",
        "duration_minutes": 60,
        "capacity": 10,
        "course_id": None,
        "course_name": None,
        "student_id": "student-1",
        "student_name": "Ruby",
    }
    calls = iter(([cancelled], [weekly]))
    monkeypatch.setattr(api_v1, "fetch_all", lambda *_args, **_kwargs: next(calls))

    roster = api_v1._daily_roster_for_date(
        SimpleNamespace(), "tenant-1", date(2026, 7, 29)
    )
    assert roster["effectiveStudents"] == []
    assert roster["entries"][0]["status"] == "cancelled"
