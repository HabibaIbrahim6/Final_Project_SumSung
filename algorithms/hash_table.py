class HashTable:
    def __init__(self, capacity=11):
        self.capacity = capacity
        self.buckets = [[] for _ in range(capacity)]
        self.size = 0
        self.comparisons = 0

    def _hash(self, key):
        return key % self.capacity

    def insert(self, key, value):
        bucket = self.buckets[self._hash(key)]
        for pair in bucket:
            if pair[0] == key:
                pair[1] = value
                return
        bucket.append([key, value])
        self.size += 1

    def get(self, key):
        self.comparisons = 0
        bucket = self.buckets[self._hash(key)]
        for k, v in bucket:
            self.comparisons += 1
            if k == key:
                return v
        return None

    def collisions(self):
        return sum(len(b) - 1 for b in self.buckets if len(b) > 1)
