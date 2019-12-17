var csrf_token = $('#csrf_token').html();
var datatable = $('#user-inform').DataTable({
  dom: '<"top"Blf>rtp<"bottom"i>',
  paging: true,
  ordering: true,
  info: false,
  filter: false,
  lengthChange: false,
  order: [[0, "desc"]],
  stateSave: false,
  pagingType: "full_numbers",
  scrollX: false,
  scrollCollapse: false,
  processing: true,
  serverSide: true,
  drawCallback: function () {},
  ajax: {
      url: "/api_service_time_read",
      type: "POST",
      dataType: "json",
      data: {
          csrfmiddlewaretoken: csrf_token,
          id: function() { return $('#filter_id').val() },
          regist_date_start: function() { return $('#filter_regist_start').val() },
          regist_date_end: function() { return $('#filter_regist_end').val() },
      },
  },
  columns: [
      {data: "id"},
      {data: "email"},
      {data: "prev_time"},
      {data: "prev_time_rad"},
      {data: "after_time"},
      {data: "after_time_rad"},
      {data: "diff"},
      {data: "reason"},
      {data: "regist_date"}
  ],
  columnDefs: [
      {
        targets: 0,
        visible: true,
        render: function (data) {
          return data;
        }
      },
      {
        targets: 1,
        visible: true,
        render: function (data) {
          return data;
        }
      },
      {
        targets: 2,
        visible: true,
        render: function (data) {
          return data;
        }
      },
      {
        targets: 3,
        visible: true,
        render: function (data) {
          return data;
        }
      },
      {
        targets: 4,
        visible: true,
        render: function (data) {
          return data;
        }
      },
      {
        targets: 5,
        visible: true,
        render: function (data) {
          return data;
        }
      },
      {
        targets: 6,
        visible: true,
        render: function (data) {
          console.log('diff_data', data);
          if(data == '세션변경'){
              return data;
          } else {
              if (data < 0){
                data = Math.abs(data)
                var hour = Math.round(data / 60)
                var minutes = data % 60
                var time = '-' + hour + '시간 ' + minutes + '분'
                return time;
              }
              else{
                var hour = Math.round(data / 60)
                var minutes = data % 60
                var time = hour + '시간 ' + minutes + '분'
                return time;
              }
          }
        }
      },
      {
        targets: 7,
        visible: true,
        render: function (data) {
          return '<button type="button" class="btn btn-outline b-primary text-primary" data-toggle="tooltip" data-placement="bottom" title="' + data +'">사유</button>';
        }
      },
      {
        targets: 8,
        visible: true,
        render: function (data) {
          return data;
        }
      }
  ],
  language: {
      lengthMenu: "Display _MENU_ records per page",
      zeroRecords: "데이터가 존재하지 않습니다",
      info: "Showing page _PAGE_ of _PAGES_",
      infoEmpty: "No records available",
      infoFiltered: "(filtered from _MAX_ total records)",
      paginate: {
          first: '처음',
          last: '끝',
          previous: "이전",
          next: "다음"
      }
  },
});

function click_service(user_seq){
    $.post( "/api_service_read", {
        csrfmiddlewaretoken: csrf_token,
        user_seq: user_seq,
    }).done(function (data) {
        swal.fire({
            title: '서비스 시간 적용',
            type: 'info',
            html:
                '<form class="form-inline" style="margin-top: 20px;">' +
                '<label class="swal-label"><span class="label-span">현재 적용시간</span></label>' +
                '<input class="swal-control form-control" type="text" value="'+data.service_time+'" readonly></form>' +
                '<form class="form-inline">' +
                '<label class="swal-label"><span class="label-span">변경할 시간</span></label>' +
                '<input class="swal-control form-control" type="text" id="swal_time" value="'+data.service_time+'"></form>',
            confirmButtonText: '수정',
            confirmButtonColor: swalColor('info'),
            cancelButtonText: '취소',
            showCloseButton: true,
            showCancelButton: true,
        }).then((call) => {
          console.log('call -> ', call);
          console.log('call/dismiss -> ', call['dismiss']);
          console.log('call/value -> ', call['value']);

          if(call['value'] == true){
            var mody_time = $("input[type=text][id=swal_time]").val();
            console.log('mod', mody_time.length);
            if(mody_time.length != 19){
              Swal.fire({
                  title: '알림',
                  text: '시간 형식을 맞게 입력해주세요.',
                  type: 'warning',
                  confirmButtonColor: swalColor('warning')
              })
              return 0;
            }
            $.post("/api_service_update", {
                csrfmiddlewaretoken: csrf_token,
                mody_time: mody_time,
                user_seq: user_seq,
            })
            .done(function (data) {
                if (data.result == '200') {
                    Swal.fire({
                        title: '알림',
                        text: '서비스 시간이 성공적으로 변경되었습니다.',
                        type: 'success',
                        confirmButtonColor: swalColor('success'),
                    }).then(function (ok) {
                        if (ok) {
                            datatable.ajax.reload();
                        }
                    })
                }
                else{
                  Swal.fire({
                      title: '알림',
                      text: '오류 발생 관리자에게 문의하세요.',
                      type: 'warning',
                      confirmButtonColor: swalColor('warning')
                  })
                  return 0;
                }
            })
          }
        })
    })
}

