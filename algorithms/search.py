class Search:
    def __init__(self):
        self.comparisons = 0

    def linear_search(self, donations, donation_id):
        self.comparisons = 0
        for donation in donations:
            self.comparisons += 1
            if donation["id"] == donation_id:
                return donation
        return None
    #the Time Complexity of the Binary  Search O( log n )
    def binary_search(self, donations, donation_id):
        self.comparisons = 0
        left, right = 0, len(donations) - 1
        while left <= right:
            mid = (left + right) // 2
            current_id = donations[mid]["id"]
            self.comparisons += 1
            if current_id == donation_id:
                return donations[mid]
            elif current_id < donation_id:
                left = mid + 1
            else:
                right = mid - 1
        return None

    def find_by_status(self, donations, status):
        result = []
        for donation in donations:
            if donation["status"] == status:
                result.append(donation)
        return result
