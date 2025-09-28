from flask import Flask, request, jsonify
import hashlib
import datetime

app = Flask(__name__)


@app.route("/certificate", methods=["POST"])
def certificate():
    data = request.get_json()
    # Generar un hash simple como certificado
    cert_data = str(data) + str(datetime.datetime.utcnow())
    certificate = hashlib.sha256(cert_data.encode()).hexdigest()

    return (
        jsonify(
            {"certificate": certificate, "timestamp": str(datetime.datetime.utcnow())}
        ),
        200,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5006, debug=False)
