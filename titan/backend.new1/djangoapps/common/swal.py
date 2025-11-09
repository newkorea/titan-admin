# swal 다국어 문구 공통
def get_swal(LANGUAGE_CODE, type):
    if type == 'NULL_EMAIL':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'Enter your email'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '输入电子邮箱'
            return title, text
        else:
            title = '알림'
            text = '이메일을 입력하십시오'
            return title, text
    elif type == 'NULL_USERNAME':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'Enter your name'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '输入名字'
            return title, text
        else:
            title = '알림'
            text = '이름을 입력하십시오'
            return title, text
    elif type == 'NULL_PASSWORD':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'Enter your password'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '输入密码'
            return title, text
        else:
            title = '알림'
            text = '비밀번호를 입력하십시오'
            return title, text
    elif type == 'NULL_RE_PASSWORD':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'Re-enter password'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '再次输入密码'
            return title, text
        else:
            title = '알림'
            text = '비밀번호 확인을 입력하십시오'
            return title, text
    elif type == 'NOT_EMAIL':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'The email format is invalid'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '电子邮箱的形式不正确'
            return title, text
        else:
            title = '알림'
            text = '이메일 형식이 유효하지 않습니다'
            return title, text
    elif type == 'NOT_MATCH_PASSWORD':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'Password and password confirmation do not match'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '密码和再次输入密码不一致'
            return title, text
        else:
            title = '알림'
            text = '비밀번호와 비밀번호 확인이 일치하지 않습니다'
            return title, text
    elif type == 'NOT_PASSWORD_RULE':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'Password must be at least 8 words long and satisfy at least 2 combinations (choice from numeric, English, and special characters)'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '密码必须要8字以上及满足至少2种组合(数字,英语,特殊符号中选择两种)'
            return title, text
        else:
            title = '알림'
            text = '비밀번호는 8자 이상이며 최소 2가지 조합(숫자, 영어, 특수문자 중 선택2)을 만족해야합니다'
            return title, text
    elif type == 'INCORRECT_LOGIN':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'Email or password does not match'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '电子邮箱或密码不对'
            return title, text
        else:
            title = '알림'
            text = '이메일 또는 비밀번호가 일치하지 않습니다'
            return title, text
    elif type == 'NOT_ACTIVE':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'This email is not authenticated'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '该邮箱未经本人认证'
            return title, text
        else:
            title = '알림'
            text = '본인인증되지 않은 이메일입니다'
            return title, text
    elif type == 'UNKNOWN_ERROR':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'Unknown Error. Please contact to administrator'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '无法知道的错误。请向管理员咨询'
            return title, text
        else:
            title = '알림'
            text = '알 수 없는 오류입니다 관리자에게 문의바랍니다'
            return title, text
    elif type == 'OVER_LOGIN':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'Your account is locked because you have exceeded your login attempt'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '登录次数过多,帐号被锁定了'
            return title, text
        else:
            title = '알림'
            text = '로그인 시도 초과하여 계정이 잠겼습니다'
            return title, text
    elif type == 'SUCCESS_SIGNUP':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'We have sent you authentication mail in the email you entered'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '向您输入的邮箱发送了本人认证邮件'
            return title, text
        else:
            title = '회원가입 완료'
            text = '입력하신 이메일에 본인인증메일을 발송하였습니다'
            return title, text
    elif type == 'SUCCESS_SIGNUP_SP':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'Your membership has been completed'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '已注册会员'
            return title, text
        else:
            title = '회원가입 완료'
            text = '회원가입이 완료되었습니다'
            return title, text
    elif type == 'SUCCESS_RESET':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'Your password has been changed'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '密码变更好了'
            return title, text
        else:
            title = '알림'
            text = '비밀번호가 새롭게 변경되었습니다'
            return title, text
    elif type == 'NOT_SESSION':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'Wrong Access'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '是不正常的访问'
            return title, text
        else:
            title = '알림'
            text = '정상적이지 않은 접근입니다'
            return title, text
    elif type == 'NON_CHECK_SERVICE':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'You did not agree to the terms of Service'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '您还没同意服务利用条款'
            return title, text
        else:
            title = '알림'
            text = '서비스이용약관에 동의하지 않았습니다'
            return title, text
    elif type == 'NON_CHECK_PRIVACY':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'You did not agree with the privacy policy'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '您还没同意隐私权政策'
            return title, text
        else:
            title = '알림'
            text = '개인정보보호정책에 동의하지 않았습니다'
            return title, text
    elif type == 'NOT_USER':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'The registered email does not exist'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '不存在已注册的邮箱'
            return title, text
        else:
            title = '알림'
            text = '가입된 이메일이 존재하지 않습니다'
            return title, text
    elif type == 'SUCCESS_FORGOT':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'We sent the password change link to the email'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '向您输入的邮箱发送了变更密码链接'
            return title, text
        else:
            title = '알림'
            text = '입력하신 이메일에 비밀번호변경 링크를 발송하였습니다'
            return title, text
    elif type == 'BAN_DOMAIN':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'You cannot sign up for this email, Use Other Email address'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '不能加入的邮件 用别的EMail'
            return title, text
        else:
            title = '알림'
            text = '가입하실 수 없는 이메일입니다. 다른 이메일주소를 사용해주세요'
            return title, text
    elif type == 'BAN_IP':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = "Your IP address cannot be used for registration. Please contact the administrator through Channel Talk."
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '您的IP地址无法用于注册。请通过渠道对话联系管理员'
            return title, text
        else:
            title = '알림'
            text = '가입하실 수 없는 아이피입니다. 채널톡을 통해 관리자에 문의해주세요.'
            return title, text
    elif type == 'EXIST_EMAIL':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'This email is already registered.'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '已经加入的邮件'
            return title, text
        else:
            title = '알림'
            text = '이미 가입되어있는 이메일입니다.'
            return title, text
    elif type == 'ERROR_CODE':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'The referrer code you entered cannot be found. Please enter the correct referrer code. Can find it on my page after log in.'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '找不到您输入的推荐人代码。请输入正确的推荐人代码。登录后在我的页面上可以找到。'
            return title, text
        else:
            title = '알림'
            text = '입력하신 추천인 아이디를 찾을 수 없습니다. 정확한 추천인ID를 입력해주세요. 추천인 ID는 로그인 후 마이페이지에서 찾으실 수 있습니다.'
            return title, text
    elif type == 'CODE_EXPIRED':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'The referrer code you entered has expired. Please enter the correct referrer code. Can find it on my page after log in.'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '您输入的推荐人代码到期了。请输入正确的推荐人代码。登录后在我的页面上可以找到。'
            return title, text
        else:
            title = '알림'
            text = '입력하신 추천인 아이디가 만료되었습니다. 정확한 추천인ID를 입력해주세요. 추천인 ID는 로그인 후 마이페이지에서 찾으실 수 있습니다.'
            return title, text
    elif type == 'DELETE_ACCOUNT':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'The account has been successfully deleted.'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '帐户已成功删除。'
            return title, text
        else:
            title = '알림'
            text = '계정이 삭제되었습니다.'
            return title, text
    elif type == 'ERROR_PASSWORD':
        if LANGUAGE_CODE == 'en':
            title = 'Notification'
            text = 'The password is incorrect.'
            return title, text
        elif LANGUAGE_CODE == 'zh':
            title = '通知'
            text = '密码不正确。'
            return title, text
        else:
            title = '알림'
            text = '비밀번호가 정확하지 않습니다. '
            return title, text