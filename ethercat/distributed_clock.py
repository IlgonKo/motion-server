import time


class _DcTimeUnwrapper:
    """Extend the reference ESC clock without resetting phase at a 32-bit wrap."""

    def __init__(self, bits):
        if bits not in (32, 64):
            raise ValueError("DC clock width must be 32 or 64 bits")
        self.bits = bits
        self.mask = (1 << bits) - 1
        self.raw_ns = None
        self.monotonic_ns = None
        self.time_ns = 0

    def update(self, raw_ns, monotonic_ns):
        raw_ns = int(raw_ns) & self.mask
        monotonic_ns = int(monotonic_ns)
        if self.raw_ns is None:
            value = raw_ns
        else:
            host_elapsed = monotonic_ns - self.monotonic_ns
            elapsed = (raw_ns - self.raw_ns) & self.mask
            # Long gaps make 32-bit wrap counting ambiguous. A clock reset must
            # not become a multi-second jump in the cyclic scheduling timeline.
            if host_elapsed < 0 or (
                self.bits == 32 and host_elapsed >= (1 << 31)
            ):
                raise ValueError("DC sample interval is ambiguous")
            if abs(elapsed - host_elapsed) > max(100_000_000, host_elapsed // 10):
                raise ValueError("DC clock discontinuity")
            value = self.time_ns + elapsed if self.bits == 32 else raw_ns
        self.raw_ns = raw_ns
        self.monotonic_ns = monotonic_ns
        self.time_ns = value
        return value


class DistributedClock:

    def __init__(self):

        self.start = time.time_ns()

    def get_time_ns(self):

        return (
            time.time_ns()
            - self.start
        )


class DcPhaseLock:
    def __init__(
        self,
        enabled,
        cycle_time,
        phase_offset_ns,
        kp,
        ki,
        max_correction,
    ):
        self.enabled = bool(enabled)
        self.cycle_time_ns = max(1, int(round(float(cycle_time) * 1_000_000_000.0)))
        self.phase_offset_ns = int(phase_offset_ns)
        self.kp = float(kp)
        self.ki = float(ki)
        self.max_correction = abs(float(max_correction))
        self.reset()

    def reset(self):
        self.integral_error_s = 0.0
        self.correction_s = 0.0

    def target_phase_ns(self):
        return (self.cycle_time_ns - self.phase_offset_ns) % self.cycle_time_ns

    def correction(self):
        return self.correction_s if self.enabled else 0.0

    def update(self, dc_time_ns, stats):
        if dc_time_ns is None:
            return

        phase_error_ns = self._wrapped_phase_error_ns(dc_time_ns)
        phase_error_s = phase_error_ns / 1_000_000_000.0
        stats.add("dc_phase_error", phase_error_s)

        if not self.enabled:
            self.integral_error_s = 0.0
            self.correction_s = 0.0
            stats.add("dc_phase_correction", 0.0)
            return

        self.integral_error_s += phase_error_s
        self.integral_error_s = self._clamp(
            self.integral_error_s,
            -self.max_correction,
            self.max_correction,
        )
        self.correction_s = -(
            self.kp * phase_error_s
            + self.ki * self.integral_error_s
        )
        self.correction_s = self._clamp(
            self.correction_s,
            -self.max_correction,
            self.max_correction,
        )

        stats.add("dc_phase_correction", self.correction_s)

    def _wrapped_phase_error_ns(self, dc_time_ns):
        actual_phase = int(dc_time_ns) % self.cycle_time_ns
        error = actual_phase - self.target_phase_ns()
        half_cycle = self.cycle_time_ns // 2
        if error > half_cycle:
            error -= self.cycle_time_ns
        elif error < -half_cycle:
            error += self.cycle_time_ns
        return error

    @staticmethod
    def _clamp(value, minimum, maximum):
        return max(minimum, min(maximum, value))


class DcCycleScheduler:
    def __init__(self, phase_lock):
        self.phase_lock = phase_lock

    def estimate_dc_time_ns(self, master, monotonic_ns=None):
        last_rx_monotonic_ns = getattr(
            master,
            "last_rx_monotonic_ns",
            None,
        )
        last_rx_dc_time_ns = getattr(master, "last_rx_dc_time_ns", 0)
        if last_rx_monotonic_ns is None or not last_rx_dc_time_ns:
            return master.get_dc_time_ns()

        if monotonic_ns is None:
            monotonic_ns = time.monotonic_ns()
        return int(
            last_rx_dc_time_ns
            + int(monotonic_ns)
            - last_rx_monotonic_ns
        )

    def estimate_transmit_dc_time_ns(self, master):
        transmit_monotonic_ns = getattr(
            master,
            "last_tx_monotonic_ns",
            None,
        )
        if transmit_monotonic_ns is None:
            return master.get_dc_time_ns()
        return self.estimate_dc_time_ns(master, transmit_monotonic_ns)

    def absolute_cycle_deadline(self, master, monotonic_ns=None):
        now_monotonic_ns = (
            time.monotonic_ns()
            if monotonic_ns is None
            else int(monotonic_ns)
        )
        dc_now_ns = self.estimate_dc_time_ns(master, now_monotonic_ns)
        phase_ns = int(dc_now_ns) % self.phase_lock.cycle_time_ns
        wait_ns = self.phase_lock.target_phase_ns() - phase_ns
        if wait_ns <= 0:
            wait_ns += self.phase_lock.cycle_time_ns

        deadline = (now_monotonic_ns + wait_ns) / 1_000_000_000.0
        return deadline, wait_ns / 1_000_000_000.0
