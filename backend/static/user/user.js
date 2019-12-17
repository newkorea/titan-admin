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
      url: "/api_user_read",
      type: "POST",
      dataType: "json",
      data: {
          csrfmiddlewaretoken: csrf_token,
          id: function() { return $('#filter_id').val() },
          email: function() { return $('#filter_email').val() },
          username: function() { return $('#filter_name').val() },
          gender: function() {
              if($('#filter_gender option:selected').text() == "선택하세요") {
                  return '';
              }
              else
                  return $('#filter_gender').val();
          },
          delete: function() {
              if($('#filter_delete option:selected').text() == "선택하세요") {
                  return '';
              }
              else
                  return $('#filter_delete').val();
          },
          black: function() {
              if($('#filter_black option:selected').text() == "선택하세요") {
                  return '';
              }
              else
                  return $('#filter_black').val();
          },
          active: function() {
              if($('#filter_active option:selected').text() == "선택하세요") {
                  return '';
              }
              else
                  return $('#filter_active').val();
          },
          staff: function() {
              if($('#filter_staff option:selected').text() == "선택하세요") {
                  return '';
              }
              else
                  return $('#filter_staff').val();
          },
      },
  },
  columns: [
      {data: "id"},
      {data: "email"},
      {data: "username"},
      {data: "gender"},
      {data: "birth_date"},
      {data: "sns"},
      {data: "phone"},
      {data: "delete_yn"},
      {data: "black_yn"},
      {data: "is_active"},
      {data: "is_staff"},
      {data: "id"},
      {data: "id"},
      {data: "id"}
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
          return data;
        }
      },
      {
        targets: 7,
        visible: true,
        render: function (data) {
          return data;
        }
      },
      {
        targets: 8,
        visible: true,
        render: function (data) {
          return data;
        }
      },
      {
        targets: 9,
        visible: true,
        render: function (data) {
          return data;
        }
      },
      {
        targets: 10,
        visible: true,
        render: function (data) {
          return data;
        }
      },
      {
        targets: 11,
        visible: true,
        orderable: false,
        render: function (data) {
          return '<button onclick="callInnerView('+ data +')" class="btn btn-outline b-primary text-primary">상세</button>';
        }
      },
      {
        targets: 12,
        visible: true,
        orderable: false,
        render: function (data) {
          return '<button onclick="click_service('+ data +')" class="btn btn-outline b-info text-info">서비스</button>';
        }
      },
      {
        targets: 13,
        visible: true,
        orderable: false,
        render: function (data) {
          return '<button onclick="click_session('+ data +')" class="btn btn-outline b-accent text-accent">세션</button>';
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


function click_session(user_seq){
    $.post( "/api_session_read", {
        csrfmiddlewaretoken: csrf_token,
        user_seq: user_seq,
    }).done(function (data) {
        swal.fire({
            title: '사용자 세션 수 변경',
            html:
                '<form class="form-inline" style="margin-top: 20px;">' +
                  '<label class="swal-label"><span class="label-span">현재 사용자 세션</span></label>' +
                  '<input class="swal-control form-control" type="text" value="'+data.result+'" readonly></form>' +
                '</form>'+
                '<form class="form-inline">' +
                  '<label class="swal-label"><span class="label-span">변경할 사용자 세션</span></label>' +
                  '<select class="form-control" id="change_session">'+
                    '<option value="1">1</option>'+
                    '<option value="2">2</option>'+
                  '</select>'+
                '</form>'+
                '<form class="form-inline">' +
                  '<label class="swal-label"><span class="label-span">변경 사유</span></label>' +
                  '<input class="swal-control form-control" type="text" id="change_reason_s">'+
                '</form>',
            confirmButtonText: '수정',
            confirmButtonColor: swalColor('info'),
            cancelButtonText: '취소',
            showCloseButton: true,
            showCancelButton: true,
        }).then((call) => {
          // confirmButton 클릭 시에 조건
          if(call['value'] == true){
              var change_session = $("#change_session").val();
              var change_reason = $("#change_reason_s").val();
              $.post("/api_session_update", {
                  csrfmiddlewaretoken: csrf_token,
                  user_seq: user_seq,
                  change_session: change_session,
                  change_reason: change_reason
              })
              .done(function (data) {
                  if (data.result == '200') {
                      Swal.fire({
                          title: '알림',
                          text: data.msg,
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
                        text: data.msg,
                        type: 'warning',
                        confirmButtonColor: swalColor('warning')
                    })
                    return false;
                  }
              })
          }
        })
    })
}


function click_service(user_seq){
    $.post( "/api_service_read", {
        csrfmiddlewaretoken: csrf_token,
        user_seq: user_seq,
    }).done(function (data) {
        swal.fire({
            title: '서비스 시간 변경',
            html:
                '<form class="form-inline" style="margin-top: 20px;">' +
                '<label class="swal-label"><span class="label-span">현재 사용자 시간</span></label>' +
                '<input class="swal-control form-control" type="text" value="'+data.service_time+'" readonly></form>' +
                '<form class="form-inline">' +
                '<label class="swal-label"><span class="label-span">변경할 사용자 시간</span></label>' +
                '<input class="swal-control form-control" type="text" id="mody_time" value="'+data.service_time+'"></form>'+
                '<form class="form-inline">' +
                '<label class="swal-label"><span class="label-span">변경 사유</span></label>' +
                '<input class="swal-control form-control" type="text" id="change_reason"></form>',
            confirmButtonText: '수정',
            confirmButtonColor: swalColor('info'),
            cancelButtonText: '취소',
            showCloseButton: true,
            showCancelButton: true,
        }).then((call) => {
          // confirmButton 클릭 시에 조건
          if(call['value'] == true){
              var mody_time = $("#mody_time").val();
              var change_reason = $("#change_reason").val();
              $.post("/api_service_update", {
                  csrfmiddlewaretoken: csrf_token,
                  mody_time: mody_time,
                  user_seq: user_seq,
                  change_reason: change_reason
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
                  else if (data.result == '300') {
                      Swal.fire({
                          title: '알림',
                          text: '시간 형식이 맞지 않습니다.',
                          type: 'warning',
                          confirmButtonColor: swalColor('warning')
                      })
                      return 0
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
