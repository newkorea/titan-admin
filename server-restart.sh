#!/bin/bash

sudo rm -rf /tmp/titan-admin.sock
. /www/wwwroot/tiadmintansk1.titanvpn.kr/venv/bin/activate
uwsgi --ini /www/wwwroot/tiadmintansk1.titanvpn.kr/titan-admin.ini
deactivate