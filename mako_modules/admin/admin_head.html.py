# -*- coding:utf-8 -*-
from mako import runtime, filters, cache
UNDEFINED = runtime.UNDEFINED
STOP_RENDERING = runtime.STOP_RENDERING
__M_dict_builtin = dict
__M_locals_builtin = locals
_magic_number = 10
_modified_time = 1756526489.4286468
_enable_loop = True
_template_filename = '/home/ubuntu/project/titan-admin/backend/templates/admin/admin_head.html'
_template_uri = 'admin/admin_head.html'
_source_encoding = 'utf-8'
_exports = []


def render_body(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        __M_locals = __M_dict_builtin(pageargs=pageargs)
        csrf_token = context.get('csrf_token', UNDEFINED)
        __M_writer = context.writer()
        __M_writer('<head>\r\n  <meta charset="utf-8" />\r\n  <title>TITAN | Admin</title>\r\n  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, minimal-ui" />\r\n  <meta http-equiv="X-UA-Compatible" content="IE=edge">\r\n  <meta name="apple-mobile-web-app-capable" content="yes">\r\n  <meta name="apple-mobile-web-app-status-barstyle" content="black-translucent">\r\n  <meta name="apple-mobile-web-app-title" content="Flatkit">\r\n  <meta name="mobile-web-app-capable" content="yes">\r\n  <link rel="shortcut icon" href="/static/admin/img/titan.png">\r\n</head>\r\n\r\n<div id="csrf_token" hidden>')
        __M_writer(filters.decode.utf8(csrf_token))
        __M_writer('</div>\r\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


"""
__M_BEGIN_METADATA
{"filename": "/home/ubuntu/project/titan-admin/backend/templates/admin/admin_head.html", "uri": "admin/admin_head.html", "source_encoding": "utf-8", "line_map": {"16": 0, "22": 1, "23": 13, "24": 13, "30": 24}}
__M_END_METADATA
"""
