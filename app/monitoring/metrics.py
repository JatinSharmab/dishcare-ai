from collections import Counter, defaultdict, deque
from math import ceil
from threading import Lock


class Metrics:
    def __init__(self, sample_size=2048):
        self.counts = Counter()
        self.timings = defaultdict(lambda: deque(maxlen=sample_size))
        self.lock = Lock()

    def increment(self, label, amount=1):
        with self.lock:
            self.counts[label] += amount

    def observe(self, label, seconds):
        with self.lock:
            self.timings[label].append(seconds)

    def snapshot(self):
        with self.lock:
            timings = {key: sorted(values) for key, values in self.timings.items()}
            counts = dict(self.counts)
        return {
            "counts": counts,
            "latency_ms": {
                key: {
                    "samples": len(values),
                    **{f"p{p}": round(values[ceil(len(values) * p / 100) - 1] * 1000, 3)
                       for p in (50, 95, 99)},
                }
                for key, values in timings.items()
            },
        }
