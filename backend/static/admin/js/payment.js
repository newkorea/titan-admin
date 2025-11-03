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

// 검색하기 버튼 클릭
function reload_data(){
    datatable.ajax.reload();
}
