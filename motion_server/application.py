from datetime import datetime, timezone
import os

from configuration import (
    ConfigurationSource,
    build_bootstrap_server_config,
    build_motion_server_config,
    load_configuration,
    load_configuration_snapshot,
    parse_cli_overrides,
)
from configuration.builder import build_file_log_config
from configuration.models import FileLogConfig
from motion_server.file_logging import FileLoggingSession
from device import available_device_names
from motion_server.app.initialization import (
    InitializationStage,
    InitializationStatus,
    initialization_failure_from_exception,
    log_initialization_failure,
)
from motion_server.diagnostic import DiagnosticManager
from motion_server.diagnostic.startup import detect_initialization_fault
from motion_server.app.session import ServerSession
from motion_server.app.listener import ListenerStartupException, log_listener_startup_failure


class MotionServerApplication:
    """Owns successive immutable sessions within one server process."""

    def __init__(
        self,
        bootstrap_config,
        config=None,
        initialization_status=None,
        initialization_exception=None,
        list_adapters=False,
        file_logging=FileLogConfig(),
        reload_inputs=None,
    ):
        self._reload_inputs = reload_inputs
        self._file_logging = file_logging
        self._bootstrap_config = bootstrap_config
        self._config = config
        self._initialization_status = (
            initialization_status or InitializationStatus.ready()
        )
        self._initialization_exception = initialization_exception
        self._list_adapters = bool(list_adapters)

    @property
    def config(self):
        return self._config

    @property
    def bootstrap_config(self):
        return self._bootstrap_config

    @property
    def initialization_status(self):
        return self._initialization_status

    @property
    def initialization_exception(self):
        return self._initialization_exception

    @classmethod
    def from_source(cls, source, argv=None, environ=None):
        if not isinstance(source, ConfigurationSource):
            raise TypeError("source must be a ConfigurationSource")
        argv = list(argv or ())
        environ = dict(os.environ if environ is None else environ)
        reload_inputs = (source, tuple(argv), environ)
        if argv:
            cli_overrides, list_adapters = parse_cli_overrides(argv)
        else:
            cli_overrides, list_adapters = parse_cli_overrides([])

        snapshot = load_configuration_snapshot(
            source.project_root,
            project_filename=source.project_filename,
            device_filename=source.device_filename,
            environ=environ,
        )
        bootstrap_config = build_bootstrap_server_config(
            snapshot,
            cli_overrides,
        )

        file_logging = FileLogConfig()
        try:
            file_logging = build_file_log_config(
                snapshot.values, (source.project_root / source.project_filename).resolve().parent)
            raw_config = load_configuration(
                available_profiles=available_device_names(),
                snapshot=snapshot,
                bus_override=cli_overrides.bus,
            )
            typed_config = build_motion_server_config(
                raw_config,
                cli_overrides,
                bootstrap=bootstrap_config,
                file_logging=file_logging,
            )
        except Exception as exc:
            failure = initialization_failure_from_exception(
                InitializationStage.CONFIGURATION,
                exc,
                occurred_at=datetime.now(timezone.utc),
            )
            return cls(
                bootstrap_config,
                initialization_status=InitializationStatus.failed(failure),
                initialization_exception=exc,
                list_adapters=list_adapters,
                file_logging=file_logging,
                reload_inputs=reload_inputs,
            )
        return cls(
            bootstrap_config,
            typed_config,
            initialization_status=InitializationStatus.ready(),
            list_adapters=list_adapters,
            file_logging=file_logging,
            reload_inputs=reload_inputs,
        )

    def run(self, runner=None):
        from motion_server.server import ServerRestartRequested, ServerCleanupError
        current = self
        try:
            while True:
                with FileLoggingSession(current._file_logging) as logging_session:
                    try:
                        return current._run(runner)
                    except ListenerStartupException as exception:
                        log_listener_startup_failure(exception)
                        return 1
                    except ServerCleanupError as exception:
                        print(f"Motion Server cleanup failed; exiting: {exception}", flush=True)
                        return 1
                    except ServerRestartRequested:
                        print("Motion Server restart accepted; reinitializing in the same process.", flush=True)
                # Never overlap an old file writer/lock with a new session.
                if logging_session.writer is not None and not logging_session.writer.stopped:
                    print("Motion Server restart aborted: file log worker has not stopped.", flush=True)
                    return 1
                if current._reload_inputs is None:
                    print("Motion Server restart aborted: configuration source is unavailable.", flush=True)
                    return 1
                source, argv, environ = current._reload_inputs
                try:
                    current = type(self).from_source(source, argv=argv, environ=environ)
                except (OSError, ValueError) as exception:
                    print(f"Motion Server configuration reload failed; exiting: {exception}", flush=True)
                    return 1
        except KeyboardInterrupt:
            # Includes session cleanup and configuration reload between iterations.
            return 0

    def _run(self, runner=None):
        if self._config is None:
            if runner is not None:
                return runner(
                    bootstrap_config=self._bootstrap_config,
                    initialization_status=self._initialization_status,
                    diagnostic_manager=DiagnosticManager(),
                )
            from motion_server.server import run_configuration_degraded_once

            session = ServerSession(self._initialization_status)
            log_initialization_failure(
                self._initialization_status.failure,
                self._initialization_exception,
            )
            detect_initialization_fault(
                session,
                at=self._initialization_status.failure.occurred_at,
            )
            return run_configuration_degraded_once(session, self._bootstrap_config)

        dependencies = {
            "server_config": self._config.server,
            "ethercat_config": self._config.ethercat,
            "motion_config": self._config.motion,
            "logging_config": self._config.logging,
            "devices": self._config.devices,
            "virtual_parameter_store": self._config.virtual_parameter_store,
        }
        if runner is not None:
            return runner(
                diagnostic_manager=DiagnosticManager(),
                **dependencies,
            )

        # Runtime recovery lifecycle belongs to this composition root.
        from motion_server.server import run_main_once, list_adapters

        if self._list_adapters:
            list_adapters()
            return

        session = ServerSession(
            InitializationStatus.ready(),
            diagnostic_manager=DiagnosticManager(),
        )
        return run_main_once(session, **dependencies)
