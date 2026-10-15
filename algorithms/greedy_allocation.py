from algorithms.merge_sort import MergeSort

TRAVEL_MIN_PER_KM = 1.5


class GreedyAllocation:
    def __init__(self, distance_matrix=None):
        self.distance_matrix = distance_matrix
        self.comparisons = 0

    @staticmethod
    def capacity_for(ngo, unit):
        cap = ngo["remaining_capacity"]
        if isinstance(cap, dict):
            return cap.get(unit, 0)
        return cap if ngo.get("unit") == unit else 0

    @staticmethod
    def consume(ngo, unit, qty):
        if isinstance(ngo["remaining_capacity"], dict):
            ngo["remaining_capacity"][unit] = round(ngo["remaining_capacity"][unit] - qty, 2)
        else:
            ngo["remaining_capacity"] = round(ngo["remaining_capacity"] - qty, 2)

    @staticmethod
    def restore(ngo, unit, qty):
        if isinstance(ngo["remaining_capacity"], dict):
            ngo["remaining_capacity"][unit] = round(ngo["remaining_capacity"][unit] + qty, 2)
        else:
            ngo["remaining_capacity"] = round(ngo["remaining_capacity"] + qty, 2)

    def distance_km(self, donation, ngo):
        if self.distance_matrix is None:
            return 0
        return self.distance_matrix.get(donation["donor_location"], ngo["id"])

    def total_minutes(self, donation, ngo):
        return ngo["pickup_time_minutes"] + self.distance_km(donation, ngo) * TRAVEL_MIN_PER_KM

    def check(self, donation, ngo):
        self.comparisons += 1
        if donation["food_type"] not in ngo["accepted_food_types"]:
            return False, f"does not accept {donation['food_type']}"
        cap = self.capacity_for(ngo, donation["unit"])
        if cap < donation["quantity"]:
            return False, f"not enough capacity ({cap:g} {donation['unit']} left, needs {donation['quantity']:g})"
        total = self.total_minutes(donation, ngo)
        if total > donation["minutes_to_expiry"]:
            return False, f"too slow ({round(total)} min needed, food expires in {donation['minutes_to_expiry']} min)"
        return True, ""

    def find_eligible_ngos(self, donation, ngos):
        return [n for n in ngos if self.check(donation, n)[0]]

    def rank_ngos(self, donation, ngos):
        candidates = []
        for ngo in self.find_eligible_ngos(donation, ngos):
            total = self.total_minutes(donation, ngo)
            candidates.append({
                "ngo": ngo,
                "distance_km": self.distance_km(donation, ngo),
                "total_minutes": round(total, 1),
                "score": round(total, 1),
            })
        sorter = MergeSort()
        ranked = sorter.sort(candidates, key="score")
        self.comparisons += sorter.comparisons
        return ranked

    def recommend(self, donation, ngos):
        self.comparisons = 0
        ranked = self.rank_ngos(donation, ngos)

        rejected = []
        for ngo in ngos:
            ok, why = self.check(donation, ngo)
            if not ok:
                rejected.append({"ngo": ngo, "reason": why})

        if not ranked:
            return {"ngo": None, "reasons": ["No NGO can accept this donation in time."],
                    "ranked": [], "rejected": rejected, "comparisons": self.comparisons}

        best = ranked[0]
        ngo = best["ngo"]
        cap = self.capacity_for(ngo, donation["unit"])
        buffer = donation["minutes_to_expiry"] - best["total_minutes"]

        reasons = [
            f"Accepts {donation['food_type']}.",
            f"Has capacity: {cap:g} {donation['unit']} left (donation is {donation['quantity']:g}).",
            f"{best['distance_km']} km away, collected in about {round(best['total_minutes'])} min "
            f"({round(buffer)} min before expiry).",
        ]
        if len(ranked) > 1:
            reasons.append(f"Fastest of {len(ranked)} eligible NGOs.")
        else:
            reasons.append("Only eligible NGO.")

        return {"ngo": ngo, "reasons": reasons, "ranked": ranked, "rejected": rejected,
                "total_minutes": best["total_minutes"], "distance_km": best["distance_km"],
                "comparisons": self.comparisons}

    def recommend_ngo(self, donation, ngos):
        return self.recommend(donation, ngos)["ngo"]

    def baseline_recommend(self, donation, ngos):
        for ngo in ngos:
            if self.check(donation, ngo)[0]:
                return ngo
        return None
