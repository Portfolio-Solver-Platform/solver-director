from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/", methods=["GET"])
def root():
    return jsonify(status="ok", service="flask-helm-skaffold")


if __name__ == "__main__":
    # app.run(host="0.0.0.0", port=8080)

    import os

    host = os.getenv("FLASK_RUN_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8080"))
    app.run(host=host, port=port)
