import os
import json
import time
import random
import requests
import bcrypt
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

# ======================
#  CONFIGURATIONS
# ======================

# NOWPayments API configuration
NOWPAYMENTS_API_KEY = os.environ.get("NOWPAYMENTS_API_KEY")  # from env
CURRENCY = "BTC"  # The target crypto

# JSON file for user data (keeping your JSON storage approach)
USER_DATA_FILE = "user_data.json"

# Flask App
app = Flask(__name__)

# Mining interval (in minutes)
MINING_INTERVAL = 10

# Slot machine cost per spin (in BTC)
SLOT_MACHINE_COST = 0.0001

# ======================
#  HELPER FUNCTIONS
# ======================

def load_user_data():
    """Load users from JSON file."""
    try:
        with open(USER_DATA_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_user_data(data):
    """Save users to JSON file."""
    with open(USER_DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def hash_password(password):
    """Hash a plaintext password."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def verify_password(password, hashed_password):
    """Verify a plaintext password against a hashed password."""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password)

def generate_session_token(user_id):
    """Generate a random session token."""
    return os.urandom(24).hex()

def get_user_by_session_token(session_token):
    """Return (user_id, user_data) given a valid session token, or (None, None) if invalid."""
    users = load_user_data()
    for uid, data in users.items():
        if data.get("session_token") == session_token:
            return uid, data
    return None, None

def get_user_by_id(user_id):
    """Return user data for a given user_id (string or int)."""
    users = load_user_data()
    return users.get(str(user_id), None)

def update_user_balance(user_id, amount):
    """Update user balance after deposit or bonus."""
    users = load_user_data()
    user_id_str = str(user_id)
    if user_id_str in users:
        # First deposit bonus check
        if "first_deposit" not in users[user_id_str]:
            users[user_id_str]["balance"] += amount * 2
            users[user_id_str]["first_deposit"] = True
            print(f"✅ Added {amount * 2} {CURRENCY} (bonus) to user {user_id}. New balance: {users[user_id_str]['balance']}")
        else:
            users[user_id_str]["balance"] += amount
            print(f"✅ Added {amount} {CURRENCY} to user {user_id}. New balance: {users[user_id_str]['balance']}")
        save_user_data(users)
        return True
    else:
        print(f"Error: User {user_id} does not exist.")
        return False

# ======================
#  NOWPAYMENTS INTEGRATION
# ======================

def generate_payment_address(user_id, amount, currency="EUR"):
    """Generate a NOWPayments invoice URL for deposit."""
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
        return data["invoice_url"]
    else:
        return None

@app.route("/webhook", methods=["POST"])
def nowpayments_webhook():
    """NOWPayments webhook to confirm deposits."""
    data = request.get_json()
    print("Webhook received:", json.dumps(data, indent=4))

    if not data or "order_id" not in data or "payment_status" not in data:
        return jsonify({"error": "Invalid data"}), 400

    user_id = data["order_id"]  # This was stored as a string
    amount_received = float(data["pay_amount"])
    # currency = data["pay_currency"]  # We can log it if needed.

    # Check transaction status
    if data["payment_status"] == "finished":
        update_user_balance(user_id, amount_received)
        return jsonify({"status": "success", "message": "Balance updated"}), 200
    else:
        return jsonify({"status": "pending", "message": "Waiting for payment"}), 202

# ======================
#  USER ACCOUNT ROUTES
# ======================

@app.route("/register", methods=["POST"])
def register_user():
    """Register a new user."""
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    users = load_user_data()
    # Check if email is already registered
    for uid, user_data in users.items():
        if user_data.get("email") == email:
            return jsonify({"error": "Email already registered"}), 400

    user_id = len(users) + 1
    hashed_pw = hash_password(password).decode('utf-8')

    users[str(user_id)] = {
        "email": email,
        "password": hashed_pw,
        "balance": 0.0,
        "session_token": generate_session_token(user_id),
        "last_passive_mine": datetime.now().isoformat(),
        "next_quiz_attempt": datetime.now().isoformat(),
        "slot_machine_unlocked": False,
        "first_deposit": False  # track if deposit bonus used
    }
    save_user_data(users)

    return jsonify({
        "message": "User registered successfully",
        "session_token": users[str(user_id)]["session_token"]
    }), 201

@app.route("/login", methods=["POST"])
def login_user():
    """Login an existing user."""
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    users = load_user_data()
    for uid, user_data in users.items():
        if user_data.get("email") == email:
            # Verify password
            if verify_password(password, user_data["password"].encode('utf-8')):
                # Generate new session token
                new_token = generate_session_token(uid)
                users[uid]["session_token"] = new_token
                save_user_data(users)
                return jsonify({"message": "Login successful", "session_token": new_token}), 200

    return jsonify({"error": "Invalid email or password"}), 401

@app.route("/logout", methods=["POST"])
def logout_user():
    """Log out the current user."""
    session_token = request.headers.get("Authorization")
    if not session_token:
        return jsonify({"error": "Session token required"}), 401

    users = load_user_data()
    for uid, user_data in users.items():
        if user_data["session_token"] == session_token:
            users[uid]["session_token"] = None
            save_user_data(users)
            return jsonify({"message": "Logged out successfully"}), 200

    return jsonify({"error": "Invalid session token"}), 401

# ======================
#  DASHBOARD & COMMANDS
# ======================

@app.route("/start", methods=["GET"])
def start_command():
    """
    /start → Show an introduction if not logged in.
             If logged in, show a "dashboard" with user balance and available commands.
    """
    session_token = request.headers.get("Authorization")
    if not session_token:
        # Not logged in
        return jsonify({
            "intro": "Welcome to the Crypto Hustler Bot!",
            "prompt": "Please log in or register to continue.",
            "commands": ["/register", "/login"]
        }), 200
    else:
        user_id, user_data = get_user_by_session_token(session_token)
        if not user_id:
            # Invalid token
            return jsonify({
                "error": "Invalid session token. Please log in again."
            }), 401
        # Logged in - show dashboard
        return jsonify({
            "message": "Welcome to your dashboard!",
            "balance": user_data["balance"],
            "available_commands": [
                "/balance",
                "/tasks",
                "/mine",
                "/quiz",
                "/slots",
                "/deposit <amount>",
                "/logout"
            ]
        }), 200

@app.route("/balance", methods=["GET"])
def balance_command():
    """ /balance -> Display the user's current balance. """
    session_token = request.headers.get("Authorization")
    if not session_token:
        return jsonify({"error": "You must be logged in to see your balance."}), 401

    user_id, user_data = get_user_by_session_token(session_token)
    if not user_id:
        return jsonify({"error": "Invalid session token"}), 401

    return jsonify({
        "message": f"Your current balance is {user_data['balance']} {CURRENCY}."
    }), 200

@app.route("/tasks", methods=["GET"])
def tasks_command():
    """
    /tasks -> List available tasks (e.g., quiz, mining, slot machine).
    Could be expanded to show more tasks if desired.
    """
    session_token = request.headers.get("Authorization")
    if not session_token:
        return jsonify({"error": "You must be logged in."}), 401

    user_id, user_data = get_user_by_session_token(session_token)
    if not user_id:
        return jsonify({"error": "Invalid session token"}), 401

    return jsonify({
        "available_tasks": [
            "Passive Mining (/mine to claim)",
            "AI Quiz (/quiz)",
            "Slot Machine (/slots)"
        ]
    }), 200

# ======================
#  PASSIVE MINING
# ======================

def mining_ascii_progress():
    """
    Returns a simple ASCII progress bar or animation string.
    In a real Telegram bot scenario, you'd update messages incrementally,
    but here we just return a final string.
    """
    bar = [
        "[=         ] 10%",
        "[==        ] 20%",
        "[===       ] 30%",
        "[====      ] 40%",
        "[=====     ] 50%",
        "[======    ] 60%",
        "[=======   ] 70%",
        "[========  ] 80%",
        "[========= ] 90%",
        "[==========] 100%"
    ]
    # Join into a single string with line breaks
    return "\n".join(bar)

@app.route("/mine", methods=["POST"])
def mine_command():
    """
    /mine -> Claim passive mining rewards if at least MINING_INTERVAL minutes have passed.
    Displays a small ASCII progress bar for flavor.
    """
    session_token = request.headers.get("Authorization")
    if not session_token:
        return jsonify({"error": "You must be logged in."}), 401

    user_id, user_data = get_user_by_session_token(session_token)
    if not user_id:
        return jsonify({"error": "Invalid session token"}), 401

    last_mine_time = datetime.fromisoformat(user_data["last_passive_mine"])
    now = datetime.now()

    # Check if enough time has passed
    if now - last_mine_time >= timedelta(minutes=MINING_INTERVAL):
        # Calculate random mining reward
        mined_amount = random.uniform(0.0001, 0.001)
        # Update balance
        users = load_user_data()
        users[user_id]["balance"] += mined_amount
        # Update last_mine time
        users[user_id]["last_passive_mine"] = now.isoformat()
        save_user_data(users)

        progress_bar = mining_ascii_progress()
        return jsonify({
            "animation": progress_bar,
            "message": f"Mining complete! You have mined {mined_amount:.6f} {CURRENCY}.",
            "new_balance": users[user_id]["balance"]
        }), 200
    else:
        # Not enough time has passed
        remaining = (last_mine_time + timedelta(minutes=MINING_INTERVAL)) - now
        return jsonify({
            "error": f"You must wait {remaining.seconds//60} minutes and {remaining.seconds%60} seconds before mining again."
        }), 400

# ======================
#  AI-STYLE QUIZ
# ======================

# Simple local question generator mimicking AI dynamic generation
QUIZ_QUESTIONS = [
    {
        "question": "Which of the following is the first decentralized cryptocurrency?",
        "options": ["Ethereum", "Bitcoin", "Litecoin", "Ripple"],
        "answer_index": 1  # 0-based index (Bitcoin)
    },
    {
        "question": "What is the purpose of blockchain consensus algorithms?",
        "options": [
            "Generate random numbers",
            "Securely agree on the state of the ledger",
            "Create user interfaces",
            "Store private keys"
        ],
        "answer_index": 1
    },
    {
        "question": "Which term describes the maximum number of coins that will exist for Bitcoin?",
        "options": ["Market Cap", "Blockchain Size", "Coin Supply", "Max Supply of 21 million"],
        "answer_index": 3
    },
    {
        "question": "Which crypto platform introduced smart contracts first?",
        "options": ["Cardano", "Ethereum", "Tron", "Polkadot"],
        "answer_index": 1
    },
    {
        "question": "What does 'HODL' mean in crypto slang?",
        "options": [
            "A type of hardware wallet",
            "Hold on for dear life",
            "Hackers only do Litecoin",
            "A new coin listing"
        ],
        "answer_index": 1
    },
]

def get_random_quiz_question():
    """Return a random question dict from QUIZ_QUESTIONS."""
    return random.choice(QUIZ_QUESTIONS)

@app.route("/quiz", methods=["GET", "POST"])
def quiz_command():
    """
    /quiz:
      - GET: Start or fetch the current quiz question
      - POST: Submit answer -> check correctness, reward, or apply cooldown
    """
    session_token = request.headers.get("Authorization")
    if not session_token:
        return jsonify({"error": "You must be logged in."}), 401

    user_id, user_data = get_user_by_session_token(session_token)
    if not user_id:
        return jsonify({"error": "Invalid session token"}), 401

    users = load_user_data()
    if request.method == "GET":
        # Check cooldown
        next_attempt_time = datetime.fromisoformat(user_data["next_quiz_attempt"])
        now = datetime.now()
        if now < next_attempt_time:
            wait_seconds = (next_attempt_time - now).seconds
            return jsonify({
                "error": f"You are on a cooldown. Please wait {wait_seconds} seconds before trying again."
            }), 400

        # Generate a random question
        question_data = get_random_quiz_question()
        # Store it on user data so we can check on POST
        users[user_id]["current_question"] = question_data
        # Save
        save_user_data(users)

        return jsonify({
            "question": question_data["question"],
            "options": question_data["options"]
        }), 200

    elif request.method == "POST":
        data = request.get_json()
        chosen_index = data.get("chosen_index")

        if "current_question" not in users[user_id]:
            return jsonify({"error": "No active quiz question. Please GET /quiz first."}), 400

        current_q = users[user_id]["current_question"]

        # Basic validation
        if chosen_index is None or not isinstance(chosen_index, int):
            return jsonify({"error": "Invalid answer index."}), 400

        if chosen_index == current_q["answer_index"]:
            # Correct answer
            reward = random.uniform(0.00001, 0.00005)  # Adjust your reward
            users[user_id]["balance"] += reward
            # Clear current question and cooldown only if correct to allow immediate new question
            del users[user_id]["current_question"]
            # Save
            save_user_data(users)
            return jsonify({
                "message": f"Correct! You earned {reward:.8f} {CURRENCY}.",
                "new_balance": users[user_id]["balance"]
            }), 200
        else:
            # Incorrect - impose cooldown (e.g. 1 minute)
            cooldown_minutes = 1
            next_time = datetime.now() + timedelta(minutes=cooldown_minutes)
            users[user_id]["next_quiz_attempt"] = next_time.isoformat()
            # Clear question
            if "current_question" in users[user_id]:
                del users[user_id]["current_question"]
            save_user_data(users)
            return jsonify({
                "message": "Incorrect answer. You must wait before trying again.",
                "cooldown_until": next_time.isoformat()
            }), 200

# ======================
#  SLOT MACHINE GAME
# ======================

def slot_machine_ascii(reels):
    """
    Returns an ASCII representation of the slot reels, e.g.:

    -------------
    | A | B | C |
    -------------
    """
    top_bottom = "-" * 13
    return f"{top_bottom}\n| {reels[0]} | {reels[1]} | {reels[2]} |\n{top_bottom}"

@app.route("/slots", methods=["POST"])
def slots_command():
    """
    /slots -> Play the slot machine game:
       - Deduct cost from balance
       - Spin reels, random symbols
       - If 3 match: jackpot
       - If 2 match: small win
       - Else: lose
    """
    session_token = request.headers.get("Authorization")
    if not session_token:
        return jsonify({"error": "You must be logged in."}), 401

    user_id, user_data = get_user_by_session_token(session_token)
    if not user_id:
        return jsonify({"error": "Invalid session token"}), 401

    # Check balance
    if user_data["balance"] < SLOT_MACHINE_COST:
        return jsonify({"error": f"Insufficient balance. You need at least {SLOT_MACHINE_COST} {CURRENCY}."}), 400

    symbols = ["A", "B", "C", "D", "7", "X"]
    # Deduct cost
    users = load_user_data()
    users[user_id]["balance"] -= SLOT_MACHINE_COST

    # Spin reels
    reel_results = [random.choice(symbols) for _ in range(3)]

    # Check outcome
    if reel_results[0] == reel_results[1] == reel_results[2]:
        # JACKPOT
        jackpot_prize = random.uniform(0.001, 0.002)  # Adjust jackpot range
        users[user_id]["balance"] += jackpot_prize
        outcome = f"JACKPOT! You win {jackpot_prize:.6f} {CURRENCY}!"
    elif reel_results[0] == reel_results[1] or reel_results[1] == reel_results[2] or reel_results[0] == reel_results[2]:
        # SMALL WIN
        small_win = random.uniform(0.00005, 0.0001)
        users[user_id]["balance"] += small_win
        outcome = f"You matched 2 symbols! You win {small_win:.6f} {CURRENCY}."
    else:
        # LOSS
        outcome = "No match. Better luck next time!"

    save_user_data(users)

    ascii_art = slot_machine_ascii(reel_results)
    return jsonify({
        "animation": ascii_art,
        "result": reel_results,
        "outcome": outcome,
        "new_balance": users[user_id]["balance"]
    }), 200

# ======================
#  DEPOSIT COMMAND
# ======================

@app.route("/deposit", methods=["POST"])
def deposit_command():
    """
    /deposit amount -> Generate a crypto deposit address (NOWPayments invoice link).
    """
    session_token = request.headers.get("Authorization")
    if not session_token:
        return jsonify({"error": "You must be logged in."}), 401

    user_id, user_data = get_user_by_session_token(session_token)
    if not user_id:
        return jsonify({"error": "Invalid session token"}), 401

    data = request.get_json()
    amount = data.get("amount", 0)

    if amount <= 0:
        return jsonify({"error": "Please specify a valid deposit amount in fiat (e.g. EUR)."}), 400

    invoice_url = generate_payment_address(user_id, amount, currency="EUR")
    if invoice_url:
        return jsonify({
            "message": "Use the following link to complete your deposit:",
            "invoice_url": invoice_url
        }), 200
    else:
        return jsonify({"error": "Failed to generate deposit address."}), 500


# ======================
#  USER INFO (IF NEEDED)
# ======================

@app.route("/user_info", methods=["GET"])
def user_info():
    """Debug endpoint to return all user info fields."""
    session_token = request.headers.get("Authorization")
    if not session_token:
        return jsonify({"error": "Session token required"}), 401

    uid, user_data = get_user_by_session_token(session_token)
    if not uid:
        return jsonify({"error": "Invalid session token"}), 401

    return jsonify({
        "email": user_data["email"],
        "balance": user_data["balance"],
        "last_passive_mine": user_data["last_passive_mine"],
        "next_quiz_attempt": user_data["next_quiz_attempt"],
        "slot_machine_unlocked": user_data["slot_machine_unlocked"]
    }), 200

# ======================
#  MAIN
# ======================

if __name__ == "__main__":
    # For production, run via WSGI (gunicorn, etc.). For local dev, you can do:
    app.run(debug=True, port=5000)
