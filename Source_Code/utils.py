import json

def load_data():
    try:
        with open("user_data.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
