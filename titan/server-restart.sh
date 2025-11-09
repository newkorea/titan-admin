#!/bin/bash
set -e

# remove old socket (ignore errors)
rm -f /tmp/titan.sock || true

# ensure logs dir exists
mkdir -p /home/newkorea/project/titan/logs

# activate new python 3.10 env
source /home/newkorea/project/titan/.venv310/bin/activate

uwsgi --ini /home/newkorea/project/titan/titan.new.ini

deactivate
