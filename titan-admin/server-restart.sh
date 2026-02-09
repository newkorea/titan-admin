#!/bin/bash
set -e

# Remove stale sockets (both legacy and current path)
rm -f /tmp/titan-admin.sock || true
rm -f /home/newkorea/project/titan-admin/mako_modules/titan-admin.sock || true

# Launch using unified venv (.venv38) and project uwsgi.ini
/home/newkorea/project/titan-admin/.venv38/bin/uwsgi --ini /home/newkorea/project/titan-admin/uwsgi.ini
