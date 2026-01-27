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
