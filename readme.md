## titan & titan-admin
선행 설치
```
cmder
python3.6.8
```

개발환경 구축 - 사용자 (windows10 64bit)
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
vi venv\lib\site-packages\Crypto\Random\OSRNG\nt.py
import winrandom -> from . import winrandom
```

개발환경 구축 - 관리자 (windows10 64bit)
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
vi venv\lib\site-packages\Crypto\Random\OSRNG\nt.py
import winrandom -> from . import winrandom
```