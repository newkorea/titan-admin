$("#login_pw").keydown(function(key) {
    if (key.keyCode == 13) {
        adminLogin();
    }
});

function adminLogin(){

var csrf_token = $('#csrf_token').html();
var login_id = $('#login_id').val();
var login_pw = $('#login_pw').val();

if(login_id == ''){
  $('#login_id').focus();
  return false;
}
if(login_pw == ''){
  $('#login_pw').focus();
  return false;
}

$.post( "/api_login", {
   csrfmiddlewaretoken: csrf_token,
   input_id: login_id,
   input_pw: login_pw
})
.done(function( data ) {
  if(data.result == 200){
    window.location.href = '/';
  }
  else if(data.result == 300){
    Swal.fire({
      title: '알림',
      text: '계정이 잠겨있습니다.',
      type: 'error',
      confirmButtonColor: swalColor('error')
    })
  }
  else if(data.result == 400){
    Swal.fire({
      title: '알림',
      text: '해킹 시도 감지 - 법적으로 처벌 받을 수 있습니다',
      type: 'error',
      confirmButtonColor: swalColor('error')
    })
  }
  else if(data.result == 600){
    Swal.fire({
      title: '알림',
      text: '아이디 또는 비밀번호가 일치하지 않습니다',
      type: 'error',
      confirmButtonColor: swalColor('error')
    })
  }
  else if(data.result == 601){
    Swal.fire({
      title: '알림',
      text: '로그인 횟수 데이터가 잘못되었습니다',
      type: 'error',
      confirmButtonColor: swalColor('error')
    })
  }
  else if(data.result == 700){
    Swal.fire({
      title: '알림',
      text: '접근 권한 없음',
      type: 'error',
      confirmButtonColor: swalColor('error')
    })
  }
  else{
    Swal.fire({
      title: '알림',
      text: '알 수 없는 오류 - 관리자에게 문의하세요',
      type: 'error',
      confirmButtonColor: swalColor('error')
    })
  }
});
}
