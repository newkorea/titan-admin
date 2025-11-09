# titan & titan-admin

### 선행 설치
* cmder
https://cmder.net/
* python3.6.8
https://www.python.org/downloads/release/python-368/

### pip 업그레이드
```
python -m pip install --upgrade pip
```

### 개발환경 구축 - 사용자 (windows10 64bit)
```
cd ~
mkdir workspace
cd workspace
git clone https://github.com/h4ppyy/titan
cd titan
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
pip install pycrypto-2.6.1-cp36-cp36m-win_amd64.whl
```

```
vi venv\lib\site-packages\Crypto\Random\OSRNG\nt.py

# 아래의 소스 수정
import winrandom -> from . import winrandom
```

```
# 서버 실행
python manage.py runserver 0.0.0.0:8000

※settings.py DB 정보가 올바르지 않을 경우 서버기동 불가능
```

### 개발환경 구축 - 관리자 (windows10 64bit)
```
cd ~
mkdir workspace
cd workspace
git clone https://github.com/h4ppyy/titan-admin
cd titan-admin
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
pip install pycrypto-2.6.1-cp36-cp36m-win_amd64.whl
```

```
vi venv\lib\site-packages\Crypto\Random\OSRNG\nt.py

# 아래의 소스 수정
import winrandom -> from . import winrandom
```

```
# 서버 실행
python manage.py runserver 0.0.0.0:9000

※settings.py DB 정보가 올바르지 않을 경우 서버기동 불가능
```

### 스테이지&운영환경 구축 - 사용자 & 관리자

가상환경 구축을 제외한 과정은 운영환경 구축메뉴얼과 동일함

###### docker 컨테이너 구축 (only staging)
```
cd titan
docker pull toolsmiths/ubuntu16.04-test:gpdb5-v105
docker run -d -it --name titan-staging toolsmiths/ubuntu16.04-test:gpdb5-v105
docker exec -it titan-staging /bin/bash
winpty docker exec -it titan-staging bash
```

###### 사용자 추가 및 기본 유틸리티 설치

```
# 아래부터 docker 내부
adduser ubuntu

apt-get update

apt-get install sudo
apt-get install vi
apt-get install git
```

###### 사용자에 sudo권한 부여

```
sudo chmod 755 /etc/sudoers

sudo vi /etc/sudoers

# 아래의 권한 추가
ubuntu  ALL=(ALL:ALL) ALL

sudo chmod 440 /etc/sudoers
```

###### python3.6 설치 (Python 3.6.13, 2021.08.14 기준)

```
※개발 당시 version 3.6.8 이기 때문에 마이너 버전까지 맞추려면 아래의 절차(pyenv) 진행할 것

sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.6
```

###### python 심볼릭 링크 변경
```
sudo rm -rf /usr/bin/python
sudo ln -s /usr/bin/python3.6 /usr/bin/python
python -V
```

###### pyenv로 python3.6.8 설정
```
su - ubuntu
sudo git clone git://github.com/yyuu/pyenv.git ~/.pyenv

sudo apt-get install libssl-dev zlib1g-dev

sudo chown -R ubuntu.ubuntu .pyenv

export PYENV_ROOT=$HOME/.pyenv
export PATH=$PYENV_ROOT/bin:$PATH
eval "$(pyenv init --path)"

pyenv install 3.6.8
pyenv global 3.6.8

python -V
```

```
sudo vi ~/.bashrc

# 아래 내용 추가
export PYENV_ROOT=$HOME/.pyenv
export PATH=$PYENV_ROOT/bin:$PATH
eval "$(pyenv init --path)"
pyenv global 3.6.8
```

###### virtualenv 설치

```
sudo apt-get install virtualenv
```

###### 레포지토리 클론
```
cd ~
mkdir project
cd project

git clone https://github.com/return-shell/titan
git clone https://github.com/return-shell/titan-admin

sudo apt-get install python3.6-dev libmysqlclient-dev
```

```
sudo apt-get install build-essential autoconf libtool pkg-config python-opengl python-pil python-pyrex python-pyside.qtopengl idle-python2.7 qt4-dev-tools qt4-designer libqtgui4 libqtcore4 libqt4-xml libqt4-test libqt4-script libqt4-network libqt4-dbus python-qt4 python-qt4-gl libgle3 python-dev libssl-dev
```

###### 사용자 구축
```
cd ~/project/titan
virtualenv -p python3.6 venv
. venv/bin/activate
```

```
vi requirements.txt

# 아래 모듈 주석 해제
pycrypto==2.6.1
```

```
vi main/settings.py

# 아래 DB정보 수정
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'titan',
        'USER': 'titan',
        'PASSWORD': 'xkdlxks12!@',
        'HOST': '15.165.156.213',
        'PORT': '3306',
    },
    'radius': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'radius',
        'USER': 'titan',
        'PASSWORD': 'xkdlxks12!@',
        'HOST': '15.165.156.213',
        'PORT': '3306',
    }
}
```

