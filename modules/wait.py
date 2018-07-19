import time

class wait:
    def __init__(self, default, limit):
        self.interval = default
        self.default = default
        self.limit = limit
        self.count = 0

    def wait(self):
        time.sleep(self.interval)
        self.interval = min(self.interval * 2, self.limit)
        self.count += 1

    def reset(self):
        self.interval = self.default
        self.count = 0
