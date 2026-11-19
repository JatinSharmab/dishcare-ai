import time

from app.core.exceptions import BusinessError


class CircuitBreaker:

    def __init__(
        self,
        failure_threshold: int = 3,
        reset_seconds: float = 15,
    ):

        self.failure_threshold = failure_threshold
        self.reset_seconds = reset_seconds

        self.failures = 0
        self.opened_at = None
        self.probe_active = False

    @property
    def state(self):

        if self.opened_at is None:
            return "closed"

        elapsed = (
            time.monotonic() - self.opened_at
        )

        if elapsed >= self.reset_seconds:
            return "half_open"

        return "open"

    def acquire(self):

        state = self.state

        if state == "open":

            raise BusinessError(
                503,
                "CIRCUIT_OPEN",
                "Technician service temporarily unavailable",
            )

        if state == "half_open":

            if self.probe_active:

                raise BusinessError(
                    503,
                    "RECOVERY_IN_PROGRESS",
                    "Service recovery is being checked",
                )

            self.probe_active = True

    def success(self):

        self.failures = 0
        self.opened_at = None
        self.probe_active = False

    def failure(self):

        self.failures += 1

        if (
            self.probe_active
            or self.failures >= self.failure_threshold
        ):

            self.opened_at = time.monotonic()

        self.probe_active = False

    def release_probe(self):

        self.probe_active = False