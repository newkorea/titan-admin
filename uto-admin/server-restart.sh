#!/bin/bash
set -e

# Remove stale socket
rm -f /tmp/uto-admin.sock || true

# Clean mako cache
rm -rf /home/newkorea/project/uto-admin/mako_modules/* || true

# Launch uWSGI
/home/newkorea/project/uto-admin/.venv38/bin/uwsgi --ini /home/newkorea/project/uto-admin/uwsgi.ini
