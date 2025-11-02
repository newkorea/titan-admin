# -*- coding:utf-8 -*-
from mako import runtime, filters, cache
UNDEFINED = runtime.UNDEFINED
STOP_RENDERING = runtime.STOP_RENDERING
__M_dict_builtin = dict
__M_locals_builtin = locals
_magic_number = 10
_modified_time = 1756526489.4318562
_enable_loop = True
_template_filename = '/home/ubuntu/project/titan-admin/backend/templates/admin/admin_js.html'
_template_uri = 'admin/admin_js.html'
_source_encoding = 'utf-8'
_exports = []


def render_body(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        __M_locals = __M_dict_builtin(pageargs=pageargs)
        __M_writer = context.writer()
        __M_writer('<script src="/static/cdn/jquery-1.12.4.js"></script>\r\n<script src="/static/cdn/jquery-ui.js"></script>\r\n<script src="/static/cdn/291a47d307.js"></script>\r\n\r\n<script src="/static/common/libs/jquery/dist/jquery.min.js"></script>\r\n<script src="/static/common/libs/jquery/dist/jquery.min.js"></script>\r\n<script src="/static/common/libs/popper.js/dist/umd/popper.min.js"></script>\r\n<script src="/static/common/libs/bootstrap/dist/js/bootstrap.min.js"></script>\r\n<script src="/static/common/libs/pace-progress/pace.min.js"></script>\r\n<script src="/static/common/libs/pjax/pjax.js"></script>\r\n<script src="/static/common/scripts/lazyload.config.js"></script>\r\n<script src="/static/common/scripts/lazyload.js"></script>\r\n<script src="/static/common/scripts/plugin.js"></script>\r\n<script src="/static/common/scripts/nav.js"></script>\r\n<script src="/static/common/scripts/scrollto.js"></script>\r\n<script src="/static/common/scripts/toggleclass.js"></script>\r\n<script src="/static/common/scripts/theme.js"></script>\r\n<script src="/static/common/scripts/ajax.js"></script>\r\n<script src="/static/common/scripts/app.js"></script>\r\n<script src="/static/common/swal2.js"></script>\r\n<script src="/static/common/swal2_color.js"></script>\r\n<script src="/static/common/countUp.js"></script>\r\n<script src="/static/common/libs/bootstrap-datepicker/dist/js/bootstrap-datepicker.min.js"></script>\r\n<script src="/static/chart/js/common_chart.js"></script>\r\n\r\n<script src="/static/cdn/sweetalert2@8"></script>\r\n<script src="/static/cdn/summernote.js"></script>\r\n<script src="/static/cdn/jquery.dataTables.min.js"></script>\r\n<script src="/static/cdn/Chart.min.js"></script>\r\n\r\n<script>\r\n    // 로그아웃\r\n    function callLogout(){\r\n        var csrf_token = $(\'#csrf_token\').html();\r\n        $.post( "/api/v1/logout", {\r\n            csrfmiddlewaretoken: csrf_token\r\n        })\r\n        .done(function( data ) {\r\n            if(data.result == 200){\r\n                window.location.href = "/login";\r\n            }\r\n        });\r\n    }\r\n\r\n    // 무통장 결제 대기 건수\r\n    function ready_count(){\r\n        var csrf_token = $(\'#csrf_token\').html();\r\n        $.post( "/api/v1/read/ready_count", {\r\n            csrfmiddlewaretoken: csrf_token\r\n        })\r\n        .done(function( data ) {\r\n            if(data.result == 200){\r\n                var ready_count = data.ready_count;\r\n                $(\'#ready_count\').html(ready_count);\r\n            }\r\n        });\r\n    }\r\n\r\n    // 현재 가입자 수\r\n    function use_count(){\r\n        var csrf_token = $(\'#csrf_token\').html();\r\n        $.post( "/api/v1/read/use_user", {\r\n            csrfmiddlewaretoken: csrf_token\r\n        })\r\n        .done(function( data ) {\r\n            if(data.result == 200){\r\n                var use_count = data.use_count;\r\n                $(\'#use_count\').html(use_count);\r\n            }\r\n        });\r\n    }\r\n\r\n    // 오늘 날짜 yyyy-mm-dd\r\n    function getNow(){\r\n        var dt = new Date();\r\n        var y = dt.getFullYear();\r\n        var m = ("00" + (dt.getMonth()+1)).slice(-2);\r\n        var d = ("00" + dt.getDate()).slice(-2);\r\n        var result = y + "-" + m + "-" + d;\r\n        return result;\r\n    }\r\n\r\n    // 내일 날짜 yyyy-mm-dd\r\n    function getTomorrow(){\r\n        var dt = new Date();\r\n        dt.setDate(dt.getDate() + 1);\r\n        var y = dt.getFullYear();\r\n        var m = ("00" + (dt.getMonth()+1)).slice(-2);\r\n        var d = ("00" + dt.getDate()).slice(-2);\r\n        var result = y + "-" + m + "-" + d;\r\n        return result;\r\n    }\r\n\r\n    // 오늘 dd\r\n    function current_day(type){\r\n        var dt = new Date();\r\n        var y = dt.getFullYear();\r\n        var m = ("00" + (dt.getMonth()+1)).slice(-2);\r\n        var d = ("00" + dt.getDate()).slice(-2);\r\n        var result = y + "-" + m + "-" + d;\r\n        if(type == \'year\'){\r\n            return Number(y);\r\n        } else if(type == \'month\'){\r\n            return Number(m);\r\n        } else if(type == \'day\'){\r\n            return Number(d);\r\n        }\r\n    }\r\n\r\n    // 초기화 실행\r\n    ready_count();\r\n    use_count();\r\n    $(\'.datepicker\').datepicker({ format: \'yyyy-mm-dd\' });\r\n</script>\r\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


"""
__M_BEGIN_METADATA
{"filename": "/home/ubuntu/project/titan-admin/backend/templates/admin/admin_js.html", "uri": "admin/admin_js.html", "source_encoding": "utf-8", "line_map": {"16": 0, "21": 1, "27": 21}}
__M_END_METADATA
"""
