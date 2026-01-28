# telemetry.py
import time

TEXT_COST_PER_1K_TOKENS = 0.00035
IMAGE_COST_USD = 0.04

class Telemetry:
    def __init__(self):
        self.start = time.time()
        self.latency = {}
        self.cost = {}

    def mark(self, name):
        self.latency[name] = int((time.time() - self.start) * 1000)

    def add_text_cost(self, prompt):
        tokens = max(1, len(prompt) // 4)
        self.cost["text_usd"] = round(tokens / 1000 * TEXT_COST_PER_1K_TOKENS, 6)

    def add_image_cost(self):
        self.cost["image_usd"] = IMAGE_COST_USD

    def export(self):
        return {
            "latency": self.latency,
            "cost": self.cost
        }

    def start_image(self):
        self._image_start = time.time()
        self.latency["image_attempts"] = 0
        self.latency["image_success"] = False

    def mark_image_attempt(self):
        self.latency["image_attempts"] += 1

    def end_image_success(self):
        self.latency["image_latency_ms"] = int(
            (time.time() - self._image_start) * 1000
        )
        self.latency["image_success"] = True
        self.cost["image_usd"] = IMAGE_COST_USD

    def end_image_failure(self, reason=None):
        self.latency["image_latency_ms"] = int(
            (time.time() - self._image_start) * 1000
        )
        self.latency["image_success"] = False
        if reason:
            self.latency["image_fail_reason"] = reason
