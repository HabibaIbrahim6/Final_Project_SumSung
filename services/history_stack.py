"""Bounded last-in-first-out history for distribution undo."""


class EmptyStackError(Exception):
    pass


class HistoryStack:
    def __init__(self, max_size=None):
        if max_size is not None and (not isinstance(max_size, int) or max_size < 1):
            raise ValueError("max_size must be a positive integer or None.")
        self._items = []
        self._max_size = max_size

    def push(self, item):
        self._items.append(item)
        if self._max_size is not None and len(self._items) > self._max_size:
            del self._items[0]

    def pop(self):
        if not self._items:
            raise EmptyStackError("The history stack is empty.")
        return self._items.pop()

    def peek(self):
        if not self._items:
            raise EmptyStackError("The history stack is empty.")
        return self._items[-1]

    def is_empty(self):
        return not self._items

    def clear(self):
        self._items.clear()

    def as_list(self):
        return list(reversed(self._items))
