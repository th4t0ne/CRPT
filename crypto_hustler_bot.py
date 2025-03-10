
import requests
import json
from flask import Flask, request, jsonify

# 🔥 Konfiguracja API NOWPayments
NOWPAYMENTS_API_KEY = "TWÓJ_KLUCZ_API"  # Wstaw swój klucz API z NOWPayments
CURRENCY = "BTC"  # Docelowa kryptowaluta

app = Flask(__name__)

# 📌 Funkcja generująca adres do wpłat
def generate_payment_address(user_id, amount, currency="EUR"):
    url = "https://api.nowpayments.io/v1/invoice"
    headers = {
        "x-api-key": NOWPAYMENTS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "price_amount": amount,
        "price_currency": currency,
        "pay_currency": CURRENCY,
        "order_id": str(user_id),
        "order_description": "CryptoHustler Deposit",
    }
    response = requests.post(url, headers=headers, json=payload)
    data = response.json()
    if "invoice_url" in data:
        return data["invoice_url"]  # Link do wpłaty
    else:
        return None

# 📌 Webhook odbierający potwierdzenia wpłat
@app.route("/webhook", methods=["POST"])
def nowpayments_webhook():
    data = request.get_json()
    print("Webhook received:", json.dumps(data, indent=4))

    if not data or "order_id" not in data or "payment_status" not in data:
        return jsonify({"error": "Invalid data"}), 400

    user_id = int(data["order_id"])  # ID użytkownika
    amount_received = float(data["pay_amount"])
    currency = data["pay_currency"]
    
    # Sprawdzenie statusu transakcji
    if data["payment_status"] == "finished":
        update_user_balance(user_id, amount_received)
        return jsonify({"status": "success", "message": "Balance updated"}), 200
    else:
        return jsonify({"status": "pending", "message": "Waiting for payment"}), 202

# 📌 Aktualizacja salda użytkownika
def update_user_balance(user_id, amount):
    try:
        with open("user_data.json", "r+") as f:
            users = json.load(f)
            if str(user_id) in users:
                users[str(user_id)]["balance"] += amount
                print(f"✅ Dodano {amount} {CURRENCY} do użytkownika {user_id}. Nowe saldo: {users[str(user_id)]['balance']}")

                f.seek(0)
                json.dump(users, f, indent=4)
                f.truncate()
                return True
    except Exception as e:
        print(f"Błąd przy aktualizacji salda: {e}")
        return False

if __name__ == "__main__":
    app.run(port=5000, debug=True)
