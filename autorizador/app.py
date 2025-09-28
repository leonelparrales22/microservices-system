from flask import Flask, request, jsonify, g
import jwt
import datetime
import os
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)

# Clave secreta (usar variable de entorno en producción)
SECRET_KEY = os.getenv("SECRET_KEY", "mysecretkey")
JWT_ALGORITHM = "HS256"

# Simulación de "base de datos" en memoria
# Estructura: users[username] = {"pwd": hash, "org": "orgA", "roles": ["client", ...]}
users = {}


def create_token(username):
    """Crea un JWT con claims: sub, org, roles, iat, exp"""
    user = users[username]
    now = datetime.datetime.utcnow()
    payload = {
        "sub": username,
        "org": user.get("org"),
        "roles": user.get("roles", []),
        "iat": now,
        "exp": now + datetime.timedelta(hours=1)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def jwt_required(f):
    """Decorator simple para validar token y exponer claims en flask.g"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", None)
        if not auth:
            return jsonify({"error": "authorization required"}), 401
        parts = auth.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return jsonify({"error": "invalid authorization header"}), 401
        token = parts[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
            # Attach claims to g for handlers that may use them
            g.current_user = payload.get("sub")
            g.current_org = payload.get("org")
            g.current_roles = payload.get("roles", [])
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "invalid token"}), 401
    return wrapper


def roles_required(*required_roles):
    """Decorator opcional para endpoints que quieran exigir roles.
       (No se usa en los 3 endpoints básicos, pero queda disponible.)"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user_roles = getattr(g, "current_roles", [])
            if not set(user_roles).intersection(set(required_roles)):
                return jsonify({"error": "forbidden - missing role"}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator


@app.route("/register", methods=["POST"])
def register():
    """
    Payload JSON esperado:
    {
      "username": "alice",
      "password": "secret",
      "org": "orgA",            # opcional, por defecto "orgA"
      "roles": ["client"]       # opcional, por defecto ["client"]
    }
    """
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    org = data.get("org", "orgA")
    roles = data.get("roles", ["client"])

    if not username or not password:
        return jsonify({"error": "username and password required"}), 400

    if username in users:
        return jsonify({"error": "User already exists"}), 400

    hashed_password = generate_password_hash(password)
    users[username] = {"pwd": hashed_password, "org": org, "roles": roles}
    return jsonify({"message": "User registered successfully"}), 201


@app.route("/login", methods=["POST"])
def login():
    """
    Payload JSON esperado:
    { "username": "alice", "password": "secret" }
    Retorna: { "token": "..." }
    """
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "username and password required"}), 400

    user = users.get(username)
    if not user or not check_password_hash(user["pwd"], password):
        return jsonify({"error": "Invalid credentials"}), 401

    token = create_token(username)
    return jsonify({"token": token}), 200


@app.route("/validate", methods=["POST"])
@jwt_required
def validate():
    """
    Endpoint protegido que valida el token y devuelve los claims del mismo.
    Útil para que el frontend/otro servicio confirme identidad y roles.
    """
    return jsonify({
        "username": g.current_user,
        "org": g.current_org,
        "roles": g.current_roles
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005, debug=False)
