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
        url: "/api/v1/read/user_datatables",
        type: "POST",
        dataType: "json",
        data: {
            csrfmiddlewaretoken: csrf_token,
            id: function() { return $('#filter_id').val() },
            email: function() { return $('#filter_email').val() },
            username: function() { return $('#filter_name').val() },
            delete: function() { return $('#filter_delete').val() },
            active: function() { return $('#filter_active').val() },
            regist_ip: function() { return $('#filter_ip').val() },
            staff: function() { return $('#filter_staff').val() }
        },
    },
    columns: [
        {data: "id"},
        {data: "email"},
        {data: "username"},
        {data: "delete_yn"},
        {data: "is_active"},
        {data: "is_staff"},
        {data: "regist_ip"},
        {data: "regist_date"},
        {data: "id"},
        {data: "id"},
        {data: "id"},
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
            orderable: false,
            render: function (data) {
                return '<button onclick="view_user_detail('+ data +')" class="btn btn-outline b-primary text-primary">정보</button>';
            }
        },
        {
            targets: 9,
            visible: true,
            orderable: false,
            render: function (data) {
                return '<button onclick="manage_service_time('+ data +')" class="btn btn-outline b-info text-info">서비스</button>';
            }
        },
        {
            targets: 10,
            visible: true,
            orderable: false,
            render: function (data) {
                return '<button onclick="manage_session('+ data +')" class="btn btn-outline b-accent text-accent">세션</button>';
            },
        },
        {
            targets: 11,
            visible: true,
            orderable: false,
            render: function (data) {
                return '<button onclick="change_password('+ data +')" class="btn btn-outline b-warning text-warning">비번</button>';
            },
        },
        {
            targets: 12,
            visible: true,
            orderable: false,
            render: function (data) {
                return '<button onclick="change_active('+ data +')" class="btn btn-outline b-success text-success">활성</button>';
            },
        },
        {
            targets: 13,
            visible: true,
            orderable: false,
            render: function (data) {
                return '<button onclick="delete_user('+ data +')" class="btn btn-outline b-danger text-danger">탈퇴</button>';
            },
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

// 정보 버튼 클릭
function view_user_detail(user_id){
    $.post( "/api/v1/read/user_detail", {
        csrfmiddlewaretoken: csrf_token,
        user_id: user_id
    }).done(function (data) {
        var user = data.result;
        swal.fire({
            title: '추가정보',
            html: ''+
                  '<div class="form-group tal">'+
                  '<label class="fz12">번호</label>'+
                  '<input type="text" class="form-control" value="' + user.id + '" readonly>'+
                  '</div>'+
                  '<div class="form-group tal">'+
                  '<label class="fz12">이메일</label>'+
                  '<input type="text" class="form-control" value="' + user.email + '" readonly>'+
                  '</div>'+
                  '<div class="form-group tal">'+
                  '<label class="fz12">본인 추천인 코드</label>'+
                  '<input type="text" class="form-control" value="' + user.rec + '" readonly>'+
                  '</div>'+
                  '<div class="form-group tal">'+
                  '<label class="fz12">가입시 입력한 추천인 코드</label>'+
                  '<input type="text" class="form-control" value="' + user.regist_rec + '" readonly>'+
                  '</div>'+
                  '',
            confirmButtonColor: swalColor('base'),
        }).then(function () { /* pass */ });
    });
}

// 서비스 버튼 클릭
function manage_service_time(user_id){
    $.post( "/api/v1/read/user_service_time", {
        csrfmiddlewaretoken: csrf_token,
        user_id: user_id,
    }).done(function (data) {
        var service_time = data.result;
        swal.fire({
            title: '서비스 시간 변경',
            html: ''+
                  '<div class="form-group tal">'+
                  '<label class="fz12">현재 사용자 시간</label>'+
                  '<input type="text" class="form-control" value="' + service_time + '" readonly>'+
                  '</div>'+
                  '<div class="form-group tal">'+
                  '<label class="fz12">변경할 사용자 시간</label>'+
                  '<input id="change_time" type="text" class="form-control" value="' + service_time + '">'+
                  '</div>'+
                  '<div class="form-group tal">'+
                  '<label class="fz12">변경 사유</label>'+
                  '<input id="change_reason" type="text" class="form-control" value="">'+
                  '</div>',
            confirmButtonText: '수정',
            cancelButtonText: '취소',
            confirmButtonColor: swalColor('base'),
            showCancelButton: true,
        }).then(function (result) {
            if (result.value) {
                var change_time = $("#change_time").val();
                var change_reason = $("#change_reason").val();
                $.post("/api/v1/update/user_service_time", {
                    csrfmiddlewaretoken: csrf_token,
                    change_time: change_time,
                    change_reason: change_reason,
                    user_id: user_id
                }).done(function (data) {
                    if (data.result == 200) {
                        Swal.fire({
                          title: data.title,
                          text: data.text,
                          type: 'success',
                          confirmButtonColor: swalColor('success')
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
        })
    })
}

// 세션 버튼 클릭
function manage_session(user_id){
    $.post( "/api/v1/read/user_session", {
        csrfmiddlewaretoken: csrf_token,
        user_id: user_id
    }).done(function (data) {
        var session = data.result;
        swal.fire({
            title: '세션 변경',
            html: ''+
                  '<div class="form-group tal">'+
                  '<label class="fz12">현재 사용자 세션</label>'+
                  '<input type="text" class="form-control" value="' + session + '" readonly>'+
                  '</div>'+
                  '<div class="form-group tal">'+
                  '<label class="fz12">변경할 사용자 세션</label>'+
                  '<select id="change_session" class="form-control">'+
                    '<option value="1">1</option>'+
                    '<option value="2">2</option>'+
                  '</select>'+
                  '</div>'+
                  '<div class="form-group tal">'+
                  '<label class="fz12">변경 사유</label>'+
                  '<input id="change_reason" type="text" class="form-control" value="">'+
                  '</div>',
                confirmButtonText: '수정',
                cancelButtonText: '취소',
                confirmButtonColor: swalColor('base'),
                showCancelButton: true
          }).then(function (result) {
              if (result.value) {
                  var change_session = $("#change_session").val();
                  var change_reason = $("#change_reason").val();
                  $.post("/api/v1/update/user_session", {
                      csrfmiddlewaretoken: csrf_token,
                      user_id: user_id,
                      change_session: change_session,
                      change_reason: change_reason
                  }).done(function (data) {
                      if (data.result == 200) {
                          Swal.fire({
                            title: data.title,
                            text: data.text,
                            type: 'success',
                            confirmButtonColor: swalColor('success')
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
                  })
              }
          })
    })
}

// 비번 버튼 클릭
function change_password(user_id){
    swal.fire({
        title: '비밀번호 변경',
        html: ''+
              '<div class="form-group tal">'+
              '<label class="fz12">변경할 비밀번호</label>'+
              '<input id="change_password" type="text" class="form-control" value="">'+
              '</div>'+
              '<div class="form-group tal">'+
              '<label class="fz12">변경 사유</label>'+
              '<input id="change_reason" type="text" class="form-control" value="">'+
              '</div>',
            confirmButtonText: '수정',
            cancelButtonText: '취소',
            confirmButtonColor: swalColor('base'),
            showCancelButton: true
      }).then(function (result) {
          if (result.value) {
              var change_password = $("#change_password").val();
              var change_reason = $("#change_reason").val();
              $.post("/api/v1/update/user_password", {
                  csrfmiddlewaretoken: csrf_token,
                  user_id: user_id,
                  change_password: change_password,
                  change_reason: change_reason
              }).done(function (data) {
                  if (data.result == 200) {
                      Swal.fire({
                        title: data.title,
                        text: data.text,
                        type: 'success',
                        confirmButtonColor: swalColor('success')
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
              })
          }
      })
}

// 활성화 버튼 클릭
function change_active(user_id){
    swal.fire({
        title: '활성화 상태 변경',
        html: ''+
              '<div class="form-group tal">'+
              '<label class="fz12">변경할 활성화 상태</label>'+
              '<select id="change_active" class="form-control">'+
                '<option value="1">활성화</option>'+
                '<option value="0">비활성화</option>'+
              '</select>'+
              '</div>'+
              '<div class="form-group tal">'+
              '<label class="fz12">변경 사유</label>'+
              '<input id="change_reason" type="text" class="form-control" value="">'+
              '</div>',
        confirmButtonText: '수정',
        cancelButtonText: '취소',
        confirmButtonColor: swalColor('base'),
        showCancelButton: true
    }).then(function (result) {
        if (result.value) {
            var change_active = $("#change_active").val();
            var change_reason = $("#change_reason").val();
            $.post("/api/v1/update/user_active", {
                csrfmiddlewaretoken: csrf_token,
                user_id: user_id,
                change_active: change_active,
                change_reason: change_reason
            }).done(function (data) {
                if (data.result == 200) {
                    Swal.fire({
                      title: data.title,
                      text: data.text,
                      type: 'success',
                      confirmButtonColor: swalColor('success')
                    })
                    reload_data();
                }
                else {
                    Swal.fire({
                      title: data.title,
                      text: data.text,
                      type: 'error',
                      confirmButtonColor: swalColor('error')
                    })
                }
            })
        }
    })
}

// 탈퇴 버튼 클릭
function delete_user(user_id){
    Swal.fire({
      title: '경고',
      html: '회원 탈퇴 시 다시 되돌릴 수 없습니다<br>정말 계속 하시겠습니까...?'+
      '<div class="form-group tal">'+
      '<label class="fz12">탈퇴 사유</label>'+
      '<input id="change_reason" type="text" class="form-control" value="">'+
      '</div>',
      type: 'error',
      confirmButtonText: '회원탈퇴',
      cancelButtonText: '취소',
      confirmButtonColor: swalColor('error'),
      showCancelButton: true
    }).then(function (result) {
        var change_reason = $("#change_reason").val();
        if (result.value) {
            $.post("/api/v1/delete/user", {
                csrfmiddlewaretoken: csrf_token,
                user_id: user_id,
                change_reason: change_reason
            }).done(function (data) {
                if (data.result == 200) {
                    Swal.fire({
                      title: data.title,
                      text: data.text,
                      type: 'success',
                      confirmButtonColor: swalColor('success')
                    })
                    reload_data();
                }
                else {
                    Swal.fire({
                      title: data.title,
                      text: data.text,
                      type: 'error',
                      confirmButtonColor: swalColor('error')
                    })
                }
            })
        }
    })
}

// 검색하기 버튼 클릭
function reload_data(){
    datatable.ajax.reload();
}
