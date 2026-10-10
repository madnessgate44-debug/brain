import json
import logging

from brain.core.logging import StructuredFormatter


def test_structured_formatter_emits_parseable_json_and_extra_fields():
    record = logging.LogRecord(
        name="brain.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=12,
        msg="mission started",
        args=(),
        exc_info=None,
    )
    record.mission_id = "mis_test"
    record.event_type = "mission_started"

    rendered = StructuredFormatter().format(record)
    parsed = json.loads(rendered)

    assert parsed["logger"] == "brain.test"
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "mission started"
    assert parsed["mission_id"] == "mis_test"
    assert parsed["event_type"] == "mission_started"
