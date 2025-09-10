from flask import Flask, jsonify
from prometheus_flask_exporter import PrometheusMetrics

app = Flask(__name__)
metrics = PrometheusMetrics(app)


@app.route("/", methods=["GET"])
def root():
    return jsonify(status="ok", service="flask-helm-skaffold")


if __name__ == "__main__":
    import os

    host = os.getenv("FLASK_RUN_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8080"))
    app.run(host=host, port=port)
