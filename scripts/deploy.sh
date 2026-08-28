#!/usr/bin/env bash
# RecruitIQ droplet deploy (Phase 4). Run as root ON the droplet:
#
#   /opt/recruitiq/app/scripts/deploy.sh
#
# Idempotent: first run is the deployment, every later run is an update.
# The droplet is shared with a latency-sensitive trading system, so the two
# heavy steps are deliberately fenced: dependency installs run under `nice`,
# and `next build` runs in a systemd scope with its own MemoryMax so a build
# can only OOM itself, never push the neighbor into swap.
set -euo pipefail

APP=/opt/recruitiq/app
ENV_FILE=/etc/recruitiq/env

as_app() { sudo -u recruitiq bash -c "$*"; }

echo "==> git pull"
as_app "git -C $APP pull --ff-only"

echo "==> backend deps"
as_app "cd $APP && nice -n 15 poetry install --no-interaction --sync"

echo "==> web deps + build (memory-fenced)"
as_app "cd $APP/web && nice -n 15 npm ci --no-audit --no-fund"
systemd-run --wait --collect --quiet \
  --property=MemoryMax=1200M --property=CPUWeight=50 \
  --uid=recruitiq --gid=recruitiq \
  bash -c "cd $APP/web && NODE_OPTIONS=--max-old-space-size=1024 npx next build"

echo "==> migrations"
as_app "set -a; . $ENV_FILE; set +a; cd $APP/backend && $APP/.venv/bin/alembic upgrade head"

echo "==> install units + nginx config"
install -d -o recruitiq -g recruitiq /opt/recruitiq/logs
cp "$APP"/deploy/recruitiq-api.service "$APP"/deploy/recruitiq-web.service /etc/systemd/system/
systemctl daemon-reload
if [ ! -f /etc/nginx/sites-available/resumecupid.ai ]; then
    cp "$APP"/deploy/nginx-resumecupid.conf /etc/nginx/sites-available/resumecupid.ai
    ln -sf /etc/nginx/sites-available/resumecupid.ai /etc/nginx/sites-enabled/resumecupid.ai
else
    echo "    nginx site exists; not overwriting (certbot manages it). Diff:"
    diff /etc/nginx/sites-available/resumecupid.ai "$APP"/deploy/nginx-resumecupid.conf || true
fi
nginx -t
systemctl reload nginx

echo "==> restart services"
systemctl enable --now recruitiq-api recruitiq-web >/dev/null 2>&1 || true
systemctl restart recruitiq-api
systemctl restart recruitiq-web

echo "==> health checks"
for i in $(seq 1 30); do
    curl -fsS -o /dev/null http://127.0.0.1:8020/health && break
    sleep 2
    [ "$i" = 30 ] && { echo "API health check failed"; journalctl -u recruitiq-api -n 30 --no-pager; exit 1; }
done
echo "    api: ok"
for i in $(seq 1 15); do
    curl -fsS -o /dev/null http://127.0.0.1:3001/ && break
    sleep 2
    [ "$i" = 15 ] && { echo "web health check failed"; journalctl -u recruitiq-web -n 30 --no-pager; exit 1; }
done
echo "    web: ok"

echo "==> deployed $(as_app "git -C $APP rev-parse --short HEAD")"
