"""Atomic in-memory Redis contract double; never used by production code."""


class MemoryExecutionStore:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def eval(self, script, count, key):
        # No awaits inside the transition: model Redis Lua atomicity.
        state = self.values.get(key)
        if "return -1" in script:
            if state is None:
                return -1
            self.values[key] = "sealed"
            return int(state == "cancelling")
        if state is None:
            return 0
        if state == "sealed":
            return 2
        self.values[key] = "cancelling"
        return 1

    async def expire(self, key, ttl):
        return key in self.values

    async def aclose(self):
        pass
