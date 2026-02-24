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
        url: "api/v1/read/payment",
        type: "POST",
        dataType: "json",
        data: {
            csrfmiddlewaretoken: csrf_token,
            email: function() { return $('#filter_email').val() },
            session: function() { return $('#filter_session').val() },
            month: function() { return $('#filter_month').val() },
            refund: function() { return $('#filter_refund').val() },
            type: function() { return $('#filter_type').val() },
            regist_start: function() { return $('#filter_regist_start').val() },
            regist_end: function() { return $('#filter_regist_end').val() }
        },
    },
    columns: [
        {data: "id"},
        {data: "tid"},
        {data: "pgcode"},
        {data: "product_name"},
        {data: "krw"},
        {data: "usd"},
        {data: "cny"},
        {data: "email"},
        {data: "refund_yn"},
        {data: "regist_date"},
        {data: "refund_date"},
        {data: "refund"},
        {data: "receipt"},
        {data: "receipt_send"},
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
                var id = data.split('+')[0]
                var refund_yn = data.split('+')[1]
                var pgcode = data.split('+')[2]
                if (refund_yn == 'Y' || pgcode == 'apple') {
                    return ''
                } else {
                    return '<button onclick="click_refund('+id+')" type="button" class="btn btn-dark">환불</button>';
                }
            }
        },
        {
            targets: 12,
            visible: true,
            orderable: false,
            render: function (data) {
                var tid = data;
                if (!tid || tid.toString().trim() === '') {
                    return '-';
                }
                return '<button onclick="click_receipt(\'' + tid + '\')" type="button" class="btn btn-info btn-sm">보기</button>';
            }
        },
        {
            targets: 13,
            visible: true,
            orderable: false,
            render: function (data) {
                var parts = data.split('+');
                var tid = parts[0];
                var email = parts[1];
                if (!tid || tid.toString().trim() === '') {
                    return '-';
                }
                return '<button onclick="click_send_receipt(\'' + tid + '\', \'' + email + '\')" type="button" class="btn btn-success btn-sm">발송</button>';
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

// 환불
function click_refund(id){
    var csrf_token = $('#csrf_token').html();
    $.post( "/api/v1/update/refund", {
        csrfmiddlewaretoken: csrf_token,
        id: id
    }).done(function( data ) {
        if (data.result == 200) {
            Swal.fire({
                title: data.title,
                text: data.text,
                type: 'success',
                confirmButtonColor: swalColor('success')
            }).then(function (result) {
                reload_data();
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

// 영수증 보기 (페이레터 API)
function click_receipt(tid) {
    if (!tid || tid.trim() === '') {
        Swal.fire({ title: '오류', text: '트랜잭션 ID가 없습니다.', type: 'warning', confirmButtonColor: swalColor('warning') });
        return;
    }
    var csrf_token = $('#csrf_token').html();
    $.post('/api/v1/read/receipt', {
        csrfmiddlewaretoken: csrf_token,
        tid: tid
    }).done(function(data) {
        if (data.result == 200 && data.receipt_url) {
            window.open(data.receipt_url, '영수증', 'width=800,height=600');
        } else {
            Swal.fire({ title: '오류', text: data.text || '영수증을 가져올 수 없습니다.', type: 'error', confirmButtonColor: swalColor('error') });
        }
    }).fail(function() {
        Swal.fire({ title: '오류', text: 'API 요청 실패', type: 'error', confirmButtonColor: swalColor('error') });
    });
}

// 영수증 이메일 발송
function click_send_receipt(tid, email) {
    if (!tid || tid.trim() === '') {
        Swal.fire({ title: '오류', text: '트랜잭션 ID가 없습니다.', type: 'warning', confirmButtonColor: swalColor('warning') });
        return;
    }
    Swal.fire({
        title: '영수증 발송',
        text: email + ' 로 영수증을 발송하시겠습니까?',
        type: 'question',
        showCancelButton: true,
        confirmButtonColor: swalColor('success'),
        cancelButtonColor: swalColor('error'),
        confirmButtonText: '발송',
        cancelButtonText: '취소'
    }).then(function(result) {
        if (result.value) {
            var csrf_token = $('#csrf_token').html();
            $.post('/api/v1/send/receipt_email', {
                csrfmiddlewaretoken: csrf_token,
                tid: tid,
                email: email
            }).done(function(data) {
                if (data.result == 200) {
                    Swal.fire({ title: data.title, text: data.text, type: 'success', confirmButtonColor: swalColor('success') });
                } else {
                    Swal.fire({ title: data.title, text: data.text, type: 'error', confirmButtonColor: swalColor('error') });
                }
            }).fail(function() {
                Swal.fire({ title: '오류', text: '이메일 발송 요청 실패', type: 'error', confirmButtonColor: swalColor('error') });
            });
        }
    });
}

// 검색하기 버튼 클릭
function reload_data(){
    datatable.ajax.reload();
}
