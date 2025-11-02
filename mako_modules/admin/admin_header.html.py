# -*- coding:utf-8 -*-
from mako import runtime, filters, cache
UNDEFINED = runtime.UNDEFINED
STOP_RENDERING = runtime.STOP_RENDERING
__M_dict_builtin = dict
__M_locals_builtin = locals
_magic_number = 10
_modified_time = 1762048999.796028
_enable_loop = True
_template_filename = '/home/ubuntu/project/titan-admin/backend/templates/admin/admin_header.html'
_template_uri = 'admin/admin_header.html'
_source_encoding = 'utf-8'
_exports = []


def render_body(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        __M_locals = __M_dict_builtin(pageargs=pageargs)
        request = context.get('request', UNDEFINED)
        __M_writer = context.writer()
        __M_writer('<header class="app-header theme">\r\n\t<div class="navbar navbar-expand-lg" style=\'background-color: #ab6cff;\'>\r\n        <a class="d-lg-none mx-2" data-toggle="modal" data-target="#aside">\r\n            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 512 512"><path d="M80 304h352v16H80zM80 248h352v16H80zM80 192h352v16H80z"/></svg>\r\n        </a>\r\n        <a class="navbar-brand" onclick="location.href=\'/dashboard\'">\r\n            <span class="hidden-folded d-inline logo-title">TITAN Admin</span>\r\n        </a>\r\n')
        if request.session['is_staff'] == 1:
            __M_writer('        <span class="hidden-folded d-inline logo-title">\r\n            현재 동시접속자 : <b id="use_count">0</b> 명\r\n        </span>\r\n')
        elif request.session['is_staff'] == 3:
            __M_writer('        <span class="hidden-folded d-inline logo-title">\r\n            추천코드 : <b>')
            __M_writer(filters.decode.utf8(request.session['rec']))
            __M_writer('</b>\r\n        </span>\r\n')
        __M_writer('        <ul class="nav flex-row order-lg-2">\r\n            <li class="dropdown d-flex align-items-center">\r\n                <span class="avatar w-32">\r\n                    <img src="/static/common/image/boy.png" alt="...">\r\n                </span>\r\n                <div class=\'info-box\'>\r\n                    <div class=\'info-box-top\'>\r\n                        ')
        __M_writer(filters.decode.utf8(request.session['username']))
        __M_writer('\r\n                    </div>\r\n')
        if request.session['is_staff'] == 1:
            __M_writer("                    <div class='info-box-bottom'>\r\n                        시스템 관리자\r\n                    </div>\r\n")
        elif request.session['is_staff'] == 2:
            __M_writer("                    <div class='info-box-bottom'>\r\n                        CS 관리자\r\n                    </div>\r\n")
        elif request.session['is_staff'] == 3:
            __M_writer("                    <div class='info-box-bottom'>\r\n                        총판 관리자\r\n                    </div>\r\n")
        __M_writer('                </div>\r\n                <div class=\'btn-logout\' onclick=\'callLogout()\'>\r\n                    로그아웃\r\n                </div>\r\n            </li>\r\n            <li class="d-lg-none d-flex align-items-center">\r\n                <a href="#" class="mx-2" data-toggle="collapse" data-target="#navbarToggler">\r\n                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 512 512"><path d="M64 144h384v32H64zM64 240h384v32H64zM64 336h384v32H64z"/></svg>\r\n                </a>\r\n            </li>\r\n        </ul>\r\n        <div class="collapse navbar-collapse  order-lg-1" id="navbarToggler">\r\n        </div>\r\n\t</div>\r\n</header>\r\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


"""
__M_BEGIN_METADATA
{"filename": "/home/ubuntu/project/titan-admin/backend/templates/admin/admin_header.html", "uri": "admin/admin_header.html", "source_encoding": "utf-8", "line_map": {"16": 0, "22": 1, "23": 9, "24": 10, "25": 13, "26": 14, "27": 15, "28": 15, "29": 18, "30": 25, "31": 25, "32": 27, "33": 28, "34": 31, "35": 32, "36": 35, "37": 36, "38": 40, "44": 38}}
__M_END_METADATA
"""
