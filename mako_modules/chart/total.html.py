# -*- coding:utf-8 -*-
from mako import runtime, filters, cache
UNDEFINED = runtime.UNDEFINED
STOP_RENDERING = runtime.STOP_RENDERING
__M_dict_builtin = dict
__M_locals_builtin = locals
_magic_number = 10
_modified_time = 1762037812.615341
_enable_loop = True
_template_filename = '/home/ubuntu/project/titan-admin/backend/templates/chart/total.html'
_template_uri = 'chart/total.html'
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
        __M_writer = context.writer()
        __M_writer('\n  <div class="chart-box" id="chart_box">\n    <canvas id="userChart" height="450" width="1500"></canvas>\n  </div>\n')
        if type == 'rec':
            __M_writer('  <div class="chart-txt">\n      * 추천인 보유수 Top 20 을 차트로 표기하고있습니다<br>\n  </div>\n')
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
        __M_writer('\n<script src="/static/chart/js/total.js"></script>\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


"""
__M_BEGIN_METADATA
{"filename": "/home/ubuntu/project/titan-admin/backend/templates/chart/total.html", "uri": "chart/total.html", "source_encoding": "utf-8", "line_map": {"27": 0, "46": 1, "51": 4, "56": 6, "61": 7, "66": 19, "71": 23, "77": 3, "83": 3, "89": 6, "96": 6, "102": 7, "109": 7, "115": 9, "123": 9, "124": 13, "125": 14, "126": 18, "127": 18, "128": 18, "134": 21, "140": 21, "146": 140}}
__M_END_METADATA
"""
