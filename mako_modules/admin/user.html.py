# -*- coding:utf-8 -*-
from mako import runtime, filters, cache
UNDEFINED = runtime.UNDEFINED
STOP_RENDERING = runtime.STOP_RENDERING
__M_dict_builtin = dict
__M_locals_builtin = locals
_magic_number = 10
_modified_time = 1762035893.683501
_enable_loop = True
_template_filename = '/home/ubuntu/project/titan-admin/backend/templates/admin/user.html'
_template_uri = 'admin/user.html'
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
        staff_list = context.get('staff_list', UNDEFINED)
        def js():
            return render_js(context._locals(__M_locals))
        active_list = context.get('active_list', UNDEFINED)
        delete_list = context.get('delete_list', UNDEFINED)
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
        

        __M_writer('\n')
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
        def title():
            return render_title(context)
        __M_writer = context.writer()
        __M_writer('\n\t<div class="row">\n    \t<div class="form-group col-sm-2">\n      \t\t<label>회원 관리</label>\n    \t</div>\n    \t<div class="form-group col-sm-10">\n      \t\t<label id="active_users"></label>\n      \t\t<label class="ml-3" id="session_one_users"></label>\n      \t\t<label class="ml-3" id="session_two_users"></label>\n      \t\t<label class="ml-3" id="session_three_users"></label>\n      \t\t<label class="ml-3" id="session_four_users"></label>\n      \t\t<label class="ml-3" id="session_five_users"></label>\n      \t\t<label class="ml-3" id="session_six_users"></label>\n      \t\t<label class="ml-3" id="expired_users"></label>\n      \t\t<label class="ml-3" id="deleted_users"></label>\n    \t</div>\n\t</div>\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_subtitle(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def subtitle():
            return render_subtitle(context)
        __M_writer = context.writer()
        __M_writer('TITAN VPN에 가입한 회원들을 관리할 수 있습니다')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_content(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        active_list = context.get('active_list', UNDEFINED)
        staff_list = context.get('staff_list', UNDEFINED)
        def content():
            return render_content(context)
        delete_list = context.get('delete_list', UNDEFINED)
        __M_writer = context.writer()
        __M_writer('\n  <!-- 검색필터 -->\n  <div class="row">\n    <div class="form-group col-sm-2">\n      <label>번호[=]</label>\n      <input class="form-control" id="filter_id">\n    </div>\n    <div class="form-group col-sm-2">\n      <label>이메일[like]</label>\n      <input class="form-control" id="filter_email">\n    </div>\n    <div class="form-group col-sm-2">\n      <label>사용자명[like]</label>\n      <input class="form-control" id="filter_name">\n    </div>\n    <div class="form-group col-sm-2">\n      <label>아이피[like]</label>\n      <input class="form-control" id="filter_ip">\n    </div>\n    <div class="form-group col-sm-2">\n      <label>삭제여부</label>\n      <select class="form-control" id="filter_delete" name="filter_delete">\n        <option value="">선택하세요</option>\n')
        for delete in delete_list:
            __M_writer('          <option value="')
            __M_writer(filters.decode.utf8( delete.code ))
            __M_writer('">')
            __M_writer(filters.decode.utf8( delete.name ))
            __M_writer('</option>\n')
        __M_writer('      </select>\n    </div>\n    <div class="form-group col-sm-2">\n      <label>활성여부</label>\n      <select class="form-control" id="filter_active" name="filter_active">\n        <option value="">선택하세요</option>\n')
        for active in active_list:
            __M_writer('          <option value="')
            __M_writer(filters.decode.utf8( active.code ))
            __M_writer('">')
            __M_writer(filters.decode.utf8( active.name ))
            __M_writer('</option>\n')
        __M_writer('      </select>\n    </div>\n    <div class="form-group col-sm-2">\n      <label>권한</label>\n      <select class="form-control" id="filter_staff" name="filter_staff">\n        <option value="">선택하세요</option>\n')
        for staff in staff_list:
            __M_writer('          <option value="')
            __M_writer(filters.decode.utf8( staff.code ))
            __M_writer('">')
            __M_writer(filters.decode.utf8( staff.name ))
            __M_writer('</option>\n')
        __M_writer('      </select>\n    </div>\n  </div>\n  <!-- 버튼 -->\n  <div class=\'btn-store\'>\n    <button class="btn btn-fw primary" onclick="reload_data()">\n      <i class="fa fa-search mr5"></i>\n      검색하기\n    </button>\n  </div>\n  <!-- 데이터테이블즈 -->\n  <div class="user-table">\n    <table id="user-inform" class="table display">\n      <thead>\n        <tr>\n          <th>번호</th>\n          <th>이메일</th>\n          <th>사용자명</th>\n          <th>삭제여부</th>\n          <th>활성여부</th>\n          <th>차단여부</th>\n          <th>권한</th>\n          <th>가입아이피</th>\n          <th>가입일시</th>\n          <th>추가정보</th>\n          <th>서비스</th>\n          <th>세션</th>\n          <th>비번</th>\n          <th>활성</th>\n          <th>탈퇴</th>\n          <th>앱퇴출</th>          \n        </tr>\n      </thead>\n      <tbody>\n      </tbody>\n    </table>\n  </div>\n</div>\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_js(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def js():
            return render_js(context)
        __M_writer = context.writer()
        __M_writer('\n<script src="/static/admin/js/user.js"></script>\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


"""
__M_BEGIN_METADATA
{"filename": "/home/ubuntu/project/titan-admin/backend/templates/admin/user.html", "uri": "admin/user.html", "source_encoding": "utf-8", "line_map": {"27": 0, "45": 1, "50": 4, "55": 23, "60": 24, "65": 107, "70": 111, "76": 3, "82": 3, "88": 6, "94": 6, "100": 24, "106": 24, "112": 25, "121": 25, "122": 48, "123": 49, "124": 49, "125": 49, "126": 49, "127": 49, "128": 51, "129": 57, "130": 58, "131": 58, "132": 58, "133": 58, "134": 58, "135": 60, "136": 66, "137": 67, "138": 67, "139": 67, "140": 67, "141": 67, "142": 69, "148": 109, "154": 109, "160": 154}}
__M_END_METADATA
"""
