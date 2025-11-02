# -*- coding:utf-8 -*-
from mako import runtime, filters, cache
UNDEFINED = runtime.UNDEFINED
STOP_RENDERING = runtime.STOP_RENDERING
__M_dict_builtin = dict
__M_locals_builtin = locals
_magic_number = 10
_modified_time = 1756526489.4303522
_enable_loop = True
_template_filename = '/home/ubuntu/project/titan-admin/backend/templates/admin/admin_css.html'
_template_uri = 'admin/admin_css.html'
_source_encoding = 'utf-8'
_exports = []


def render_body(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        __M_locals = __M_dict_builtin(pageargs=pageargs)
        __M_writer = context.writer()
        __M_writer('<link rel="stylesheet" href="/static/common/libs/font-awesome/css/font-awesome.min.css" type="text/css" />\r\n<link rel="stylesheet" href="/static/common/libs/bootstrap/dist/css/bootstrap.min.css" type="text/css" />\r\n<link rel="stylesheet" href="/static/common/assets/css/theme/primary.css" type="text/css" />\r\n<link rel="stylesheet" href="/static/common/assets/css/app.css" type="text/css" />\r\n<link rel="stylesheet" href="/static/common/assets/css/style.css" type="text/css" />\r\n<link rel="stylesheet" href="/static/common/assets/css/style.css" type="text/css" />\r\n<link rel="stylesheet" href="/static/admin/style.css" type="text/css" />\r\n\r\n<link rel="stylesheet" href="/static/cdn/jquery-ui.css" type="text/css" />\r\n<link rel="stylesheet" href="/static/cdn/jquery.dataTables.min.css" type="text/css" />\r\n<link rel="stylesheet" href="/static/cdn/summernote.css">\r\n\r\n<link rel="stylesheet" href="/static/common/libs/bootstrap-datepicker/dist/css/bootstrap-datepicker.min.css" type="text/css" />\r\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


"""
__M_BEGIN_METADATA
{"filename": "/home/ubuntu/project/titan-admin/backend/templates/admin/admin_css.html", "uri": "admin/admin_css.html", "source_encoding": "utf-8", "line_map": {"16": 0, "21": 1, "27": 21}}
__M_END_METADATA
"""
