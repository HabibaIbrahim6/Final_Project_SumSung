class PriorityQueue:
    def __init__(self, key="minutes_to_expiry"):
        self.heap = []
        self.key = key
        self.comparisons = 0

    def is_empty(self):
        return len(self.heap) == 0

    def size(self):
        return len(self.heap)

    def peek(self):
        return None if self.is_empty() else self.heap[0]

    def push(self, donation):
        self.heap.append(donation)
        self._heapify_up(len(self.heap) - 1)

    def pop(self):
        if self.is_empty():
            return None
        if len(self.heap) == 1:
            return self.heap.pop()
        most_urgent = self.heap[0]
        self.heap[0] = self.heap.pop()
        self._heapify_down(0)
        return most_urgent

    def to_sorted_list(self):
        copy = PriorityQueue(self.key)
        copy.heap = list(self.heap)
        result = []
        while not copy.is_empty():
            result.append(copy.pop())
        self.comparisons += copy.comparisons
        return result

    def _heapify_up(self, index):
        while index > 0:
            parent = (index - 1) // 2
            self.comparisons += 1
            if self.heap[index][self.key] >= self.heap[parent][self.key]:
                break
            self.heap[index], self.heap[parent] = self.heap[parent], self.heap[index]
            index = parent

    def _heapify_down(self, index):
        size = len(self.heap)
        while True:
            smallest = index
            left = 2 * index + 1
            right = 2 * index + 2
            if left < size:
                self.comparisons += 1
                if self.heap[left][self.key] < self.heap[smallest][self.key]:
                    smallest = left
            if right < size:
                self.comparisons += 1
                if self.heap[right][self.key] < self.heap[smallest][self.key]:
                    smallest = right
            if smallest == index:
                break
            self.heap[index], self.heap[smallest] = self.heap[smallest], self.heap[index]
            index = smallest
