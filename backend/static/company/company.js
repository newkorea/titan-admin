$('input[type=radio][name=sum]').on('click', function () {
  var chkValue = $('input[type=radio][name=sum]:checked').val();
  if(chkValue == '1') {
      note_disable();
      load_content();
  }
  else if(chkValue == '2') {
      note_disable();
      load_content();
  }
  else if(chkValue == '3') {
      note_disable();
      load_content();
  }
  else if(chkValue == '4') {
      note_disable();
      load_content();
  }
});

function click_edit(){
    var chkValue = $('input[type=radio][name=sum]:checked').val();
    var sum;
    var lang;
    var kind = $('#kind').html();
    if(chkValue == '1') {
        sum = $('#summernote1').summernote('code');
        lang = 'en';
    }
    else if(chkValue == '2') {
        sum = $('#summernote1').summernote('code');
        lang = 'ko';
    }
    else if(chkValue == '3') {
        sum = $('#summernote1').summernote('code');
        lang = 'ja';
    }
    else if(chkValue == '4') {
        sum = $('#summernote1').summernote('code');
        lang = 'zh';
    }
  var csrf_token = $('#csrf_token').html();
  if(sum == ''){
      Swal.fire({
          title: '알림',
          text: '내용 입력 없이 저장할 수 없습니다',
          type: 'error',
          confirmButtonColor: "#dc3545"
      })
    return 1;
  }
    Swal.fire({
        title: '알림',
        html:
            '<div style="font-size: 14px;">회사소개의 수정은 시스템의 중대한 영향을 미칩니다</div>'+
            '<div style="font-size: 14px;">정말로 저장하시겠습니까?</div>',
        confirmButtonColor: swalColor('error'),
        showCancelButton: true,
        confirmButtonText: '저장',
        cancelButtonText: "취소"
    }).then(function (result) {
        if (result.value) {
                $.post("/api_company_edit", {
                    csrfmiddlewaretoken: csrf_token,
                    sum: sum,
                    lang: lang,
                    kind: kind,
                })
                    .done(function (data) {
                        if (data.result == '200') {
                            Swal.fire({
                                title: '알림',
                                text: '회사소개가 성공적으로 변경되었습니다.',
                                type: 'success',
                                confirmButtonColor: swalColor('success'),
                            }).then(function (ok) {
                                if (ok) {
                                    load_content();
                                }
                            })
                        }
                    })

        }
    })
}

function load_content(){
    var chkValue = $('input[type=radio][name=sum]:checked').val();
    var csrf_token = $('#csrf_token').html();
    var kind = $('#kind').html();

    $.post( "/api_company_load", {
        csrfmiddlewaretoken: csrf_token,
        kind: kind
    })
        .done(function( data ) {
            for(var i=0; i<4; i++){
                if(chkValue == '1') {
                    $('#summernote1').summernote('code', data.result[0]['en']);
                }
                else if(chkValue == '2') {
                    $('#summernote1').summernote('code', data.result[0]['ko']);
                }
                else if(chkValue == '3') {
                    $('#summernote1').summernote('code', data.result[0]['ja']);
                }
                else if(chkValue == '4') {
                    $('#summernote1').summernote('code', data.result[0]['zh']);
                }
            }
        });
}
$(document).ready(function() {
    $('.summernote').on('summernote.init', function () {
    }).summernote({
        height: 500,
        lang: 'ko-KR',
        popover: {
            image: [],
            link: [],
            air: []
        },
    });
    note_disable();
    $('#summernote1').summernote('code', load_content());
});

function note_disable() {
    $('#summernote1').summernote('disable');
    $('.note-editable').attr('style', 'background-color: #e2e2e2 !important; height: 500px');

    setTimeout(note_enable, 1000);
}

function note_enable() {
    $('#summernote1').summernote('enable');
    $('.note-editable').attr('style', 'background-color: #ffffff !important; height: 500px');
}
