import os
import json
import uuid
import hashlib
from datetime import datetime, timedelta
import base64
import re
try:
    from html.parser import HTMLParser
except:
    from HTMLParser import HTMLParser
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db import connections
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from Crypto import Random
from Crypto.Cipher import AES

from backend.models import *


def common_sample():
    print("hello world")


def xssProtect(text):
    if '<'  in text:
        text = text.replace('<', '&lt')
    if '>' in text:
        text = text.replace('>', '&gt')
    if '&ltbr&gt' in text:
        text = text.replace('&ltbr&gt', '<br>')
    return text


class XssHtml(HTMLParser):
    """
    allow_tags = ['a', 'img', 'br', 'strong', 'b', 'code', 'pre',
                  'p', 'div', 'em', 'span', 'h1', 'h2', 'h3', 'h4',
                  'h5', 'h6', 'blockquote', 'ul', 'ol', 'tr', 'th', 'td',
                  'hr', 'li', 'u', 'embed', 's', 'table', 'thead', 'tbody',
                  'caption', 'small', 'q', 'sup', 'sub']
    """
    allow_tags = ['br']
    common_attrs = ["style", "class", "name"]
    nonend_tags = ["img", "hr", "br", "embed"]
    tags_own_attrs = {
        "img": ["src", "width", "height", "alt", "align"], 
        "a": ["href", "target", "rel", "title"],
        "embed": ["src", "width", "height", "type", "allowfullscreen", "loop", "play", "wmode", "menu"],
        "table": ["border", "cellpadding", "cellspacing"],
    }

    _regex_url = re.compile(r'^(http|https|ftp)://.*', re.I | re.S)
    _regex_style_1 = re.compile(r'(\\|&#|/\*|\*/)', re.I)
    _regex_style_2 = re.compile(r'e.*x.*p.*r.*e.*s.*s.*i.*o.*n', re.I | re.S)


    def __init__(self, allows=[]):
        HTMLParser.__init__(self)
        self.allow_tags = allows if allows else self.allow_tags
        self.result = []
        self.start = []
        self.data = []

    def getHtml(self):
        """
        Get the safe html code
        """
        for i in range(0, len(self.result)):
            self.data.append(self.result[i])
        return ''.join(self.data)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_starttag(self, tag, attrs):
        if tag not in self.allow_tags:
            return
        end_diagonal = ' /' if tag in self.nonend_tags else ''
        if not end_diagonal:
            self.start.append(tag)
        attdict = {}
        for attr in attrs:
            attdict[attr[0]] = attr[1]

        attdict = self._wash_attr(attdict, tag)
        if hasattr(self, "node_%s" % tag):
            attdict = getattr(self, "node_%s" % tag)(attdict)
        else:
            attdict = self.node_default(attdict)

        attrs = []
        for (key, value) in attdict.items():
            attrs.append('%s="%s"' % (key, self._htmlspecialchars(value)))
        attrs = (' ' + ' '.join(attrs)) if attrs else ''
        self.result.append('<' + tag + attrs + end_diagonal + '>')

    def handle_endtag(self, tag):
        if self.start and tag == self.start[len(self.start) - 1]:
            self.result.append('</' + tag + '>')
            self.start.pop()

    def handle_data(self, data):
        self.result.append(self._htmlspecialchars(data))

    def handle_entityref(self, name):
        if name.isalpha():
            self.result.append("&%s;" % name)

    def handle_charref(self, name):
        if name.isdigit():
            self.result.append("&#%s;" % name)

    def node_default(self, attrs):
        attrs = self._common_attr(attrs)
        return attrs

    def node_a(self, attrs):
        attrs = self._common_attr(attrs)
        attrs = self._get_link(attrs, "href")
        attrs = self._set_attr_default(attrs, "target", "_blank")
        attrs = self._limit_attr(attrs, {
            "target": ["_blank", "_self"]
        })
        return attrs

    def node_embed(self, attrs):
        attrs = self._common_attr(attrs)
        attrs = self._get_link(attrs, "src")
        attrs = self._limit_attr(attrs, {
            "type": ["application/x-shockwave-flash"],
            "wmode": ["transparent", "window", "opaque"],
            "play": ["true", "false"],
            "loop": ["true", "false"],
            "menu": ["true", "false"],
            "allowfullscreen": ["true", "false"]
        })
        attrs["allowscriptaccess"] = "never"
        attrs["allownetworking"] = "none"
        return attrs

    def _true_url(self, url):
        if self._regex_url.match(url):
            return url
        else:
            return "http://%s" % url

    def _true_style(self, style):
        if style:
            style = self._regex_style_1.sub('_', style)
            style = self._regex_style_2.sub('_', style)
        return style

    def _get_style(self, attrs):
        if "style" in attrs:
            attrs["style"] = self._true_style(attrs.get("style"))
        return attrs

    def _get_link(self, attrs, name):
        if name in attrs:
            attrs[name] = self._true_url(attrs[name])
        return attrs

    def _wash_attr(self, attrs, tag):
        if tag in self.tags_own_attrs:
            other = self.tags_own_attrs.get(tag)
        else:
            other = []

        _attrs = {}
        if attrs:
            for (key, value) in attrs.items():
                if key in self.common_attrs + other:
                    _attrs[key] = value
        return _attrs

    def _common_attr(self, attrs):
        attrs = self._get_style(attrs)
        return attrs

    def _set_attr_default(self, attrs, name, default=''):
        if name not in attrs:
            attrs[name] = default
        return attrs

    def _limit_attr(self, attrs, limit={}):
        for (key, value) in limit.items():
            if key in attrs and attrs[key] not in value:
                del attrs[key]
        return attrs

    def _htmlspecialchars(self, html):
        return html.replace("<", "&lt;")\
            .replace(">", "&gt;")\
            .replace('"', "&quot;")\
            .replace("'", "&#039;")


