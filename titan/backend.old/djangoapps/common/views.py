import hashlib
from django.http import JsonResponse


def get_client_ip(request):
	xff = request.META.get('HTTP_X_FORWARDED_FOR')
	if xff:
		ip = xff.split(',')[0].strip()
	else:
		ip = request.META.get('REMOTE_ADDR')
	return ip


def hashText(text: str) -> str:
	return hashlib.sha256(text.encode('utf-8')).hexdigest()


def matchHashedText(hashed: str, plain: str) -> bool:
	return hashed == hashText(plain)


# Radius Expiration 포맷 헬퍼 (YYMMDDHHMMSS)
def enc_radius_time(dt):
	try:
		return dt.strftime('%y%m%d%H%M%S')
	except Exception:
		return ''


def duplicatePaymentProtect(user):
	# 프론트/서버에서 1분 재사용 정책으로 제어하므로, 기본 False 반환
	return False


# 결제 유틸: 코드/가격/상품명
def convertEximbayCode(pgcode):
	mapping = {
		'WECHAT': 'P141',
		'ALIPAY': 'P003',
		'PLCreditCard': 'P101',
	}
	return mapping.get(pgcode, pgcode)


def createOrderNumber(user_id):
	import uuid
	return f"{user_id}-{uuid.uuid4().hex[:12]}"


def createCustomParameter(session, month_type):
	return f"{session}_{month_type}"


def makeProductName(session, month_type):
	return f"{session} Session / {month_type} Month"


def getProductPirce(session, month_type, cur):
	# 기존 템플릿 가격표와 일치하도록 간단 매핑 (필요 시 서버 로직 교체)
	s = int(session)
	m = int(month_type)
	KRW = {
		1: {1: 8300, 2: 16600, 3: 24900, 6: 47000, 12: 83000},
		2: {1: 14000,2: 28000,3: 42000,6: 69000,12: 125000},
		3: {1: 22000,2: 44000,3: 66000,6: 110000,12: 199000},
		4: {1: 28000,2: 56000,3: 84000,6: 135000,12: 249000},
		5: {1: 35000,2: 70000,3: 105000,6: 179000,12: 329000},
		6: {1: 43300,2: 86600,3: 125400,6: 226000,12: 412000},
	}
	USD = {
		1: {1: 7, 2: 14, 3: 21, 6: 40, 12: 70},
		2: {1: 12,2: 24,3: 36,6: 58,12: 105},
		3: {1: 19,2: 38,3: 55,6: 95,12: 169},
		4: {1: 24,2: 48,3: 72,6: 110,12: 210},
		5: {1: 30,2: 60,3: 89,6: 149,12: 279},
		6: {1: 37,2: 74,3: 110,6: 189,12: 349},
	}
	CNY = {
		1: {1: 69, 2: 98, 3: 147, 6: 280, 12: 490},
		2: {1: 99, 2: 170,3: 255, 6: 399, 12: 720},
		3: {1: 168,2: 336,3: 402,6: 670,12: 1199},
		4: {1: 198,2: 396,3: 510,6: 798,12: 1420},
		5: {1: 259,2: 518,3: 649,6: 798,12: 1890},
		6: {1: 328,2: 656,3: 718,6: 1330,12: 2380},
	}
	table = {'KRW': KRW, 'USD': USD, 'CNY': CNY}.get(cur, USD)
	try:
		return str(table[s][m])
	except Exception:
		return '0'

