# -*- coding:utf-8 -*-
from mako import runtime, filters, cache
UNDEFINED = runtime.UNDEFINED
STOP_RENDERING = runtime.STOP_RENDERING
__M_dict_builtin = dict
__M_locals_builtin = locals
_magic_number = 10
_modified_time = 1762036418.342216
_enable_loop = True
_template_filename = '/home/ubuntu/project/titan-admin/backend/templates/chart/dd.html'
_template_uri = 'chart/dd.html'
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
        box_title = context.get('box_title', UNDEFINED)
        def subtitle():
            return render_subtitle(context._locals(__M_locals))
        def content():
            return render_content(context._locals(__M_locals))
        def css():
            return render_css(context._locals(__M_locals))
        year_list = context.get('year_list', UNDEFINED)
        def title():
            return render_title(context._locals(__M_locals))
        box_desc = context.get('box_desc', UNDEFINED)
        def js():
            return render_js(context._locals(__M_locals))
        endpoint = context.get('endpoint', UNDEFINED)
        type = context.get('type', UNDEFINED)
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
        box_title = context.get('box_title', UNDEFINED)
        def title():
            return render_title(context)
        __M_writer = context.writer()
        __M_writer(filters.decode.utf8(box_title))
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_subtitle(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def subtitle():
            return render_subtitle(context)
        box_desc = context.get('box_desc', UNDEFINED)
        __M_writer = context.writer()
        __M_writer(filters.decode.utf8(box_desc))
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_content(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        endpoint = context.get('endpoint', UNDEFINED)
        type = context.get('type', UNDEFINED)
        def content():
            return render_content(context)
        year_list = context.get('year_list', UNDEFINED)
        __M_writer = context.writer()
        __M_writer('\n  <!-- 검색필터 -->\n  <div class="row">\n    <div class="form-group col-sm-2">\n      <label>년도</label>\n      <select class="form-control" id="year_selectbox">\n')
        for year in year_list:
            __M_writer('          <option value="')
            __M_writer(filters.decode.utf8( year ))
            __M_writer('">')
            __M_writer(filters.decode.utf8( year ))
            __M_writer('</option>\n')
        __M_writer('      </select>\n    </div>\n    <div class="form-group col-sm-2">\n      <label>월</label>\n      <select class="form-control" id="month_selectbox">\n          <option value="1">1월</option>\n          <option value="2">2월</option>\n          <option value="3">3월</option>\n          <option value="4">4월</option>\n          <option value="5">5월</option>\n          <option value="6">6월</option>\n          <option value="7">7월</option>\n          <option value="8">8월</option>\n          <option value="9">9월</option>\n          <option value="10">10월</option>\n          <option value="11">11월</option>\n          <option value="12">12월</option>\n      </select>\n    </div>\n  </div>\n  <div class=\'btn-store\'>\n    <button class="btn btn-fw primary" onclick="click_search()">\n      <i class="fa fa-search mr5"></i>\n        검색하기\n    </button>\n  </div>\n  <div class="chart-box" id="chart_box">\n    <canvas id="userChart" height="450" width="1500"></canvas>\n  </div>\n')
        if type == 'user':
            __M_writer('  <div class="chart-txt">\n      * 활성화 수 기록은 2020년 03월 29일 이후로 적용되었습니다<br>\n      * 그 이전 활성화 수는 전부 0 으로 표기되오니 참고바랍니다\n  </div>\n')
        elif type == 'money':
            __M_writer('  <div class="chart-txt">\n      * 무통장은 "위쳇(수동)", "무통장"을 포함합니다<br>\n      * 결제모듈은 사용자가 결제모듈을 이용하여 결제된 데이터입니다<br>\n      * usd, cny는 단위가 작아 눈으로 확인하기 어려우므로 마우스를 차트위로 올려 확인바랍니다<br>\n  </div>\n')
        __M_writer('<input type="text" id="endpoint" value="')
        __M_writer(filters.decode.utf8(endpoint))
        __M_writer('" hidden>\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_js(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def js():
            return render_js(context)
        __M_writer = context.writer()
        __M_writer('\n<script src="/static/chart/js/dd.js"></script>\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


"""
__M_BEGIN_METADATA
{"filename": "/home/ubuntu/project/titan-admin/backend/templates/chart/dd.html", "uri": "chart/dd.html", "source_encoding": "utf-8", "line_map": {"27": 0, "47": 1, "52": 4, "57": 6, "62": 7, "67": 60, "72": 64, "78": 3, "84": 3, "90": 6, "97": 6, "103": 7, "110": 7, "116": 9, "125": 9, "126": 15, "127": 16, "128": 16, "129": 16, "130": 16, "131": 16, "132": 18, "133": 47, "134": 48, "135": 52, "136": 53, "137": 59, "138": 59, "139": 59, "145": 62, "151": 62, "157": 151}}
__M_END_METADATA
"""
