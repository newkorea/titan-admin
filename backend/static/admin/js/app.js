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
        url: "/api/v1/read/app_datatables",
        type: "POST",
        dataType: "json",
        data: {
            csrfmiddlewaretoken: csrf_token
        },
    },
    columns: [
        {data: "id"},
        {data: "app_name"},
        {data: "package_name"},
        {data: "created_at"},
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
            orderable: false,
            render: function (data) {
                return '<button onclick="change_app('+ data +')" class="btn btn-outline b-success text-success">수정</button>';
            },
        },
        {
            targets: 5,
            visible: true,
            orderable: false,
            render: function (data) {
                return '<button onclick="delete_app('+ data +')" class="btn btn-outline b-danger text-danger">삭제</button>';
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


function change_app(app_id){
	$.post( "/api/v1/read/app_detail", {
        csrfmiddlewaretoken: csrf_token,
        app_id: app_id,
    }).done(function (data) {
        swal.fire({
	        title: '차단앱 변경',
	        html: ''+
	              '<div class="form-group tal">'+
	              '<label class="fz12">앱 이름</label>'+
	              '<input type="text" id="app_name" class="form-control" value="' + data.data.app_name + '">'+
	              '</div>'+
	              '<div class="form-group tal">'+
	              '<label class="fz12">패키지 이름</label>'+
	              '<input id="package_name" type="text" class="form-control" value="' + data.data.package_name + '">'+
	              '</div>',
	        confirmButtonText: '수정',
	        cancelButtonText: '취소',
	        confirmButtonColor: swalColor('base'),
	        showCancelButton: true
	    }).then(function (result) {
	        if (result.value) {
	            var app_name = $("#app_name").val();
	            var package_name = $("#package_name").val();
	            $.post("/api/v1/update/app", {
	                csrfmiddlewaretoken: csrf_token,
	                app_id: app_id,
	                app_name: app_name,
	                package_name: package_name
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
	                      title: '',
	                      text: '등록된 패키지 이름입니다.',
	                      type: 'error',
	                      confirmButtonColor: swalColor('error')
	                    })
	                }
	            })
	        }
	    })
    })
}

// 탈퇴 버튼 클릭
function delete_app(app_id){
    Swal.fire({
      title: '경고',
      html: '앱삭제시 다시 되돌릴 수 없습니다<br>정말 계속 하시겠습니까...?'+
      '<div class="form-group tal">'+
      '</div>',
      type: 'error',
      confirmButtonText: '삭제',
      cancelButtonText: '취소',
      confirmButtonColor: swalColor('error'),
      showCancelButton: true
    }).then(function (result) {
        if (result.value) {
            $.post("/api/v1/delete/app", {
                csrfmiddlewaretoken: csrf_token,
                app_id: app_id,
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
function add_app(){
    var csrf_token = $('#csrf_token').html();
    Swal.fire({
        title: '차단앱 추가',
        html: '' +
              '<div class="form-group tal">'+
              '<label class="fz12">앱 이름</label>'+
              '<input id="app_name" type="text" class="form-control" value="">'+
              '</div>'+
              '<div class="form-group tal">'+
              '<label class="fz12">패키지 이름</label>'+
              '<input id="package_name" type="text" class="form-control" value="">'+
              '</div>',
        confirmButtonText: '등록',
        cancelButtonText: "닫기",
        confirmButtonColor: swalColor('base'),
        showCancelButton: true
    }).then(function (result){
        if (result.value) {
            var app_name = $('#app_name').val();
            var package_name = $('#package_name').val();
            $.post("/api/v1/create/app", {
                csrfmiddlewaretoken: csrf_token,
                app_name: app_name,
                package_name: package_name
            })
            .done(function (data) {
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
                      title: '',
                      text: '등록된 패키지 이름입니다.',
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
