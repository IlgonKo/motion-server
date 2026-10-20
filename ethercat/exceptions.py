from motion_server.failure import CommunicationException, CommunicationTimeoutException


class EtherCATStateTransitionException(CommunicationTimeoutException):
    """Expected failure to reach a requested EtherCAT bus state."""

    def __init__(self, requested_state, reached_state, *, slaves=(), wkc=None, expected_wkc=None, elapsed_s=None, sync_parameters=None):
        self.requested_state = requested_state
        self.reached_state = reached_state
        self.slaves = tuple(slaves)
        self.wkc = wkc
        self.expected_wkc = expected_wkc
        self.elapsed_s = elapsed_s
        self.sync_parameters = sync_parameters
        super().__init__(operation="ethercat_state_transition")

    def __str__(self):
        detail = (
            f"EtherCAT network did not reach {self.requested_state}. "
            f"Reached={self.reached_state}. Slaves={list(self.slaves)}"
        )
        if self.wkc is not None:
            detail += f" WKC={self.wkc}/{self.expected_wkc}"
        if self.elapsed_s is not None:
            detail += f" elapsed_s={self.elapsed_s:.3f}"
        if self.sync_parameters is not None:
            detail += f" sync_parameters={self.sync_parameters}"
        return detail


class EtherCATDiscoveryException(CommunicationException):
    """Discovery failed before a valid slave count was available."""

    def __init__(self, interface, expected_slaves, discovery_result):
        self.interface = interface
        self.expected_slaves = expected_slaves
        self.discovery_result = discovery_result
        super().__init__(operation="ethercat_discovery")

    def __str__(self):
        return (
            "EtherCAT discovery failed: "
            f"result={self.discovery_result} expected_slaves={self.expected_slaves} "
            f"interface={self.interface}"
        )
