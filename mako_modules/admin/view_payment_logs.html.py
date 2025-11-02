# -*- coding:utf-8 -*-
from mako import runtime, filters, cache
UNDEFINED = runtime.UNDEFINED
STOP_RENDERING = runtime.STOP_RENDERING
__M_dict_builtin = dict
__M_locals_builtin = locals
_magic_number = 10
_modified_time = 1751248282.2155051
_enable_loop = True
_template_filename = '/www/wwwroot/tiadmintansk1.titanvpn.kr/backend/templates/admin/view_payment_logs.html'
_template_uri = 'admin/view_payment_logs.html'
_source_encoding = 'utf-8'
_exports = ['title', 'content']


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
        logs = context.get('logs', UNDEFINED)
        def title():
            return render_title(context._locals(__M_locals))
        def content():
            return render_content(context._locals(__M_locals))
        __M_writer = context.writer()
        __M_writer('\n\n')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'title'):
            context['self'].title(**pageargs)
        

        __M_writer('\n\n')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'content'):
            context['self'].content(**pageargs)
        

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
        __M_writer('API 결제 승인 로그')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_content(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        logs = context.get('logs', UNDEFINED)
        def content():
            return render_content(context)
        __M_writer = context.writer()
        __M_writer('\n  <table class="table table-bordered">\n    <thead>\n      <tr>\n        <th>ID</th>\n        <th>요청시각</th>\n        <th>결제유형</th>\n        <th>금액</th>\n        <th>결제시각</th>\n        <th>IP</th>\n        <th>상태</th>\n        <th>결과</th>\n      </tr>\n    </thead>\n    <tbody>\n')
        for log in logs:
            __M_writer('        <tr>\n          <td>')
            __M_writer(filters.decode.utf8(log.id))
            __M_writer('</td>\n          <td>')
            __M_writer(filters.decode.utf8(log.request_time))
            __M_writer('</td>\n          <td>')
            __M_writer(filters.decode.utf8(log.payment_type))
            __M_writer('</td>\n          <td>')
            __M_writer(filters.decode.utf8(log.payment_amount))
            __M_writer('</td>\n          <td>')
            __M_writer(filters.decode.utf8(log.payment_time))
            __M_writer('</td>\n          <td>')
            __M_writer(filters.decode.utf8(log.ip_address))
            __M_writer('</td>\n          <td>')
            __M_writer(filters.decode.utf8(log.status))
            __M_writer('</td>\n          <td>')
            __M_writer(filters.decode.utf8(log.result_message))
            __M_writer('</td>\n        </tr>\n')
        __M_writer('    </tbody>\n  </table>\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


"""
__M_BEGIN_METADATA
{"filename": "/www/wwwroot/tiadmintansk1.titanvpn.kr/backend/templates/admin/view_payment_logs.html", "uri": "admin/view_payment_logs.html", "source_encoding": "utf-8", "line_map": {"27": 0, "37": 1, "42": 3, "47": 34, "53": 3, "59": 3, "65": 5, "72": 5, "73": 20, "74": 21, "75": 22, "76": 22, "77": 23, "78": 23, "79": 24, "80": 24, "81": 25, "82": 25, "83": 26, "84": 26, "85": 27, "86": 27, "87": 28, "88": 28, "89": 29, "90": 29, "91": 32, "97": 91}}
__M_END_METADATA
"""
