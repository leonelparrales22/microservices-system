from flask import Flask, request, jsonify
import jwt
import datetime
import hashlib
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Clave secreta para JWT
SECRET_KEY = os.getenv("SECRET_KEY", "mysecretkey")

# Simulación de BD de usuarios
users = {}


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if username in users:
        return jsonify({"error": "User already exists"}), 400

    hashed_password = generate_password_hash(password)
    users[username] = hashed_password

    return jsonify({"message": "User registered successfully"}), 201


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if username not in users or not check_password_hash(users[username], password):
        return jsonify({"error": "Invalid credentials"}), 401

    token = jwt.encode(
        {
            "username": username,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        },
        SECRET_KEY,
        algorithm="HS256",
    )

    return jsonify({"token": token}), 200


@app.route("/validate", methods=["POST"])
def validate():
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "Token missing"}), 401

    try:
        token = token.split(" ")[1]  # Bearer token
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return jsonify({"username": payload["username"]}), 200
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005, debug=False)