class AESCipher(object):

    def __init__(self):
        key = settings.ACTIVE_AES_KEY
        self.bs = 32
        self.key = hashlib.sha256(key.encode()).digest()

    def encrypt(self, raw):
        raw = self._pad(raw)
        iv = Random.new().read(AES.block_size)
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return base64.b64encode(iv + cipher.encrypt(raw))

    def decrypt(self, enc):
        enc = base64.b64decode(enc)
        iv = enc[:AES.block_size]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return self._unpad(cipher.decrypt(enc[AES.block_size:])).decode('utf-8')

    def _pad(self, s):
        return s + (self.bs - len(s) % self.bs) * chr(self.bs - len(s) % self.bs)

    @staticmethod
    def _unpad(s):
        return s[:-ord(s[len(s)-1:])]


def dictfetchall(cursor):
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()
    ]


def login_check(func):
    def wrapper(request, *args, **kwargs):

        if 'id' in request.session:
            pass
        else:
            return redirect('/login')

        result = func(request, *args, **kwargs)
        return result

    return wrapper


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def hashText(text):
    salt = uuid.uuid4().hex
    return hashlib.sha256(salt.encode() + text.encode()).hexdigest() + ':' + salt


def matchHashedText(hashedText, providedText):
    _hashedText, salt = hashedText.split(':')
    return _hashedText == hashlib.sha256(salt.encode() + providedText.encode()).hexdigest()


