import datetime
from pytz import timezone
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.db.models import Q
from django.conf import settings

from backend.models import TblUser, TblBankAccount, TblSendHistory
from backend.models_radius import Radcheck


def _dictfetchall(cursor):
	columns = [col[0] for col in cursor.description]
	return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _get_user_by_target_or_session(request, target_email):
	if target_email:
		try:
			return TblUser.objects.get(email=target_email)
		except TblUser.DoesNotExist:
			return None
	if 'id' not in request.session:
		return None
	try:
		return TblUser.objects.get(id=request.session['id'])
	except TblUser.DoesNotExist:
		return None


# [render] 이용가격
def price(request):
	LANGUAGE_CODE = getattr(request, 'LANGUAGE_CODE', 'ko')

	current_user_email = ''
	target_emails = []

	user = None
	if 'id' in request.session:
		try:
			user = TblUser.objects.get(id=request.session['id'])
			current_user_email = user.email or ''
			# 본인 + 추천인(rec)로 가입된 사용자들(regist_rec == 내 rec)
			target_emails = [current_user_email]
			if user.rec:
				ref_emails = list(
					TblUser.objects.filter(regist_rec=user.rec, delete_yn='N').values_list('email', flat=True)
				)
				# 중복 제거
				for em in ref_emails:
					if em and em not in target_emails:
						target_emails.append(em)
		except TblUser.DoesNotExist:
			pass

	# 무통장 계좌(없으면 빈 값)
	person_name = bank_name = bank_number = ''
	try:
		# 타입 구분이 불명확하므로 첫 레코드 사용
		ba = TblBankAccount.objects.all().first()
		if ba:
			person_name = ba.person_name or ''
			bank_name = ba.bank_name or ''
			bank_number = ba.bank_number or ''
	except Exception:
		pass

	context = {
		'LANGUAGE_CODE': LANGUAGE_CODE,
		'person_name': person_name,
		'bank_name': bank_name,
		'bank_number': bank_number,
		'target_emails': target_emails,
		'current_user_email': current_user_email,
	}
	return render(request, 'new/price.html', context)


# [api] 최근 결제(요청) 여부 확인: 1분 이내 동일 타입의 대기(R)건 존재 여부
@csrf_protect
def api_check_recent_payments(request):
	if 'id' not in request.session:
		return JsonResponse({'hasRecentPayments': False})
	user_id = request.session['id']
	p_type = request.POST.get('type')  # 'A' (ALIPAY_IV) / 'W' (WECHAT_IV) 등
	now = datetime.datetime.now(timezone('Asia/Seoul'))
	one_min_ago = now - datetime.timedelta(minutes=1)

	qs = TblSendHistory.objects.filter(user_id=user_id, status='R', regist_date__gte=one_min_ago)
	if p_type:
		qs = qs.filter(type=p_type)
	has_recent = qs.exists()
	return JsonResponse({'hasRecentPayments': has_recent})


# [api] 세션 변경 시 대상 계정 비밀번호 필요 여부 및 검증
@csrf_protect
def api_check_session_and_auth(request):
	target_email = request.POST.get('target_email')
	new_session = request.POST.get('session')  # str
	password = request.POST.get('password')  # 선택적

	# 파라미터 체크
	try:
		new_session_int = int(new_session) if new_session is not None else None
	except ValueError:
		return JsonResponse({'ok': False, 'need_password': False, 'error': 'INVALID_SESSION'})

	u = _get_user_by_target_or_session(request, target_email)
	if not u:
		return JsonResponse({'ok': False, 'need_password': False, 'error': 'USER_NOT_FOUND'})

	# 현재 동시접속(세션) 조회 (radius.radcheck)
	current_session = None
	try:
		rc = Radcheck.objects.using('radius').filter(username=u.email, attribute='Simultaneous-Use').first()
		if rc and rc.value:
			current_session = int(rc.value)
	except Exception:
		pass

	# 세션이 다르면 비밀번호 요구
	need_password = (new_session_int is not None and current_session is not None and new_session_int != current_session)

	if not need_password:
		return JsonResponse({'ok': True, 'need_password': False})

	# 비밀번호 검증
	if password is None or password == '':
		return JsonResponse({'ok': False, 'need_password': True, 'error': 'NEED_PASSWORD'})

	# 로컬 해시 비교 (SHA-256 가정)
	import hashlib

	def _hash_text(txt: str) -> str:
		return hashlib.sha256(txt.encode('utf-8')).hexdigest()

	is_match = (u.password == _hash_text(password))
	return JsonResponse({'ok': is_match, 'need_password': True, 'error': None if is_match else 'INVALID_PASSWORD'})


# [api] 수기 QR/무통장 결제 생성 및 재사용(1분 규칙)
@csrf_protect
def api_create_payment(request):
	p_type = request.POST.get('type')    # 'A'/'W'/'B' 등
	pgcode = request.POST.get('pgcode')  # 표기용
	session = request.POST.get('session')
	month_type = request.POST.get('month_type')
	target_email = request.POST.get('target_email')

	try:
		session_i = int(session)
		month_i = int(month_type)
	except (TypeError, ValueError):
		return JsonResponse({'result': 400, 'message': 'INVALID_PARAMS'})

	u = _get_user_by_target_or_session(request, target_email)
	if not u:
		return JsonResponse({'result': 404, 'message': 'User not found'})

	now = datetime.datetime.now(timezone('Asia/Seoul'))
	one_min_ago = now - datetime.timedelta(minutes=1)

	# 동일 사용자/세션/개월/타입의 대기건 재사용 정책
	existing = TblSendHistory.objects.filter(
		user_id=u.id,
		session=session_i,
		month_type=month_i,
		type=p_type,
		status='R'
	).order_by('-regist_date').first()

	if existing:
		if existing.regist_date and existing.regist_date >= one_min_ago:
			# 1분 이내면 갱신하지 않고 알림만
			return JsonResponse({'result': 202, 'message': 'PENDING_EXISTS', 'data': {'email': u.email}, 'id': existing.id})
		else:
			# 1분 이후면 시간만 갱신하여 재사용
			existing.regist_date = now
			existing.save(update_fields=['regist_date'])
			return JsonResponse({'result': 200, 'message': 'PENDING_REUSED', 'data': {'email': u.email}, 'id': existing.id})

	# 새 요청 생성
	tsh = TblSendHistory(
		user_id=u.id,
		product_name=f"{session_i}session_{month_i}month",
		session=session_i,
		month_type=month_i,
		krw=None,
		usd=None,
		jpy=None,
		cny=None,
		status='R',  # 대기
		type=p_type,
		regist_date=now,
		accept_date=None,
		cancel_date=None,
		refund_date=None,
	)
	tsh.save()
	return JsonResponse({'result': 200, 'message': 'CREATED', 'data': {'email': u.email}, 'id': tsh.id})


# 아래 API들은 URL 매핑상 필수이므로 최소 동작 구현으로 제공
@csrf_protect
def api_plz_payment(request):
	return JsonResponse({'result': 501, 'message': 'NOT_IMPLEMENTED'})


@csrf_protect
def api_delete_account(request):
	return JsonResponse({'result': 501, 'message': 'NOT_IMPLEMENTED'})


def payletter_cancel(request):
	return redirect('/price')


def globalpayletter_cancel(request):
	return redirect('/price')


def paybox_cancel(request):
	return redirect('/price')


@csrf_protect
def api_check_payment_status(request):
	# 간단한 placeholder: 실제 승인 확인 로직은 결제 모듈 콜백/조회에 의존
	return JsonResponse({'status': 'pending'})

