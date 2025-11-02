# -*- coding:utf-8 -*-
from mako import runtime, filters, cache
UNDEFINED = runtime.UNDEFINED
STOP_RENDERING = runtime.STOP_RENDERING
__M_dict_builtin = dict
__M_locals_builtin = locals
_magic_number = 10
_modified_time = 1762037809.2747362
_enable_loop = True
_template_filename = '/home/ubuntu/project/titan-admin/backend/templates/chart/connection_info.html'
_template_uri = 'chart/connection_info.html'
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
    return runtime._inherit_from(context, '../admin/admin_frame.html', _template_uri)
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
        __M_writer('\r\n\r\n')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'css'):
            context['self'].css(**pageargs)
        

        __M_writer('\r\n\r\n')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'title'):
            context['self'].title(**pageargs)
        

        __M_writer('\r\n')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'subtitle'):
            context['self'].subtitle(**pageargs)
        

        __M_writer('\r\n\r\n')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'content'):
            context['self'].content(**pageargs)
        

        __M_writer('\r\n\r\n')
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
        __M_writer('\r\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_title(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def title():
            return render_title(context)
        __M_writer = context.writer()
        __M_writer('서버접속로그')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_subtitle(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def subtitle():
            return render_subtitle(context)
        __M_writer = context.writer()
        __M_writer('You can see user server connection logs')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_content(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def content():
            return render_content(context)
        __M_writer = context.writer()
        __M_writer('\r\n<div>\r\n  <!-- 검색필터 -->\r\n  <div class="row">\r\n    <div class="form-group col-sm-2">\r\n      <label>번호[=]</label>\r\n      <input class="form-control" id="filter_number">\r\n    </div>\r\n    <div class="form-group col-sm-2">\r\n      <label>이메일[like]</label>\r\n      <input class="form-control" id="filter_username">\r\n    </div>\r\n    <div class="form-group col-sm-2">\r\n      <label>Nasipaddress</label>\r\n      <input class="form-control" id="filter_nasipaddress">\r\n    </div>\r\n    <div class="form-group col-sm-2">\r\n      <label>Nastype[=]</label>\r\n      <input class="form-control" id="filter_nasporttype">\r\n    </div>\r\n    <div class="form-group col-sm-2">\r\n      <label>calledstationid[Like]</label>\r\n      <input class="form-control" id="filter_calledstationid">\r\n    </div>\r\n    <div class="form-group col-sm-2">\r\n      <label>callingstationid[Like]</label>\r\n      <input class="form-control" id="filter_callingstationid">\r\n    </div>\r\n    <div class="form-group col-sm-2">\r\n      <label>framedipaddress[Like]</label>\r\n      <input class="form-control" id="filter_framedipaddress">\r\n    </div>\r\n    <div class="form-group col-sm-2">\r\n      <label>접속 시간[From]</label>\r\n      <input id="filter_acctstarttime_start" type="text" class="form-control datepicker dp-re" data-plugin="datepicker" placeholder="yyyy-mm-dd">\r\n    </div>\r\n    <div class="form-group col-sm-2">\r\n      <label>접속 시간[To]</label>\r\n      <input id="filter_acctstarttime_end" type="text" class="form-control datepicker dp-re" data-plugin="datepicker" placeholder="yyyy-mm-dd">\r\n    </div>\r\n  </div>\r\n<div class=\'btn-store\'>\r\n<button class="btn btn-fw primary" onclick="reload_data()">\r\n      <i class="fa fa-search mr5"></i>\r\n      검색하기\r\n    </button>\r\n  </div>\r\n\r\n\r\n  <!-- 데이터테이블즈 -->\r\n  <div class="user-table">\r\n    <table id="connection-inform" class="display table">\r\n      <thead>\r\n        <tr>\r\n          <th>번호</th>\r\n          <th>이메일</th>\r\n          <th>Nasipaddress</th>\r\n          <th>Nasporttype</th>\r\n          <th>Acctstarttime</th>\r\n          <th>Acctstoptime</th>\r\n          <th>Acctinputoctets</th>\r\n          <th>Acctoutputoctets</th>\r\n          <th>Calledstationid</th>\r\n          <th>Callingstationid</th>\r\n          <th>Framedipaddress</th>\r\n        </tr>\r\n      </thead>\r\n      <tbody>\r\n      </tbody>\r\n    </table>\r\n  </div>\r\n</div>\r\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_js(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def js():
            return render_js(context)
        __M_writer = context.writer()
        __M_writer('\r\n<script src="/static/chart/js/connection_info.js"></script>\r\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


"""
__M_BEGIN_METADATA
{"filename": "/home/ubuntu/project/titan-admin/backend/templates/chart/connection_info.html", "uri": "chart/connection_info.html", "source_encoding": "utf-8", "line_map": {"27": 0, "42": 1, "47": 4, "52": 6, "57": 7, "62": 81, "67": 85, "73": 3, "79": 3, "85": 6, "91": 6, "97": 7, "103": 7, "109": 9, "115": 9, "121": 83, "127": 83, "133": 127}}
__M_END_METADATA
"""
