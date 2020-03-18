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
            type: function() { return $('#filter_type').val() },
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
        {data: "regist_date"},
        {data: "reason"}
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
                if(data == '세션 변경' || data == '비밀번호 변경' || data == '활성화 변경' || data == '회원탈퇴'){
                    return data;
                } else {
                    if (data < 0){
                        data = Math.abs(data)
                        var hour = Math.round(data / 60)
                        var minutes = data % 60
                        var time = '-' + hour + '시간 ' + minutes + '분'
                        return time;
                      } else {
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
                return data;
            }
        },
        {
            targets: 8,
            visible: true,
            orderable: false,
            render: function (data) {
                return '<button onclick="view_reason(\'' + data + '\')" type="button" class="btn btn-outline b-primary text-primary">사유</button>';
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

// 사유 버튼 클릭
function view_reason(reason) {
    if (reason == '') {
        reason = '변경 사유가 등록되지 않았습니다';
    }
    swal.fire({
        title: '변경 사유',
        html: reason,
        confirmButtonColor: swalColor('base')
    }).then(function () { /* pass */ });
}

// 검색하기 버튼 클릭
function reload_data(){
    datatable.ajax.reload();
}

$('.datepicker').datepicker({ format: 'yyyy-mm-dd' });
