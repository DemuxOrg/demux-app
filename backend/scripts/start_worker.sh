#!/bin/sh
# Production start command of the worker container (Scaleway Serverless Containers):
#   sh /app/scripts/start_worker.sh
#
# 1. Serves an empty directory on $PORT (8080 by default). The platform's health check
#    needs something listening; the worker itself has no HTTP server.
# 2. Applies the database migrations, retried for ~30 s: a new instance can fail to reach
#    the Private Network (the database) in its first seconds.
# 3. Replaces itself with the worker process, so it receives SIGTERM on redeploys.
#
# Kept in a file on purpose: an inline `sh -c '…'` command with quotes got mangled by
# Scaleway on every container update and ended in a shell syntax error.
set -eu

mkdir -p /tmp/health
python -m http.server "${PORT:-8080}" --directory /tmp/health >/dev/null 2>&1 &

attempt=1
until alembic upgrade head; do
    if [ "$attempt" -ge 6 ]; then
        echo "start_worker: migrations failed after $attempt attempts" >&2
        exit 1
    fi
    attempt=$((attempt + 1))
    sleep 5
done

exec python -m app.worker
