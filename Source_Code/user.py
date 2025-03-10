import random

class User:
    def __init__(self, user_id: int, username: str = None, language: str = "pl"):
        self.user_id = user_id
        self.username = username
        self.balance = 0
        self.completed_tasks = 0
        self.referral_earnings = 0
        self.referral_code = self.generate_referral_code()
        self.referred_by = None
        self.language = language

    def generate_referral_code(self):
        return f"REF-{self.user_id}-{random.randint(1000, 9999)}"
