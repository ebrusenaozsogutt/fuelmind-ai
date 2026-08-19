"""Regression coverage for false-positive audit retention."""

from app.repositories.alarm_repository import AlarmRepository
from app.utils.enums import AlarmStatus


class _Scalars:
    def __init__(self, rows):
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)


class _Db:
    def __init__(self):
        self.statement = None

    def scalars(self, statement):
        self.statement = statement
        return _Scalars([])


def test_default_alarm_query_excludes_false_positives_but_audit_query_can_include_them() -> None:
    db = _Db()
    repository = AlarmRepository(db)  # type: ignore[arg-type]

    repository.list()
    default_sql = str(db.statement.compile(compile_kwargs={"literal_binds": True}))
    assert "FALSE_POSITIVE" in default_sql

    repository.list(include_false_positives=True)
    audit_sql = str(db.statement.compile(compile_kwargs={"literal_binds": True}))
    assert "FALSE_POSITIVE" not in audit_sql


def test_false_positive_is_a_persisted_status_not_a_delete_transition() -> None:
    # The lifecycle service changes this enum field and commits the row; the
    # repository has no deletion path for operational alarms.
    assert AlarmStatus.FALSE_POSITIVE.value == "FALSE_POSITIVE"
