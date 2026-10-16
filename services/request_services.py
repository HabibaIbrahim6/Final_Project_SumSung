from collections import deque

class RequestService:
    def __init__(self):
        self.request_queue = deque()
        self.pending_offers = []

    def add_request(self, item, ngo_name):
        request_data = {
            "id": str(len(self.pending_offers) + 1),
            "item": item,
            "ngo_name": ngo_name,
            "status": "Pending"
        }
        self.request_queue.append(request_data)
        self.pending_offers.append(request_data)

    def get_next_request(self):
        if self.request_queue:
            return self.request_queue.popleft()
        return None

    def respond_to_offer(self, offer, ngo_name, accepted: bool):
        status = "Accepted" if accepted else "Rejected"
        offer["status"] = status
        return True, f"Offer {status} successfully"

# نسخة عامة تستخدم مباشرة في صفحات الـ Streamlit
request_service = RequestService()