function click_search(){
    datatable.ajax.reload();
}

function editView() {
    id = $('input[id=user_id]').val();
    active = $('#user_active').val();
    delete_yn = $('#user_delete').val();
    staff = $('#user_staff').val();
    black = $('#user_black').val();
    $.ajax({
        url: "/api_user_edit",
        type: "POST",
        async: false, // ture: 비동기, false: 동기
        data: {
            csrfmiddlewaretoken: csrf_token,
            id: id,
            active: active,
            delete_yn: delete_yn,
            staff: staff,
            black: black,
        },
        dataType: "json",
        success: function(data){
            if (data.result == '200') {
                Swal.fire({
                    title: '알림',
                    text: '성공적으로 변경되었습니다.',
                    type: 'success',
                    confirmButtonColor: swalColor('success')
                })
                click_search();
            }
        }
    });
}

function callInnerView(seq){
  $('.user-table').hide();
  $('.user-filter').hide();
  $('.btn-store').hide();
  $('.inner-title').fadeIn();
  $('.inner-view').fadeIn();
  $('.inner-view').css({display: 'flex'})
    $.ajax({
        url: "/api_user_detail",
        type: "POST",
        async: false, // ture: 비동기, false: 동기
        data: {
            csrfmiddlewaretoken: csrf_token,
            seq: seq,
        },
        dataType: "json",
        success: function(data){
            $('input[id=user_id]').attr('value', data.result[0]['id']);
            $('input[id=user_email]').attr('value', data.result[0]['email']);
            $('input[id=user_name]').attr('value', data.result[0]['username']);
            $('input[id=user_phone]').attr('value', data.result[0]['phone']);
            $('input[id=user_gender]').attr('value', data.result[0]['gender']);
            $('input[id=user_birth]').attr('value', data.result[0]['birth_date']);
            $('input[id=user_sns]').attr('value', data.result[0]['sns']);
            $('input[id=user_regist]').attr('value', data.result[0]['regist_date']);
            $('input[id=user_rec1]').attr('value', data.result[0]['rec']);
            $('input[id=user_rec2]').attr('value', data.result[0]['regist_rec']);
            $('input[id=user_rec_ip]').attr('value', data.result[0]['regist_ip']);
            $('input[id=user_attempt]').attr('value', data.result[0]['attempt']);
            $('input[id=user_login_ip]').attr('value', data.result[0]['login_ip']);
            $('input[id=user_login_date]').attr('value', data.result[0]['login_date']);
            $('#user_active').val(data.result[0]['is_active']).attr("selected", "selected");
            $('#user_delete').val(data.result[0]['delete_yn']).attr("selected", "selected");
            $('#user_staff').val(data.result[0]['is_staff']).attr("selected", "selected");
            $('#user_black').val(data.result[0]['black_yn']).attr("selected", "selected");
        }
    });
}

function returnView(seq){
    $('input[id=user_id]').attr('value', '');
    $('input[id=user_email]').attr('value', '');
    $('input[id=user_name]').attr('value', '');
    $('input[id=user_phone]').attr('value', '');
    $('input[id=user_gender]').attr('value', '');
    $('input[id=user_birth]').attr('value', '');
    $('input[id=user_sns]').attr('value', '');
    $('input[id=user_regist]').attr('value', '');
    $('input[id=user_rec1]').attr('value', '');
    $('input[id=user_rec2]').attr('value', '');
    $('input[id=user_rec_ip]').attr('value', '');

  $('.user-table').fadeIn();
  $('.user-filter').fadeIn();
  $('.btn-store').fadeIn();
  $('.inner-title').hide();
  $('.inner-view').hide();
}
