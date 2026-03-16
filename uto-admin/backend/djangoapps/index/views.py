from django.shortcuts import redirect
from backend.djangoapps.common.views import login_check


@login_check
def index(request):
    return redirect('/uto_user')
