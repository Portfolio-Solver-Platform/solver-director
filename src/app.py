from flask import Flask, jsonify
from prometheus_flask_exporter import PrometheusMetrics

app = Flask(__name__)
metrics = PrometheusMetrics(app)


@app.route("/", methods=["GET"])
def root():
    return jsonify(status="ok", service="flask-helm-skaffold")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

