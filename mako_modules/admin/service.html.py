# -*- coding:utf-8 -*-
from mako import runtime, filters, cache
UNDEFINED = runtime.UNDEFINED
STOP_RENDERING = runtime.STOP_RENDERING
__M_dict_builtin = dict
__M_locals_builtin = locals
_magic_number = 10
_modified_time = 1762035902.0553722
_enable_loop = True
_template_filename = '/home/ubuntu/project/titan-admin/backend/templates/admin/service.html'
_template_uri = 'admin/service.html'
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
        __M_writer('\n\n\n')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'css'):
            context['self'].css(**pageargs)
        

        __M_writer('\n\n\n')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'title'):
            context['self'].title(**pageargs)
        

        __M_writer('\n')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'subtitle'):
            context['self'].subtitle(**pageargs)
        

        __M_writer('\n\n\n')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'content'):
            context['self'].content(**pageargs)
        

        __M_writer('\n\n\n')
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
        __M_writer('변경 내역')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_subtitle(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def subtitle():
            return render_subtitle(context)
        __M_writer = context.writer()
        __M_writer('TITAN VPN 회원 관리에서 변경한 내역들을 볼 수 있습니다')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_content(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def content():
            return render_content(context)
        __M_writer = context.writer()
        __M_writer('\n<div>\n  <!-- 검색필터 -->\n  <div class="row">\n    <div class="form-group col-sm-2">\n      <label>이메일[like]</label>\n      <input class="form-control" id="filter_id">\n    </div>\n    <div class="form-group col-sm-2">\n      <label>등록일[>=]</label>\n      <input id="filter_regist_start" type="text" class="form-control datepicker dp-re" data-plugin="datepicker" placeholder="yyyy-mm-dd">\n    </div>\n    <div class="form-group col-sm-2">\n      <label>등록일[<]</label>\n      <input id="filter_regist_end" type="text" class="form-control datepicker dp-re" data-plugin="datepicker" placeholder="yyyy-mm-dd">\n    </div>\n    <div class="form-group col-sm-2">\n      <label>내역</label>\n      <select class="form-control" id="filter_type" name="filter_delete">\n        <option value="">선택하세요</option>\n        <option value="service">서비스시간 변경</option>\n        <option value="session">세션 변경</option>\n        <option value="refund">환불</option>\n        <option value="password">비밀번호 변경</option>\n        <option value="active">활성화 변경</option>\n        <option value="delete">회원탈퇴</option>\n      </select>\n    </div>\n  </div>\n  <!-- 버튼 -->\n  <div class=\'btn-store\'>\n    <button class="btn btn-fw primary" onclick="reload_data()">\n      <i class="fa fa-search mr5"></i>\n      검색하기\n    </button>\n  </div>\n  <!-- 데이터테이블즈 -->\n  <div class="user-table">\n    <table id="user-inform" class="display table">\n      <thead>\n        <tr>\n          <th>아이디</th>\n          <th>이메일</th>\n          <th>변경 전 내역</th>\n          <th>변경 전 시간(rad)</th>\n          <th>변경 후 내역</th>\n          <th>변경 후 시간(rad)</th>\n          <th>내역</th>\n          <th>등록일</th>\n          <th>변경 사유</th>\n        </tr>\n      </thead>\n      <tbody>\n      </tbody>\n    </table>\n  </div>\n</div>\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_js(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def js():
            return render_js(context)
        __M_writer = context.writer()
        __M_writer('\n<script src="/static/admin/js/service.js"></script>\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


"""
__M_BEGIN_METADATA
{"filename": "/home/ubuntu/project/titan-admin/backend/templates/admin/service.html", "uri": "admin/service.html", "source_encoding": "utf-8", "line_map": {"27": 0, "42": 1, "47": 5, "52": 8, "57": 9, "62": 69, "67": 74, "73": 4, "79": 4, "85": 8, "91": 8, "97": 9, "103": 9, "109": 12, "115": 12, "121": 72, "127": 72, "133": 127}}
__M_END_METADATA
"""