```
pip install -r requirements.txt

# 서버 기동테스트
python manage.py runserver 0.0.0.0:8000
```

###### 관리자 구축
```
deactivate

cd ~/project/titan-admin
virtualenv -p python3.6 venv
. venv/bin/activate
```

```
vi requirements.txt

# 아래 모듈 주석 해제
pycrypto==2.6.1
```

```
vi main/settings.py

# 아래 DB정보 수정
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'titan',
        'USER': 'titan',
        'PASSWORD': 'xkdlxks12!@',
        'HOST': '15.165.156.213',
        'PORT': '3306',
    },
    'radius': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'radius',
        'USER': 'titan',
        'PASSWORD': 'xkdlxks12!@',
        'HOST': '15.165.156.213',
        'PORT': '3306',
    }
}
```

```
pip install -r requirements.txt

# 서버 기동테스트
python manage.py runserver 0.0.0.0:9000
```

###### nginx 설치
```
export PATH=/usr/sbin/:$PATH

cd /tmp
curl -O http://nginx.org/keys/nginx_signing.key
sudo apt-key add nginx_signing.key
sudo sh -c "echo deb http://nginx.org/packages/ubuntu/ xenial nginx >> /etc/apt/sources.list"
sudo sh -c "echo deb-src http://nginx.org/packages/ubuntu/ xenial nginx >> /etc/apt/sources.list"
sudo apt-get update
sudo apt-get install nginx

nginx -v

sudo systemctl enable nginx
sudo service nginx restart
sudo service nginx status
```

```
sudo vi /etc/nginx/nginx.conf

# 아래 추가
include /etc/nginx/sites-enabled/*;
```

```
sudo mkdir /etc/nginx/sites-enabled
sudo mkdir /etc/nginx/sites-available

sudo mv /etc/nginx/conf.d/default.conf /etc/nginx/sites-enabled/

sudo service nginx restart

# nginx 접속 테스트
curl -XGET localhost
```

###### pip 설치
```
sudo apt-get install python3-pip
sudo ln -s /usr/bin/pip3 /usr/bin/pip
```

###### uwsgi 설치
```
deactivate
pip install uwsgi
```

###### nginx 서비스 구성

```
sudo vi /etc/nginx/sites-available/titan
```
```
server {

    listen 80 default;
    server_name aws1.titanvpn.io;

    access_log /var/log/nginx/titan_access.log;
    error_log /var/log/nginx/titan_error.log;

    if ($http_x_forwarded_proto = 'http'){
        return 301 https://$host$request_uri;
    }

    location / {
        uwsgi_pass unix:///tmp/titan.sock;
        include uwsgi_params;
    }

    location /static/ {
        alias /home/ubuntu/project/titan/backend/static/;
        expires -1;
    }

    location /upload/download/ {
        alias /home/ubuntu/project/titan-admin/upload/download/;
        expires -1;
    }

    # error_page  403 404 405 406 411 497 500 501 502 503 504 505 /error.html;
    # location = /error.html {
    #     root /usr/share/nginx/html;
    # }
}
```

```
sudo vi /etc/nginx/sites-available/titan-admin
```
```
server {
    listen 80;

    server_name chmaster.titanvpn.io tiadmintan1.titanvpn.io;
    client_max_body_size 100M;

    access_log /var/log/nginx/titan-admin_access.log;
    error_log /var/log/nginx/titan-admin_error.log;

    location / {
        uwsgi_pass unix:///tmp/titan-admin.sock;
        include uwsgi_params;
    }

    location /static/ {
        alias /home/ubuntu/project/titan-admin/backend/static/;
        expires -1;
    }

    location /upload/ {
        alias /home/ubuntu/project/titan/upload/;
        expires -1;
    }

    #listen 443 ssl; # managed by Certbot
    #ssl_certificate /etc/letsencrypt/live/admin.titanvpn.io/fullchain.pem; # managed by Certbot
    #ssl_certificate_key /etc/letsencrypt/live/admin.titanvpn.io/privkey.pem; # managed by Certbot
    #include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
    #ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot
}
```

```
sudo ln -s /etc/nginx/sites-available/titan /etc/nginx/sites-enabled/titan
sudo ln -s /etc/nginx/sites-available/titan-admin /etc/nginx/sites-enabled/titan-admin

ls -al /etc/nginx/sites-enabled/

sudo service nginx restart
```

###### uwsgi 서비스 구성
```
# 아래 디렉토리에 로그가 저장됨
cd /home/ubuntu
mkdir uwsgi

cd ~/project/titan
bash server-restart.sh

cd ~/project/titan-admin
bash server-restart.sh

# sock 생성 확인
ls -al /tmp/titan*
```

###### nginx 재기동
```
※ sock 파일을 읽기 위한 재기동

sudo service nginx restart
```