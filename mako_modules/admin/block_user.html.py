# -*- coding:utf-8 -*-
from mako import runtime, filters, cache
UNDEFINED = runtime.UNDEFINED
STOP_RENDERING = runtime.STOP_RENDERING
__M_dict_builtin = dict
__M_locals_builtin = locals
_magic_number = 10
_modified_time = 1762036405.4659655
_enable_loop = True
_template_filename = '/home/ubuntu/project/titan-admin/backend/templates/admin/block_user.html'
_template_uri = 'admin/block_user.html'
_source_encoding = 'utf-8'
_exports = ['css', 'title', 'subtitle', 'content', 'js']


def _mako_get_namespace(context, name):
    try:
        return context.namespaces[(__name__, name)]
    except KeyError:
        _mako_generate_namespaces(context)
        return context.namespaces[(__name__, name)]
def _mako_generate_namespaces(context):
    pass
def _mako_inherit(template, context):
    _mako_generate_namespaces(context)
    return runtime._inherit_from(context, 'admin_frame.html', _template_uri)
def render_body(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        __M_locals = __M_dict_builtin(pageargs=pageargs)
        def subtitle():
            return render_subtitle(context._locals(__M_locals))
        def content():
            return render_content(context._locals(__M_locals))
        def css():
            return render_css(context._locals(__M_locals))
        def title():
            return render_title(context._locals(__M_locals))
        def js():
            return render_js(context._locals(__M_locals))
        __M_writer = context.writer()
        __M_writer('\n\n')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'css'):
            context['self'].css(**pageargs)
        

        __M_writer('\n\n')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'title'):
            context['self'].title(**pageargs)
        

        __M_writer('\n')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'subtitle'):
            context['self'].subtitle(**pageargs)
        

        __M_writer('\n\n')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'content'):
            context['self'].content(**pageargs)
        

        __M_writer('\n\n')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'js'):
            context['self'].js(**pageargs)
        

        __M_writer('\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_css(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def css():
            return render_css(context)
        __M_writer = context.writer()
        __M_writer('\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_title(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def title():
            return render_title(context)
        __M_writer = context.writer()
        __M_writer('사용자 차단')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_subtitle(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def subtitle():
            return render_subtitle(context)
        __M_writer = context.writer()
        __M_writer('TITAN VPN을 악의적으로 사용하는 사용자를 차단할 수 있습니다')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_content(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def content():
            return render_content(context)
        __M_writer = context.writer()
        __M_writer('\n\n<div class="real_step">\n    <span class="badge badge-pill warn">Step1</span> 차단할 사용자를 입력해주십시오\n</div>\n<div class="form-group">\n    <label for="exampleInputEmail1">차단할 사용자</label>\n    <textarea id="user_list" class="form-control" rows="5" placeholder="hackx@naver.com, 93immm@naver.com, 13, 17"></textarea>\n    <div style="margin-top: 10px;">\n        * 차단할 사용자를 쉼표(,) 구분으로 입력해주십시오<br>\n        * 이메일 또는 회원번호를 입력하십시오<br>\n        * 이메일과 회원번호를 섞어서 사용할 수 있습니다<br>\n        * 전부 입력하신 후에 "검증" 버튼을 클릭하여 차단할 수 있는지 확인하십시오\n    </div>\n</div>\n<div class="text-right">\n    <button class="btn btn-fw warn" onclick="click_validate()">검증</button>\n</div>\n<div class="real_step">\n    <span class="badge badge-pill warn">Step2</span> 차단 될 사용자를 검토 후에 차단처리하십시오\n</div>\n<div style="margin-top: 20px;">\n    <table class="table">\n        <thead class="thead-light">\n            <tr>\n            <th>회원번호</th>\n            <th>이메일</th>\n            <th>가입일자</th>\n            <th>만료날짜</th>\n            <th>가입아이피</th>\n            <th>활성화여부</th>\n            </tr>\n        </thead>\n        <tbody id="add_point">\n        </tbody>\n    </table>\n    <div class="null-txt" id="null_txt" style="display: block">\n        조건에 해당하는 데이터가 존재하지 않습니다\n    </div>\n    <div style="margin-top: 10px;">\n        * 이메일 또는 회원번호가 없는 경우나 오류인 경우는 테이블 내에 포함되지 않습니다<br>\n        * 테이블 내에 표기된 데이터가 실질적으로 차단 처리되는 데이터입니다<br>\n        * 차단은 사용시간이 2010-01-01 로 변경되면서 이용할 수 없도록 만드는 프로세스입니다<br>\n    </div>\n</div>\n<div class="text-right">\n    <button class="btn btn-fw danger" onclick="click_block()">차단</button>\n</div>\n\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_js(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def js():
            return render_js(context)
        __M_writer = context.writer()
        __M_writer('\n<script src="/static/chart/js/block_user.js"></script>\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


"""
__M_BEGIN_METADATA
{"filename": "/home/ubuntu/project/titan-admin/backend/templates/admin/block_user.html", "uri": "admin/block_user.html", "source_encoding": "utf-8", "line_map": {"27": 0, "42": 1, "47": 4, "52": 6, "57": 7, "62": 58, "67": 62, "73": 3, "79": 3, "85": 6, "91": 6, "97": 7, "103": 7, "109": 9, "115": 9, "121": 60, "127": 60, "133": 127}}
__M_END_METADATA
"""
