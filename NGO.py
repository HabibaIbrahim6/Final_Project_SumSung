class NGO:
    def __init__(self, ngo_id, name, address, capacity, food_list):
        self.ngo_id = str(ngo_id)
        self.name = name
        self.address = address
        self.capacity = float(capacity) 
        self.food_list = food_list 

    def to_dict(self):
        return {
            "ngo_id": self.ngo_id,
            "name": self.name,
            "address": self.address,
            "capacity": self.capacity,
            "food_list": self.food_list
        }

    @staticmethod
    def get_static_ngos():
        return [
            NGO(ngo_id="1", name="Resala Charity", address="Cairo", capacity=150.0, food_list=["Rice", "Pasta", "Meat"]),
            NGO(ngo_id="2", name="Egyptian Food Bank", address="Giza", capacity=300.0, food_list=["Rice", "Vegetables", "Chicken"]),
            NGO(ngo_id="3", name="Dar Al Orman", address="Giza", capacity=100.0, food_list=["Pasta", "Bread", "Meat"])
        ]