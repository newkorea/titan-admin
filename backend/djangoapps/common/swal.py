# swal 문구 공통
def get_swal(type):
    if type == 'NULL_EMAIL':
        title = '알림'
        text = '이메일을 입력하십시오'
        return title, text
    elif type == 'NULL_USERNAME':
        title = '알림'
        text = '이름을 입력하십시오'
        return title, text
    elif type == 'NULL_PASSWORD':
        title = '알림'
        text = '비밀번호를 입력하십시오'
        return title, text
    elif type == 'NULL_RE_PASSWORD':
        title = '알림'
        text = '비밀번호 확인을 입력하십시오'
        return title, text
    elif type == 'NOT_EMAIL':
        title = '알림'
        text = '이메일 형식이 유효하지 않습니다'
        return title, text
    elif type == 'NOT_MATCH_PASSWORD':
        title = '알림'
        text = '비밀번호와 비밀번호 확인이 일치하지 않습니다'
        return title, text
    elif type == 'NOT_PASSWORD_RULE':
        title = '알림'
        text = '비밀번호는 8자 이상이며 최소 2가지 조합(숫자, 영어, 특수문자 중 선택2)을 만족해야합니다'
        return title, text
    elif type == 'INCORRECT_LOGIN':
        title = '알림'
        text = '이메일 또는 비밀번호가 일치하지 않습니다'
        return title, text
    elif type == 'NOT_ACTIVE':
        title = '알림'
        text = '본인인증되지 않은 이메일입니다'
        return title, text
    elif type == 'UNKNOWN_ERROR':
        title = '알림'
        text = '알 수 없는 오류입니다 관리자에게 문의바랍니다'
        return title, text
    elif type == 'OVER_LOGIN':
        title = '알림'
        text = '로그인 시도 초과하여 계정이 잠겼습니다'
        return title, text
    elif type == 'SUCCESS_SIGNUP':
        title = '회원가입 완료'
        text = '입력하신 이메일에 본인인증메일을 발송하였습니다'
        return title, text
    elif type == 'SUCCESS_RESET':
        title = '알림'
        text = '비밀번호가 새롭게 변경되었습니다'
        return title, text
    elif type == 'NOT_SESSION':
        title = '알림'
        text = '정상적이지 않은 접근입니다'
        return title, text
    elif type == 'NON_CHECK_SERVICE':
        title = '알림'
        text = '서비스이용약관에 동의하지 않았습니다'
        return title, text
    elif type == 'NON_CHECK_PRIVACY':
        title = '알림'
        text = '개인정보보호정책에 동의하지 않았습니다'
        return title, text
    elif type == 'NOT_USER':
        title = '알림'
        text = '가입된 이메일이 존재하지 않습니다'
        return title, text
    elif type == 'SUCCESS_FORGOT':
        title = '알림'
        text = '입력하신 이메일에 비밀번호변경 링크를 발송하였습니다'
        return title, text
    elif type == 'NOT_ALLOW_IP':
        title = '알림'
        text = '허용되지 않은 IP 접근입니다'
        return title, text
    elif type == 'NOT_TIME_FORMAT':
        title = '알림'
        text = '유효하지 않은 시간 형식입니다'
        return title, text
    elif type == 'SUCCESS_SERVICE_TIME':
        title = '알림'
        text = '서비스 시간이 변경되었습니다'
        return title, text
    elif type == 'NOT_SESSION_FORMAT':
        title = '알림'
        text = '유효하지 않은 세션값입니다'
        return title, text
    elif type == 'SUCCESS_SESSION':
        title = '알림'
        text = '세션이 변경되었습니다'
        return title, text
    elif type == 'SUCCESS_PASSWORD':
        title = '알림'
        text = '비밀번호가 변경되었습니다'
        return title, text
    elif type == 'SUCCESS_ACTIVE':
        title = '알림'
        text = '활성화 상태가 변경되었습니다'
        return title, text
    elif type == 'SUCCESS_DELETE_USER':
        title = '알림'
        text = '회원 탈퇴 처리가 완료되었습니다'
        return title, text
    elif type == 'PAYMENT_ERROR':
        title = '알림'
        text = '환불 API 반환이 정상적으로 반환되지 않았습니다'
        return title, text
    elif type == 'PAYMENT_UNKNOWN':
        title = '알림'
        text = '알 수 없는 결제 수단 입니다'
        return title, text
    elif type == 'PAYMENT_SUCCESS':
        title = '알림'
        text = '환불이 정상적으로 처리되었습니다'
        return title, text
    elif type == 'PAYMENT_ALREADY':
        title = '알림'
        text = '이미 처리된 트랜잭션 입니다'
        return title, text
    elif type == 'SUCCESS_ACCOUNT':
        title = '알림'
        text = '성공적으로 계좌 정보가 수정되었습니다'
        return title, text
    elif type == 'SUCCESS_BANK':
        title = '알림'
        text = '결제요청이 정상적으로 등록되었습니다'
        return title, text
    elif type == 'SUCCESS_COMMON':
        title = '알림'
        text = '프로세스가 정상적으로 등록되었습니다'
        return title, text
    elif type == 'SUCCESS_BLOCK':
        title = '알림'
        text = '테이블 내에 있는 사용자들 전부 차단 완료되었습니다'
        return title, text
