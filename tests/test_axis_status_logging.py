from types import SimpleNamespace
import unittest
from unittest.mock import patch

from configuration.builder import build_logging_config
from motion_server.runtime_logging import RuntimeLogger
from motion_server.app.cycle_diagnostics import log_status_if_due


class AxisStatusLoggingTest(unittest.TestCase):
    def test_independent_event_and_axis_switches(self):
        for events in (False, True):
            for axes in (False, True):
                with self.subTest(events=events, axes=axes):
                    messages = []
                    config = build_logging_config({
                        "MOTION_SERVER_STATUS_LOGS": str(int(events)),
                        "MOTION_SERVER_AXIS_STATUS_LOGS": str(int(axes)),
                    })
                    logger = RuntimeLogger(config, logger=SimpleNamespace(info=messages.append))
                    runtime = SimpleNamespace(logger=logger)
                    if axes:
                        runtime.slaves = []
                        runtime.wkc = 0
                        runtime.expected_wkc = lambda: 0
                    logger.status("Client connected")
                    with patch("motion_server.app.cycle_diagnostics.time.monotonic", return_value=10):
                        result = log_status_if_due(runtime, {}, 0)
                    self.assertEqual("Client connected" in messages, events)
                    self.assertEqual(any(m.startswith("Axis status:") for m in messages), axes)
                    self.assertEqual(result, 10 if axes else 0)

    def test_axis_logging_is_optional_and_defaults_off(self):
        self.assertFalse(build_logging_config({}).status.axis_enabled)

    def test_rejects_invalid_axis_switch(self):
        with self.assertRaises(ValueError):
            build_logging_config({"MOTION_SERVER_AXIS_STATUS_LOGS": "invalid"})

    def test_period_throttles_axis_output(self):
        logger = SimpleNamespace(config=build_logging_config({"MOTION_SERVER_AXIS_STATUS_LOGS": "1"}))
        with patch("motion_server.app.cycle_diagnostics.time.monotonic", return_value=10.5):
            self.assertEqual(log_status_if_due(SimpleNamespace(logger=logger), {}, 10), 10)
