#!/usr/bin/env bash
  set -e

  echo "Starting port-forward to postgres..."
  kubectl port-forward -n psp svc/postgres-postgresql 5432:5432 &
  PORT_FORWARD_PID=$!

  # Wait for port-forward to be ready
  sleep 3

  echo "Upgrading database..."
  DATABASE_URL="postgresql://appuser:devpassword123@localhost:5432/appdb" \
      alembic upgrade head

  # Clean up
  kill $PORT_FORWARD_PID
  wait $PORT_FORWARD_PID 2>/dev/null || true

  echo ""
  echo "✓ Database upgraded successfully!"