def sizeof_fmt(num, suffix='b'):
    for unit in ['', 'k', 'm', 'g', 't', 'p', 'e', 'z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def file_upload(file, gname, gid):

    upload_root = settings.UPLOAD_ROOT
    real_name = file.name
    save_name = str(uuid.uuid4()).replace('-', '')
    ext = file.name.split('.')[-1]
    real_size = file.size
    save_size = sizeof_fmt(file.size)
    save_path = upload_root + save_name

    print('upload_root -> ', upload_root)
    print('save_name -> ', save_name)
    print('ext -> ', ext)
    print('real_size -> ', real_size)
    print('save_size -> ', save_size)

    if not os.path.exists(upload_root):
        os.makedirs(upload_root)

    fs = FileSystemStorage()
    filename = fs.save(save_path, file)

    file = TblFile(
        gname       = gname,
        gid         = gid,
        real_name   = real_name,
        save_name   = save_name,
        ext         = ext,
        real_size   = real_size,
        save_size   = save_size,
        save_path   = save_path,
        regist_id   = None,
        regist_date = datetime.datetime.now(),
        delete_yn   = 'N',
        delete_date = None
    )
    file.save()


def download_upload(file, flag):

    if flag.find('link') != -1:
        real_name = file
        real_size = 0
        save_size = ''
        save_path = ''

        print('real_name -> ', real_name)
        print('real_size -> ', real_size)
        print('save_size -> ', save_size)
        print('save_path -> ', save_path)
    else:
        upload_root = settings.UPLOAD_ROOT + 'download/'
        real_name = file.name
        real_size = file.size
        save_size = sizeof_fmt(file.size)
        save_path = upload_root + real_name

        print('upload_root -> ', upload_root)
        print('real_name -> ', real_name)
        print('real_size -> ', real_size)
        print('save_size -> ', save_size)
        print('save_path -> ', save_path)

        if not os.path.exists(upload_root):
            os.makedirs(upload_root)

        fs = FileSystemStorage()
        filename = fs.save(save_path, file)

    if flag == 'ko_win_clt' or flag == 'ko_win_img':
        tdm = TblDownloadManage.objects.get(type='windows', language='ko')
    if flag == 'en_win_clt' or flag == 'en_win_img':
        tdm = TblDownloadManage.objects.get(type='windows', language='en')
    if flag == 'zh_win_clt' or flag == 'zh_win_img':
        tdm = TblDownloadManage.objects.get(type='windows', language='zh')
    if flag == 'ja_win_clt' or flag == 'ja_win_img':
        tdm = TblDownloadManage.objects.get(type='windows', language='ja')

    if flag == 'ko_mac_clt' or flag == 'ko_mac_img':
        tdm = TblDownloadManage.objects.get(type='mac', language='ko')
    if flag == 'en_mac_clt' or flag == 'en_mac_img':
        tdm = TblDownloadManage.objects.get(type='mac', language='en')
    if flag == 'zh_mac_clt' or flag == 'zh_mac_img':
        tdm = TblDownloadManage.objects.get(type='mac', language='zh')
    if flag == 'ja_mac_clt' or flag == 'ja_mac_img':
        tdm = TblDownloadManage.objects.get(type='mac', language='ja')

    if flag == 'ko_and_link' or flag == 'ko_and_img':
        tdm = TblDownloadManage.objects.get(type='android', language='ko')
    if flag == 'en_and_link' or flag == 'en_and_img':
        tdm = TblDownloadManage.objects.get(type='android', language='en')
    if flag == 'zh_and_link' or flag == 'zh_and_img':
        tdm = TblDownloadManage.objects.get(type='android', language='zh')
    if flag == 'ja_and_link' or flag == 'ja_and_img':
        tdm = TblDownloadManage.objects.get(type='android', language='ja')

    if flag == 'ko_ios_link' or flag == 'ko_ios_img':
        tdm = TblDownloadManage.objects.get(type='ios', language='ko')
    if flag == 'en_ios_link' or flag == 'en_ios_img':
        tdm = TblDownloadManage.objects.get(type='ios', language='en')
    if flag == 'zh_ios_link' or flag == 'zh_ios_img':
        tdm = TblDownloadManage.objects.get(type='ios', language='zh')
    if flag == 'ja_ios_link' or flag == 'ja_ios_img':
        tdm = TblDownloadManage.objects.get(type='ios', language='ja')

    if flag.find('clt') != -1 or flag.find('link') != -1:
        tdm.client_name = real_name
        tdm.client_real_size = real_size
        tdm.client_save_size = save_size
        tdm.client_save_path = save_path
        tdm.client_modify_date = datetime.datetime.now()
        tdm.save()

    if flag.find('img') != -1:
        tdm.image_name = real_name
        tdm.image_real_size = real_size
        tdm.image_save_size = save_size
        tdm.image_save_path = save_path
        tdm.image_modify_date = datetime.datetime.now()
        tdm.save()
