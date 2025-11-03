var csrf_token = $('#csrf_token').html();

// Enter 키로도 검색 가능하게 바인딩
$('#filter_host, #filter_telecom').on('keypress', function(e){
  if (e.which === 13) {
    reload_servers();
  }
});
$('#filter_active, #filter_status').on('change', function(){
  reload_servers();
});

var serverDT = $('#server-table').DataTable({
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
  ajax: {
    url: '/api/v1/read/agents',
    type: 'POST',
    dataType: 'json',
    data: function (d) {
      d.csrfmiddlewaretoken = csrf_token;
      d.host = $('#filter_host').val();
      d.telecom = $('#filter_telecom').val();
      d.is_active = $('#filter_active').val();
      d.is_status = $('#filter_status').val();
    }
  },
  columns: [
    { data: 'id' },
    { data: 'name' },
    { data: 'hostdomain' },
    { data: 'hostip' },
    { data: 'telecom' },
    { data: 'protocol' },
    { data: 'is_active' },
    { data: 'is_status' },
    { data: null }
  ],
  columnDefs: [
    {
      targets: 6,
      render: function (data) {
        return (String(data) === '1' || data === 1) ? '<span class="text-success">Y</span>' : '<span class="text-muted">N</span>';
      }
    },
    {
      targets: 7,
      render: function (data) {
        return (String(data) === '1' || data === 1) ? '<span class="text-success">정상</span>' : '<span class="text-danger">중지</span>';
      }
    },
    {
      targets: 8,
      orderable: false,
      render: function (_, __, row) {
        var payload = encodeURIComponent(JSON.stringify(row));
        return '<button class="btn btn-outline b-primary text-primary" onclick="editAgent(\'' + payload + '\')">수정</button>';
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
      previous: '이전',
      next: '다음'
    }
  }
});

function reload_servers(){
  serverDT.ajax.reload();
}

function editAgent(payload) {
  var row = JSON.parse(decodeURIComponent(payload));
  var html = ''+
    '<div class="form-group tal">'+
    '<label class="fz12">이름</label>'+
    '<input id="edit_name" type="text" class="form-control" value="'+(row.name||'')+'">'+
    '</div>'+
    '<div class="form-group tal">'+
    '<label class="fz12">도메인</label>'+
    '<input id="edit_hostdomain" type="text" class="form-control" value="'+(row.hostdomain||'')+'">'+
    '</div>'+
    '<div class="form-group tal">'+
    '<label class="fz12">IP</label>'+
    '<input id="edit_hostip" type="text" class="form-control" value="'+(row.hostip||'')+'">'+
    '</div>'+
    '<div class="form-group tal">'+
    '<label class="fz12">통신사</label>'+
    '<input id="edit_telecom" type="text" class="form-control" value="'+(row.telecom||'')+'">'+
    '</div>'+
    '<div class="form-group tal">'+
    '<label class="fz12">프로토콜</label>'+
    '<input id="edit_protocol" type="text" class="form-control" value="'+(row.protocol||'')+'" placeholder="예: OPENVPN/SSTP/IKEV2">'+
    '</div>'+
    '<div class="form-group tal">'+
    '<label class="fz12">접속계정</label>'+
    '<input id="edit_username" type="text" class="form-control" value="'+(row.username||'')+'">'+
    '</div>'+
    '<div class="form-group tal">'+
    '<label class="fz12">비밀번호</label>'+
    '<input id="edit_password" type="text" class="form-control" value="'+(row.password||'')+'">'+
    '</div>'+
    '<div class="row">'+
    ' <div class="form-group col-sm-6 tal">'+
    '  <label class="fz12">활성화 (1/0)</label>'+
    '  <select id="edit_is_active" class="form-control">'+
    '    <option value="1"'+((String(row.is_active)==='1')?' selected':'')+'>1</option>'+
    '    <option value="0"'+((String(row.is_active)!=='1')?' selected':'')+'>0</option>'+
    '  </select>'+
    ' </div>'+
    ' <div class="form-group col-sm-6 tal">'+
    '  <label class="fz12">상태 (1/0)</label>'+
    '  <select id="edit_is_status" class="form-control">'+
    '    <option value="1"'+((String(row.is_status)==='1')?' selected':'')+'>1</option>'+
    '    <option value="0"'+((String(row.is_status)!=='1')?' selected':'')+'>0</option>'+
    '  </select>'+
    ' </div>'+
    '</div>';

  Swal.fire({
    title: '서버 수정 (#'+row.id+')',
    html: html,
    confirmButtonText: '저장',
    cancelButtonText: '닫기',
    confirmButtonColor: swalColor('base'),
    showCancelButton: true
  }).then(function (result){
    if (result.value) {
      $.post('/api/v1/update/agent', {
        csrfmiddlewaretoken: csrf_token,
        id: row.id,
        name: $('#edit_name').val(),
        hostdomain: $('#edit_hostdomain').val(),
        hostip: $('#edit_hostip').val(),
        telecom: $('#edit_telecom').val(),
        protocol: $('#edit_protocol').val(),
        username: $('#edit_username').val(),
        password: $('#edit_password').val(),
        is_active: $('#edit_is_active').val(),
        is_status: $('#edit_is_status').val()
      }).done(function (data) {
        if (data.result == 200) {
          Swal.fire({
            title: data.title,
            text: data.text,
            type: 'success',
            confirmButtonColor: swalColor('success')
          });
          reload_servers();
        } else {
          Swal.fire({
            title: data.title,
            text: data.text,
            type: 'error',
            confirmButtonColor: swalColor('error')
          });
        }
      }).fail(function () {
        Swal.fire('오류', '서버 통신에 실패했습니다', 'error');
      });
    }
  });
}
