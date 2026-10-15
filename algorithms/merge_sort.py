class MergeSort:
    def __init__(self):
        self.comparisons = 0
        self.recursive_calls = 0

    def sort(self, donations, reverse=False, key="minutes_to_expiry"):
        self.comparisons = 0
        self.recursive_calls = 0
        return self._merge_sort(donations, reverse, key)

    def _merge_sort(self, donations, reverse, key):
        self.recursive_calls += 1
        if len(donations) <= 1:
            return donations
        mid = len(donations) // 2
        left_half = self._merge_sort(donations[:mid], reverse, key)
        right_half = self._merge_sort(donations[mid:], reverse, key)
        return self._merge(left_half, right_half, reverse, key)

    def _merge(self, left, right, reverse, key):
        sorted_list = []
        i = j = 0
        while i < len(left) and j < len(right):
            self.comparisons += 1
            val1 = left[i][key]
            val2 = right[j][key]
            take_left = val1 >= val2 if reverse else val1 <= val2
            if take_left:
                sorted_list.append(left[i])
                i += 1
            else:
                sorted_list.append(right[j])
                j += 1
        sorted_list.extend(left[i:])
        sorted_list.extend(right[j:])
        return sorted_list
