import copy
import unittest

from algorithms.distance_matrix import DistanceMatrix
from algorithms.greedy_allocation import GreedyAllocation
from algorithms.hash_table import HashTable
from algorithms.merge_sort import MergeSort
from algorithms.priority_queue import PriorityQueue
from algorithms.search import Search
from algorithms.stack import Stack
from allocation_service import default_matrix, default_ngos

ITEMS = [
    {"id": 5, "food_type": "Cooked Meals", "quantity": 50, "unit": "portions", "minutes_to_expiry": 120, "status": "Pending", "donor_location": "Fayoum"},
    {"id": 1, "food_type": "Bakery", "quantity": 120, "unit": "items", "minutes_to_expiry": 45, "status": "Pending", "donor_location": "Cairo"},
    {"id": 8, "food_type": "Fruits & Vegetables", "quantity": 80, "unit": "kg", "minutes_to_expiry": 300, "status": "Allocated", "donor_location": "Giza"},
    {"id": 2, "food_type": "Dairy", "quantity": 30, "unit": "liters", "minutes_to_expiry": 90, "status": "Pending", "donor_location": "Giza"},
    {"id": 4, "food_type": "Cooked Meals", "quantity": 40, "unit": "portions", "minutes_to_expiry": 60, "status": "Pending", "donor_location": "Cairo"},
]


def fresh():
    return copy.deepcopy(ITEMS)


class TestMergeSort(unittest.TestCase):
    def test_sorts_both_directions(self):
        asc = [d["minutes_to_expiry"] for d in MergeSort().sort(fresh())]
        desc = [d["minutes_to_expiry"] for d in MergeSort().sort(fresh(), reverse=True)]
        self.assertEqual(asc, [45, 60, 90, 120, 300])
        self.assertEqual(desc, [300, 120, 90, 60, 45])

    def test_edge_cases(self):
        self.assertEqual(MergeSort().sort([]), [])
        self.assertEqual(len(MergeSort().sort(fresh()[:1])), 1)

    def test_input_is_not_changed(self):
        data = fresh()
        MergeSort().sort(data)
        self.assertEqual(data, fresh())

    def test_counters(self):
        sorter = MergeSort()
        sorter.sort(fresh())
        self.assertEqual(sorter.comparisons, 8)
        self.assertEqual(sorter.recursive_calls, 9)

    def test_sort_by_id(self):
        ids = [d["id"] for d in MergeSort().sort(fresh(), key="id")]
        self.assertEqual(ids, [1, 2, 4, 5, 8])


class TestSearch(unittest.TestCase):
    def test_linear(self):
        search = Search()
        self.assertEqual(search.linear_search(fresh(), 2)["id"], 2)
        self.assertEqual(search.comparisons, 4)
        self.assertIsNone(search.linear_search(fresh(), 99))

    def test_binary_on_sorted_data(self):
        by_id = MergeSort().sort(fresh(), key="id")
        for i in (1, 2, 4, 5, 8):
            self.assertEqual(Search().binary_search(by_id, i)["id"], i)
        self.assertIsNone(Search().binary_search(by_id, 3))

    def test_binary_needs_sorted_data(self):
        misses = [i for i in (1, 2, 4, 5, 8) if Search().binary_search(fresh(), i) is None]
        self.assertTrue(misses)

    def test_binary_beats_linear(self):
        big = [{"id": i} for i in range(1, 1001)]
        linear, binary = Search(), Search()
        linear.linear_search(big, 1000)
        binary.binary_search(big, 1000)
        self.assertLess(binary.comparisons, linear.comparisons)

    def test_find_by_status(self):
        self.assertEqual(len(Search().find_by_status(fresh(), "Pending")), 4)


class TestHashTable(unittest.TestCase):
    def test_insert_get_update(self):
        table = HashTable(capacity=3)
        for d in fresh():
            table.insert(d["id"], d)
        self.assertEqual(table.get(4)["id"], 4)
        self.assertIsNone(table.get(99))
        table.insert(4, {"id": 4, "x": 1})
        self.assertEqual(table.size, 5)
        self.assertEqual(table.get(4)["x"], 1)

    def test_collisions(self):
        table = HashTable(capacity=1)
        for d in fresh():
            table.insert(d["id"], d)
        self.assertEqual(table.collisions(), 4)
        self.assertEqual(table.get(8)["id"], 8)


class TestPriorityQueue(unittest.TestCase):
    def test_order(self):
        queue = PriorityQueue()
        for d in fresh():
            queue.push(d)
        self.assertEqual([queue.pop()["id"] for _ in range(5)], [1, 4, 2, 5, 8])

    def test_empty(self):
        queue = PriorityQueue()
        self.assertTrue(queue.is_empty())
        self.assertIsNone(queue.pop())
        self.assertIsNone(queue.peek())

    def test_sorted_list_keeps_queue(self):
        queue = PriorityQueue()
        for d in fresh():
            queue.push(d)
        queue.to_sorted_list()
        self.assertEqual(queue.size(), 5)


class TestStack(unittest.TestCase):
    def test_lifo(self):
        stack = Stack()
        stack.push(1)
        stack.push(2)
        self.assertEqual(stack.pop(), 2)
        self.assertEqual(stack.peek(), 1)
        stack.pop()
        self.assertIsNone(stack.pop())


class TestDistanceMatrix(unittest.TestCase):
    def test_lookup(self):
        self.assertEqual(default_matrix.get("Cairo", 4), 6)
        self.assertEqual(default_matrix.get("Alexandria", 5), 6)

    def test_unknown_uses_default(self):
        self.assertEqual(DistanceMatrix(["A"], [1], [[3]], default=77).get("B", 1), 77)


class TestGreedy(unittest.TestCase):
    def setUp(self):
        self.ngos = copy.deepcopy(default_ngos)
        self.greedy = GreedyAllocation(default_matrix)

    def test_picks_fastest_eligible(self):
        rec = self.greedy.recommend(fresh()[1], self.ngos)
        self.assertEqual(rec["ngo"]["name"], "Bread for All")
        self.assertTrue(rec["reasons"])

    def test_no_match(self):
        impossible = dict(fresh()[1], quantity=100000)
        rec = self.greedy.recommend(impossible, self.ngos)
        self.assertIsNone(rec["ngo"])
        self.assertTrue(rec["rejected"])

    def test_too_late(self):
        tight = dict(fresh()[1], minutes_to_expiry=5)
        self.assertIsNone(self.greedy.recommend_ngo(tight, self.ngos))

    def test_food_type_filter(self):
        names = [n["name"] for n in self.greedy.find_eligible_ngos(fresh()[3], self.ngos)]
        self.assertNotIn("Bread for All", names)

    def test_consume_and_restore(self):
        ngo = self.ngos[3]
        self.greedy.consume(ngo, "items", 120)
        self.assertEqual(ngo["remaining_capacity"]["items"], 80)
        self.greedy.restore(ngo, "items", 120)
        self.assertEqual(ngo["remaining_capacity"]["items"], 200)

    def test_baseline_is_first_eligible(self):
        ngo = self.greedy.baseline_recommend(fresh()[1], self.ngos)
        self.assertEqual(ngo["name"], "Cairo Food Bank")


if __name__ == "__main__":
    unittest.main()
