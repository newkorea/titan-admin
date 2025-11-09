from django.conf import settings
from django.http import JsonResponse
from functools import wraps

def api_key_required(view_func):
    """ API Key를 검증하는 데코레이터 """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        api_key = request.headers.get("Authorization")  # 헤더에서 API Key 가져오기

        if not api_key or api_key != f"Bearer {settings.API_SECRET_KEY}":
            return JsonResponse({"status": "error", "message": "인증 실패! API Key가 유효하지 않습니다."}, status=403)

        return view_func(request, *args, **kwargs)

    return wrapper
