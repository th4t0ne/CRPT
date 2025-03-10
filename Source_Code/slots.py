import random

class SlotMachine:
    def __init__(self, symbols: list, payouts: dict):
        self.symbols = symbols
        self.payouts = payouts

    def spin(self):
        result = [random.choice(self.symbols) for _ in range(3)]
        winnings = self.calculate_winnings(tuple(result))
        return result, winnings

    def calculate_winnings(self, result: tuple) -> float:
        return self.payouts.get(result, 0)
