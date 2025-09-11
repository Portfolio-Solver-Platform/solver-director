from flask import Flask, jsonify
import os
import psycopg2
from datetime import datetime

app = Flask(__name__)


@app.route("/", methods=["GET"])
def root():
    return jsonify(status="ok", service="flask-helm-skaffold")


@app.route("/test-db", methods=["GET"])
def test_db():
    try:
        # Connect to database
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
        )

        with conn.cursor() as cur:
            # Create a simple test table if it doesn't exist
            cur.execute("""
                CREATE TABLE IF NOT EXISTS test_table (
                    id SERIAL PRIMARY KEY,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Insert a test record
            test_message = f"Test message at {datetime.now()}"
            cur.execute(
                "INSERT INTO test_table (message) VALUES (%s) RETURNING id",
                (test_message,),
            )
            inserted_id = cur.fetchone()[0]

            # Retrieve the record
            cur.execute(
                "SELECT id, message, created_at FROM test_table WHERE id = %s",
                (inserted_id,),
            )
            record = cur.fetchone()

            conn.commit()

        conn.close()

        return jsonify(
            {
                "status": "success",
                "database_test": "passed",
                "inserted_record": {
                    "id": record[0],
                    "message": record[1],
                    "created_at": record[2].isoformat(),
                },
            }
        )

    except Exception as e:
        return jsonify(
            {"status": "error", "database_test": "failed", "error": str(e)}
        ), 500


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    app.run(host="127.0.0.1", port=5000, debug=debug_mode)
