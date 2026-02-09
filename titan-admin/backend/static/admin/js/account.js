read_bank();
read_payment_methods();

function read_bank(){
  var csrf_token = $('#csrf_token').html();
  $.post( "/api/v1/read/account", {
      csrfmiddlewaretoken: csrf_token
  })
  .done(function( data ) {
      if(data.result == 200){
          var person_name = data.bank.person_name;
          var bank_name = data.bank.bank_name;
          var bank_number = data.bank.bank_number;
          $('#person_name').val(person_name);
          $('#bank_name').val(bank_name);
          $('#bank_number').val(bank_number);
      } else {
          Swal.fire({
            title: data.title,
            text: data.text,
            type: 'error',
            confirmButtonColor: swalColor('error')
          })
      }
  });
}

function read_payment_methods(){
  var csrf_token = $('#csrf_token').html();
  $.post( "/api/v1/read/payment_methods", {
      csrfmiddlewaretoken: csrf_token
  })
  .done(function( data ) {
      if(data.result == 200){
          $('#wechat_payment_enabled').prop('checked', data.wechat_enabled);
          $('#alipay_payment_enabled').prop('checked', data.alipay_enabled);
      } else {
          // 기본값 설정
          $('#wechat_payment_enabled').prop('checked', true);
          $('#alipay_payment_enabled').prop('checked', true);
      }
  });
}

function update_bank(){
    var csrf_token = $('#csrf_token').html();
    var person_name = $('#person_name').val();
    var bank_name = $('#bank_name').val();
    var bank_number = $('#bank_number').val();
    $.post( "/api/v1/update/account", {
        csrfmiddlewaretoken: csrf_token,
        person_name: person_name,
        bank_name: bank_name,
        bank_number: bank_number
    })
    .done(function( data ) {
        if (data.result == 200) {
            Swal.fire({
                title: data.title,
                text: data.text,
                type: 'success',
                confirmButtonColor: swalColor('success')
            }).then(function (result) {
                read_bank();
            })
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

function update_payment_methods(){
    var csrf_token = $('#csrf_token').html();
    var wechat_enabled = $('#wechat_payment_enabled').is(':checked');
    var alipay_enabled = $('#alipay_payment_enabled').is(':checked');
    $.post( "/api/v1/update/payment_methods", {
        csrfmiddlewaretoken: csrf_token,
        wechat_enabled: wechat_enabled,
        alipay_enabled: alipay_enabled
    })
    .done(function( data ) {
        if (data.result == 200) {
            Swal.fire({
                title: data.title,
                text: data.text,
                type: 'success',
                confirmButtonColor: swalColor('success')
            }).then(function (result) {
                read_payment_methods();
            })
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
