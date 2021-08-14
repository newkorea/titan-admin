#!/bin/bash

sudo rm -rf /tmp/titan-admin.sock
uwsgi --ini /home/ubuntu/project/titan-admin/titan-admin.ini