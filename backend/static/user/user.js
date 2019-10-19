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
          return '<button onclick="callInnerView('+ data +')" class="btn btn-fw warn">상세</button>';
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
