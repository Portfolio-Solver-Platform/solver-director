#!/usr/bin/env bash
set -e


echo "Starting port-forward to postgres..."
kubectl port-forward -n psp svc/postgres-postgresql 5432:5432 &
PORT_FORWARD_PID=$!

# Wait for port-forward to be ready
sleep 3

echo "Generating migration: $1"
DATABASE_URL="postgresql://appuser:devpassword123@localhost:5432/appdb" \
    alembic revision --autogenerate -m "$1"

# Clean up
kill $PORT_FORWARD_PID
wait $PORT_FORWARD_PID 2>/dev/null || true

echo ""
echo "✓ Migration generated successfully!"
echo ""
echo "Next steps:"
echo "  1. Review the generated file in alembic/versions/"
echo "  2. Test: skaffold dev (migration will apply automatically)"
echo "  3. Make sure the alembic/versions is added in git"
