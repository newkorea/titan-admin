#!/bin/bash

sudo rm -rf /tmp/titan-admin.sock
. /home/ubuntu/project/titan-admin/.venv38/bin/activate
uwsgi --ini /home/ubuntu/project/titan-admin/titan-admin.ini
deactivate
