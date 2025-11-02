# -*- coding:utf-8 -*-
from mako import runtime, filters, cache
UNDEFINED = runtime.UNDEFINED
STOP_RENDERING = runtime.STOP_RENDERING
__M_dict_builtin = dict
__M_locals_builtin = locals
_magic_number = 10
_modified_time = 1762049008.077954
_enable_loop = True
_template_filename = '/home/ubuntu/project/titan-admin/backend/templates/admin/dashboard.html'
_template_uri = 'admin/dashboard.html'
_source_encoding = 'utf-8'
_exports = ['title', 'subtitle', 'css', 'content', 'js']


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
        def title():
            return render_title(context._locals(__M_locals))
        def css():
            return render_css(context._locals(__M_locals))
        def js():
            return render_js(context._locals(__M_locals))
        request = context.get('request', UNDEFINED)
        def subtitle():
            return render_subtitle(context._locals(__M_locals))
        def content():
            return render_content(context._locals(__M_locals))
        __M_writer = context.writer()
        __M_writer('\n\n')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'title'):
            context['self'].title(**pageargs)
        

        __M_writer('\n')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'subtitle'):
            context['self'].subtitle(**pageargs)
        

        __M_writer('\n\n')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'css'):
            context['self'].css(**pageargs)
        

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


def render_title(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def title():
            return render_title(context)
        __M_writer = context.writer()
        __M_writer('시작하기')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_subtitle(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def subtitle():
            return render_subtitle(context)
        __M_writer = context.writer()
        __M_writer('타이탄 관리자 사이트에 오신걸 환영합니다')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_css(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def css():
            return render_css(context)
        __M_writer = context.writer()
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_content(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        request = context.get('request', UNDEFINED)
        def content():
            return render_content(context)
        __M_writer = context.writer()
        __M_writer('\n')
        if request.session['is_staff'] in [1]:
            __M_writer('<div>\n  안녕하세요 담당 개발자입니다<br>\n  <br>\n  현재 지속적으로 기능이 추가되는 중입니다<br>\n  <br>\n  AS-IS 기능들은 전부 개선 완료되었습니다<br>\n  <br>\n  감사합니다<br>\n  <br>\n</div>\n')
        __M_writer('\n')
        if request.session['is_staff'] in [3]:
            __M_writer('<div>\n  안녕하세요 총판님<br>\n  <br>\n  TITAN VPN 담당 개발자입니다<br>\n  <br>\n  타이탄 관리자 사이트에 오신걸 환영합니다<br>\n  <br>\n  마케팅에 필요한 기능들을 지속적으로 추가할 예정입니다<br>\n  <br>\n  이용해주셔서 감사합니다<br>\n  <br>\n</div>\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_js(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def js():
            return render_js(context)
        __M_writer = context.writer()
        __M_writer('\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


"""
__M_BEGIN_METADATA
{"filename": "/home/ubuntu/project/titan-admin/backend/templates/admin/dashboard.html", "uri": "admin/dashboard.html", "source_encoding": "utf-8", "line_map": {"27": 0, "43": 1, "48": 3, "53": 4, "58": 6, "63": 36, "68": 39, "74": 3, "80": 3, "86": 4, "92": 4, "98": 6, "109": 8, "116": 8, "117": 9, "118": 10, "119": 21, "120": 22, "121": 23, "127": 38, "133": 38, "139": 133}}
__M_END_METADATA
"""
