// 검색필터 날짜 초기화
// $('#filter_regist_start').val(getNow());
// $('#filter_regist_end').val(getTomorrow());

var csrf_token = $('#csrf_token').html();
var datatable = $('#reward-inform').DataTable({
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
        url: "/api/v1/read/reward",
        type: "POST",
        dataType: "json",
        data: {
            csrfmiddlewaretoken: csrf_token,
            number: function() { return $('#filter_number').val() },
            refferer_email: function() { return $('#filter_refferer_email').val() },
            register_email: function() { return $('#filter_register_email').val() },
            refferer_name: function() { return $('#filter_refferer_name').val() },
            register_name: function() { return $('#filter_register_name').val() },
            code: function() { return $('#filter_code').val() },
            start_time: function() { return $('#filter_start_time').val() },
            end_time: function() { return $('#filter_end_time').val() }
        },
    },
    columns: [
        {data: "id"},
        {data: "refferer_email"},
        {data: "refferer_name"},
        {data: "event_code"},
        {data: "register_email"},
        {data: "register_username"},
        {data: "reward_days"},
        {data: "type"},
        {data: "register_date"}
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
                return (data / 60) + "시간";
            }
        },
        {
            targets: 7,
            visible: true,
            orderable: false,
            render: function (data) {
            	if (data == 0)
                	return "이벤트";
                else
                	return "추천보상"
            }
        },
        {
            targets: 8,
            visible: true,
            orderable: false,
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
            '  <option value="2">2 개월</option>'+
            '  <option value="3">3 개월</option>'+
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
