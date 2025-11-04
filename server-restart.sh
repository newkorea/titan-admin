#!/bin/bash
set -e

# Remove stale sockets (both legacy and current path)
sudo rm -f /tmp/titan-admin.sock || true
sudo rm -f /home/ubuntu/project/titan-admin/mako_modules/titan-admin.sock || true

# Launch using unified venv (.venv38) and project uwsgi.ini
/home/ubuntu/project/titan-admin/.venv38/bin/uwsgi --ini /home/ubuntu/project/titan-admin/uwsgi.ini
