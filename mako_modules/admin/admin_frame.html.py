# -*- coding:utf-8 -*-
from mako import runtime, filters, cache
UNDEFINED = runtime.UNDEFINED
STOP_RENDERING = runtime.STOP_RENDERING
__M_dict_builtin = dict
__M_locals_builtin = locals
_magic_number = 10
_modified_time = 1762035869.2781713
_enable_loop = True
_template_filename = '/home/ubuntu/project/titan-admin/backend/templates/admin/admin_frame.html'
_template_uri = 'admin/admin_frame.html'
_source_encoding = 'utf-8'
_exports = ['css', 'title', 'subtitle', 'content', 'js']


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
        __M_writer('<html>\r\n<head>\r\n    ')
        runtime._include_file(context, 'admin_head.html', _template_uri)
        __M_writer('\r\n    ')
        runtime._include_file(context, 'admin_css.html', _template_uri)
        __M_writer('\r\n    ')
        runtime._include_file(context, 'admin_header.html', _template_uri)
        __M_writer('\r\n    ')
        runtime._include_file(context, 'admin_menu.html', _template_uri)
        __M_writer('\r\n    ')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'css'):
            context['self'].css(**pageargs)
        

        __M_writer('\r\n</head>\r\n<body>\r\n<section style="width: 100%">\r\n<div id="content" class="app-content box-shadow-0" role="main">\r\n  <div class="content-main" id="content-main">\r\n    <div class="padding">\r\n      <div class="box">\r\n        <div class="box-header light lt">\r\n          <h3>')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'title'):
            context['self'].title(**pageargs)
        

        __M_writer('</h3>\r\n          <small>')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'subtitle'):
            context['self'].subtitle(**pageargs)
        

        __M_writer('</small>\r\n        </div>\r\n        <div class="box-body">\r\n          ')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'content'):
            context['self'].content(**pageargs)
        

        __M_writer('\r\n        </div>\r\n      </div>\r\n    </div>\r\n  </div>\r\n</div>\r\n</section>\r\n</body>\r\n    ')
        runtime._include_file(context, 'admin_js.html', _template_uri)
        __M_writer('\r\n    ')
        if 'parent' not in context._data or not hasattr(context._data['parent'], 'js'):
            context['self'].js(**pageargs)
        

        __M_writer('\r\n</html>\r\n')
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


def render_title(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def title():
            return render_title(context)
        __M_writer = context.writer()
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_subtitle(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def subtitle():
            return render_subtitle(context)
        __M_writer = context.writer()
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_content(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def content():
            return render_content(context)
        __M_writer = context.writer()
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_js(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def js():
            return render_js(context)
        __M_writer = context.writer()
        return ''
    finally:
        context.caller_stack._pop_frame()


"""
__M_BEGIN_METADATA
{"filename": "/home/ubuntu/project/titan-admin/backend/templates/admin/admin_frame.html", "uri": "admin/admin_frame.html", "source_encoding": "utf-8", "line_map": {"16": 0, "31": 1, "32": 3, "33": 3, "34": 4, "35": 4, "36": 5, "37": 5, "38": 6, "39": 6, "44": 7, "49": 16, "54": 17, "59": 20, "60": 28, "61": 28, "66": 29, "72": 7, "83": 16, "94": 17, "105": 20, "116": 29, "127": 116}}
__M_END_METADATA
"""
