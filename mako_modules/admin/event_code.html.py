# -*- coding:utf-8 -*-
from mako import runtime, filters, cache
UNDEFINED = runtime.UNDEFINED
STOP_RENDERING = runtime.STOP_RENDERING
__M_dict_builtin = dict
__M_locals_builtin = locals
_magic_number = 10
_modified_time = 1762036398.9128177
_enable_loop = True
_template_filename = '/home/ubuntu/project/titan-admin/backend/templates/admin/event_code.html'
_template_uri = 'admin/event_code.html'
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
        def js():
            return render_js(context._locals(__M_locals))
        rows = context.get('rows', UNDEFINED)
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
        def title():
            return render_title(context)
        __M_writer = context.writer()
        __M_writer('이벤트 코드')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_subtitle(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def subtitle():
            return render_subtitle(context)
        __M_writer = context.writer()
        __M_writer('TITAN VPN 이벤트 코드를 관리할 수 있습니다')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_content(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        rows = context.get('rows', UNDEFINED)
        def content():
            return render_content(context)
        __M_writer = context.writer()
        __M_writer('\n\n  <!-- 버튼 -->\n  <div class=\'btn-store\'>\n    <button class="btn btn-fw success mr-2" onclick="add_default_setting()">\n      <i class="fa fa-plus mr5"></i>\n      Default Reward 설정\n    </button>\n    <button class="btn btn-fw success" onclick="add_event()">\n      <i class="fa fa-plus mr5"></i>\n      이벤트 등록하기\n    </button>\n  </div>\n\n  <!-- 데이터테이블즈 -->\n  <div class="user-table">\n    <table id="event_code" class="table display">\n      <thead>\n        <tr>\n          <th>이벤트 코드</th>\n          <th>적용 시작일시</th>\n          <th>적용 종료일시</th>\n          <th>무료체험일</th>\n          <th>Reward Percent</th>\n          <th>적용 상태</th>\n          <th>등록일시</th>\n          <th>삭제일시</th>\n          <th>삭제여부</th>\n          <th>삭제</th>\n          <th>수정</th>\n        </tr>\n      </thead>\n      <tbody>\n')
        for row in rows:
            __M_writer('        <tr>\n            <th>')
            __M_writer(filters.decode.utf8(row['event_code']))
            __M_writer('</th>\n            <td>')
            __M_writer(filters.decode.utf8(row['start']))
            __M_writer('</td>\n            <td>')
            __M_writer(filters.decode.utf8(row['end']))
            __M_writer('</td>\n            <td>')
            __M_writer(filters.decode.utf8(row['free_day']))
            __M_writer('</td>\n            <td>')
            __M_writer(filters.decode.utf8(row['reward_percent']))
            __M_writer('</td>\n            <td>')
            __M_writer(filters.decode.utf8(row['status']))
            __M_writer('</td>\n            <td>')
            __M_writer(filters.decode.utf8(row['regist_date']))
            __M_writer('</td>\n            <td>')
            __M_writer(filters.decode.utf8(row['delete_date']))
            __M_writer('</td>\n            <td>')
            __M_writer(filters.decode.utf8(row['delete_yn']))
            __M_writer('</td>\n            <td>\n                <button onclick="delete_event(\'')
            __M_writer(filters.decode.utf8(row['event_code']))
            __M_writer('\')" class="btn btn-outline b-danger text-danger">삭제</button>\n            </td>\n            <td>\n                <button onclick="modify_event(\'')
            __M_writer(filters.decode.utf8(row['event_code']))
            __M_writer('\')" class="btn btn-outline b-primary text-primary">수정</button>\n            </td>\n        </tr>\n')
        __M_writer('      </tbody>\n    </table>\n  </div>\n\n  <div style="margin-top: 10px;">\n      * 적용 시작일시는 현재시간보다 과거일 수 없습니다 (트랜잭션 오류 가능성)<br>\n      * 적용 시작일시는 적용 종료일시보다 미래일 수 없습니다<br>\n      * 삭제여부가 "삭제"인 이벤트는 적용되지 않습니다<br>\n      * 이벤트 코드는 대소문자 구분을 하지않고 적용됩니다<br>\n      * 사용자 추천인 코드와 중복되지 않도록 프로세스가 적용되어있습니다<br>\n  </div>\n</div>\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


def render_js(context,**pageargs):
    __M_caller = context.caller_stack._push_frame()
    try:
        def js():
            return render_js(context)
        __M_writer = context.writer()
        __M_writer('\n<script src="/static/admin/js/event.js"></script>\n')
        return ''
    finally:
        context.caller_stack._pop_frame()


"""
__M_BEGIN_METADATA
{"filename": "/home/ubuntu/project/titan-admin/backend/templates/admin/event_code.html", "uri": "admin/event_code.html", "source_encoding": "utf-8", "line_map": {"27": 0, "43": 1, "48": 4, "53": 6, "58": 7, "63": 73, "68": 77, "74": 3, "80": 3, "86": 6, "92": 6, "98": 7, "104": 7, "110": 9, "117": 9, "118": 42, "119": 43, "120": 44, "121": 44, "122": 45, "123": 45, "124": 46, "125": 46, "126": 47, "127": 47, "128": 48, "129": 48, "130": 49, "131": 49, "132": 50, "133": 50, "134": 51, "135": 51, "136": 52, "137": 52, "138": 54, "139": 54, "140": 57, "141": 57, "142": 61, "148": 75, "154": 75, "160": 154}}
__M_END_METADATA
"""
