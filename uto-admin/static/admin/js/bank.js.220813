// 검색필터 날짜 초기화
// $('#filter_regist_start').val(getNow());
// $('#filter_regist_end').val(getTomorrow());

var csrf_token = $('#csrf_token').html();
var datatable = $('#price-inform').DataTable({
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
        url: "/api/v1/read/bank",
        type: "POST",
        dataType: "json",
        data: {
            csrfmiddlewaretoken: csrf_token,
            number: function() { return $('#filter_number').val() },
            email: function() { return $('#filter_email').val() },
            username: function() { return $('#filter_username').val() },
            session: function() { return $('#filter_session').val() },
            month: function() { return $('#filter_month').val() },
            status: function() { return $('#filter_status').val() },
            regist_start: function() { return $('#filter_regist_start').val() },
            regist_end: function() { return $('#filter_regist_end').val() }
        },
    },
    columns: [
        {data: "id"},
        {data: "email"},
        {data: "username"},
        {data: "session"},
        {data: "month_type"},
        {data: "krw"},
        {data: "status"},
        {data: "cancel"},
        {data: "cancel_date"},
        {data: "accept"},
        {data: "accept_date"},
        {data: "refund"},
        {data: "refund_date"},
        {data: "type"},
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
            orderable: false,
            render: function (data) {
                var data = data.split('@');
                var status = data[0];
                var id = data[1];
                if (status == 'R') {
                    return '<button class="md-btn md-flat mb-2 w-xs text-primary">대기</button>'
                } else if (status == 'C') {
                    return '<button class="md-btn md-flat mb-2 w-xs">취소</button>'
                } else if (status == 'A') {
                    return '<button class="md-btn md-flat mb-2 w-xs text-success">승인</button>'
                } else if (status == 'Z') {
                    return '<button class="md-btn md-flat mb-2 w-xs text-danger">환불</button>'
                }
            }
        },
        {
            targets: 7,
            visible: true,
            orderable: false,
            render: function (data) {
                var data = data.split('@');
                var status = data[0];
                var id = data[1];
                var username = data[2];
                var product_name = data[3];
                var krw = data[4];
                if (status == 'R') {
                    return '<button onclick="call_cancel(\''+id+'\', \''+username+'\', \''+product_name+'\', \''+krw+'\')" class="btn btn-outline b-warning text-warning">취소</button>';
                } else {
                    return '';
                }
            }
        },
        {
            targets: 8,
            visible: true,
            orderable: false,
            render: function (data) {
                return data;
            }
        },
        {
            targets: 9,
            visible: true,
            orderable: false,
            render: function (data) {
                var data = data.split('@');
                var status = data[0];
                var id = data[1];
                var username = data[2];
                var product_name = data[3];
                var krw = data[4];
                if (status == 'R') {
                    return '<button onclick="call_accept(\''+id+'\', \''+username+'\', \''+product_name+'\', \''+krw+'\')" class="btn btn-outline b-success text-success">승인</button>';
                } else {
                    return '';
                }
            }
        },
        {
            targets: 10,
            visible: true,
            orderable: false,
            render: function (data) {
                return data;
            }
        },
        {
            targets: 11,
            visible: true,
            orderable: false,
            render: function (data) {
                var data = data.split('@');
                var status = data[0];
                var id = data[1];
                var username = data[2];
                var product_name = data[3];
                var krw = data[4];
                if (status == 'A') {
                    return '<button onclick="call_refund(\''+id+'\', \''+username+'\', \''+product_name+'\', \''+krw+'\')" class="btn btn-outline b-danger text-danger">환불</button>';
                } else {
                    return '';
                }
            }
        },
        {
            targets: 12,
            visible: true,
            orderable: false,
            render: function (data) {
                return data;
            }
        },
        {
            targets: 13,
            visible: true,
            orderable: false,
            render: function (data) {
                if (data == 'M') {
                    return '무통장';
                } else if (data == 'W') {
                    return '위쳇페이';
                } else {
                    return '';
                }
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

// 결제 등록
function enroll_ready(){
    var csrf_token = $('#csrf_token').html();
    Swal.fire({
        title: '결제요청 등록',
        html: '' +
              '<div class="form-group tal">'+
              '<label class="fz12">사용자 이메일</label>'+
              '<input id="note_email" type="text" class="form-control" value="">'+
              '</div>'+
              '<div class="form-group tal">'+
              '<label class="fz12">세션</label>'+
              '<select id="note_session" class="form-control">'+
              '  <option value="1">1 세션</option>'+
              '  <option value="2">2 세션</option>'+
              '</select>'+
              '</div>'+
              '<div class="form-group tal">'+
              '<label class="fz12">개월</label>'+
              '<select id="note_month" class="form-control">'+
              '  <option value="1">1 개월</option>'+
              '  <option value="6">6 개월</option>'+
              '  <option value="12">12 개월</option>'+
              '</select>'+
              '</div>'+
              '<div class="form-group tal">'+
              '<label class="fz12">결제방식</label>'+
              '<select id="note_type" class="form-control">'+
              '  <option value="M">무통장</option>'+
              '  <option value="W">위쳇페이</option>'+
              '</select>'+
              '</div>',
        confirmButtonText: '등록',
        cancelButtonText: "닫기",
        confirmButtonColor: swalColor('base'),
        showCancelButton: true
    }).then(function (result){
        if (result.value) {
            var note_email = $('#note_email').val();
            var note_session = $('#note_session').val();
            var note_month = $('#note_month').val();
            var note_type = $('#note_type').val();
            $.post("/api/v1/create/bank", {
                csrfmiddlewaretoken: csrf_token,
                note_email: note_email,
                note_session: note_session,
                note_month: note_month,
                note_type: note_type
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

// 결제 취소
function call_cancel(id, username, product_name, krw){
    var csrf_token = $('#csrf_token').html();
    Swal.fire({
        title: '결제요청 취소',
        html: '' +
        '<div style="font-size: 12px; margin-top: 10px;">사용자명</div>' +
        '<div style="font-weight: bold; color: red;">'+username+'</div>' +
        '<div style="font-size: 12px; margin-top: 10px;">상품명</div>' +
        '<div style="font-weight: bold; color: red;">'+product_name+'</div>' +
        '<div style="font-size: 12px; margin-top: 10px;">가격</div>' +
        '<div style="font-weight: bold; color: red;">'+krw+'원</div>' +
        '<div style="margin-top: 10px;">결제요청을 취소하시겠습니까?</div>',
        confirmButtonColor: swalColor('warning'),
        showCancelButton: true,
        confirmButtonText: '취소처리',
        cancelButtonText: "닫기"
    }).then(function (result){
        if (result.value) {
            $.post("/api/v1/update/bank", {
                csrfmiddlewaretoken: csrf_token,
                id: id,
                type: 'C'
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

// 결제 승인
function call_accept(id, username, product_name, krw){
    var csrf_token = $('#csrf_token').html();
    Swal.fire({
        title: '결제요청 승인',
        html: '' +
        '<div style="font-size: 12px; margin-top: 10px;">사용자명</div>' +
        '<div style="font-weight: bold; color: red;">'+username+'</div>' +
        '<div style="font-size: 12px; margin-top: 10px;">상품명</div>' +
        '<div style="font-weight: bold; color: red;">'+product_name+'</div>' +
        '<div style="font-size: 12px; margin-top: 10px;">가격</div>' +
        '<div style="font-weight: bold; color: red;">'+krw+'원</div>' +
        '<div style="margin-top: 10px;">결제요청을 승인하시겠습니까?</div>',
        confirmButtonColor: swalColor('success'),
        showCancelButton: true,
        confirmButtonText: '승인처리',
        cancelButtonText: "닫기"
    }).then(function (result){
        if (result.value) {
            $.post("/api/v1/update/bank", {
                csrfmiddlewaretoken: csrf_token,
                id: id,
                type: 'A'
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

// 결제 환불
function call_refund(id, username, product_name, krw){
    var csrf_token = $('#csrf_token').html();
    Swal.fire({
        title: '결제 환불',
        html: '' +
        '<div style="font-size: 12px; margin-top: 10px;">사용자명</div>' +
        '<div style="font-weight: bold; color: red;">'+username+'</div>' +
        '<div style="font-size: 12px; margin-top: 10px;">상품명</div>' +
        '<div style="font-weight: bold; color: red;">'+product_name+'</div>' +
        '<div style="font-size: 12px; margin-top: 10px;">가격</div>' +
        '<div style="font-weight: bold; color: red;">'+krw+'원</div>' +
        '<div style="margin-top: 10px;">결제를 환불하시겠습니까?</div>',
        confirmButtonColor: swalColor('error'),
        showCancelButton: true,
        confirmButtonText: '환불처리',
        cancelButtonText: "닫기"
    }).then(function (result){
        if (result.value) {
            $.post("/api/v1/update/bank", {
                csrfmiddlewaretoken: csrf_token,
                id: id,
                type: 'Z'
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

// 처리되지 않은 일감 클릭
function ready_list() {
    $.post("/api/v1/read/ready_data", {
        csrfmiddlewaretoken: csrf_token
    })
    .done(function (data) {
        var ready_list = data.ready_list;
        var total = data.total;
        swal.fire({
            title: '처리되지 않은 일감',
            html: ''+
                  '<div class="form-group tal">'+
                  '<label class="fz12">번호</label>'+
                  '<input type="text" class="form-control" value="' + ready_list + '" readonly>'+
                  '</div>'+
                  '<div class="form-group tal">'+
                  '<label class="fz12">처리되지 않은 일감 수</label>'+
                  '<input type="text" class="form-control" value="' + total + ' 건" readonly>'+
                  '</div>'+
                  '<div">'+
                  '<label class="fz12">담당자님께서는 처리되지 않은 일감이 없도록 처리해주세요!</label>'+
                  '</div>'+
                  '',
            confirmButtonColor: swalColor('base'),
        }).then(function () { /* pass */ });
    });
}

// 검색하기 버튼 클릭
function reload_data(){
    datatable.ajax.reload();
}
