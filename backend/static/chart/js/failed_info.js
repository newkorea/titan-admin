// 검색필터 날짜 초기화
// $('#filter_regist_start').val(getNow());
// $('#filter_regist_end').val(getTomorrow());

var csrf_token = $('#csrf_token').html();
var datatable = $('#connection-inform').DataTable({
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
        url: "/api/v1/read/failed",
        type: "POST",
        dataType: "json",
        data: {
            csrfmiddlewaretoken: csrf_token,
            number: function() { return $('#filter_number').val() },
            username: function() { return $('#filter_username').val() },
            platform: function() { return $('#filter_platform').val() },
            app_version: function() { return $('#filter_version').val() },            
            server_name: function() { return $('#filter_server_name').val() },
            server_domain: function() { return $('#filter_server_domain').val() },
            server_ip: function() { return $('#filter_server_ip').val() },
            server_protocol: function() { return $('#filter_protocol').val() },
            user_ip: function() { return $('#filter_user_ip').val() },
            user_location: function() { return $('#filter_user_location').val() },
            start_time: function() { return $('#filter_failed_start').val() },
        	end_time: function() { return $('#filter_failed_end').val() }
        },
    },
    columns: [
        {data: "id"},
        {data: "username"},
        {data: "platform"},
        {data: "app_version"},
        {data: "server_name"},
        {data: "server_domain"},
        {data: "server_protocol"},
        {data: "user_ip"},
        {data: "user_location"},
        {data: "device_info"},
        {data: "failed_time"},
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
                return data;
            }
        },
        {
            targets: 7,
            visible: true,
            orderable: false,
            render: function (data) {
                return data;
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
                return data;
            }
        },
        {
            targets: 10,
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


// 검색하기 버튼 클릭
function reload_data(){
    datatable.ajax.reload();
}
