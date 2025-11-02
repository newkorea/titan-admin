$("#login_pw").keydown(function(key) {
    if (key.keyCode == 13) {
        adminLogin();
    }
});

function adminLogin(){
    var csrf_token = $('#csrf_token').html();
    var login_id = $('#login_id').val();
    var login_pw = $('#login_pw').val();

    $.post( "/api/v1/login", {
       csrfmiddlewaretoken: csrf_token,
       input_id: login_id,
       input_pw: login_pw
    })
    .done(function( data ) {
      if (data.result == 200) {
        window.location.href = '/';
      }
      else {
        Swal.fire({
          title: data.title,
          text: data.text,
          type: 'error',
          confirmButtonColor: swalColor('error')
        })
      }
    });
}
