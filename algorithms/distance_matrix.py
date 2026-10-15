class DistanceMatrix:
    def __init__(self, donor_locations, ngo_ids, distances, default=50):
        self.donor_locations = donor_locations
        self.ngo_ids = ngo_ids
        self.distances = distances
        self.default = default

    def get(self, donor_location, ngo_id):
        if donor_location not in self.donor_locations or ngo_id not in self.ngo_ids:
            return self.default
        row = self.donor_locations.index(donor_location)
        col = self.ngo_ids.index(ngo_id)
        return self.distances[row][col]
