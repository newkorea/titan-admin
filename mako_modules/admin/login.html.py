# -*- coding:utf-8 -*-
from mako import runtime, filters, cache
UNDEFINED = runtime.UNDEFINED
STOP_RENDERING = runtime.STOP_RENDERING
__M_dict_builtin = dict
__M_locals_builtin = locals
_magic_number = 10
_modified_time = 1756526489.4249852
_enable_loop = True
_template_filename = '/home/ubuntu/project/titan-admin/backend/templates/admin/login.html'
_template_uri = 'admin/login.html'
_source_encoding = 'utf-8'
_exports = ['css', 'js']


def render_body(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        __M_locals = __M_dict_builtin(pageargs=pageargs)
        def css():
            return render_css(context._locals(__M_locals))
        def js():
            return render_js(context._locals(__M_locals))
        __M_writer = context.writer()
        runtime._include_file(context, 'admin_head.html', _template_uri)
        __M_writer('\r\n')
        runtime._include_file(context, 'admin_css.html', _template_uri)
        __M_writer('\r\n\r\n\r\n')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'css'):
            context['self'].css(**pageargs)
        

        __M_writer('\r\n\r\n\r\n<div class="login-container">\r\n  <div class="common-title">\r\n    <img class="common-logo" src=\'/static/admin/img/titan.png\'>\r\n    <div>TITAN Admin</div>\r\n  </div>\r\n  <div class="form-group">\r\n    <label for="login_id"></label>\r\n    <input type="text" class="form-control common-login-input" id="login_id" placeholder="아이디를 입력해주세요">\r\n  </div>\r\n\r\n  <div class="form-group">\r\n    <label for="login_pw"></label>\r\n    <input type="password" class="form-control common-login-input" id="login_pw" placeholder="비밀번호를 입력해주세요">\r\n  </div>\r\n\r\n  <div class="button">\r\n    <button id="btn-Yes" class="btn btn-lg btn-block btn-login" onclick=\'adminLogin()\'>로 그 인</button>\r\n  </div>\r\n</div>\r\n\r\n\r\n')
        runtime._include_file(context, 'admin_js.html', _template_uri)
        __M_writer('\r\n')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'js'):
            context['self'].js(**pageargs)
        

        __M_writer('\r\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_css(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def css():
            return render_css(context)
        __M_writer = context.writer()
        __M_writer('\r\n<link rel="stylesheet" href="/static/admin/css/login.css">\r\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_js(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def js():
            return render_js(context)
        __M_writer = context.writer()
        __M_writer('\r\n<script src="/static/admin/js/login.js"></script>\r\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


"""
__M_BEGIN_METADATA
{"filename": "/home/ubuntu/project/titan-admin/backend/templates/admin/login.html", "uri": "admin/login.html", "source_encoding": "utf-8", "line_map": {"16": 0, "25": 1, "26": 1, "27": 2, "28": 2, "33": 7, "34": 31, "35": 31, "40": 34, "46": 5, "52": 5, "58": 32, "64": 32, "70": 64}}
__M_END_METADATA
"""
