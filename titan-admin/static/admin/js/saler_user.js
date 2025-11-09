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
        url: "/api/v1/read/saler_user",
        type: "POST",
        dataType: "json",
        data: {
            csrfmiddlewaretoken: csrf_token,
            id: function() { return $('#filter_id').val() },
            email: function() { return $('#filter_email').val() },
            username: function() { return $('#filter_name').val() },
            delete: function() { return $('#filter_delete').val() },
            active: function() { return $('#filter_active').val() },
        },
    },
    columns: [
        {data: "id"},
        {data: "email"},
        {data: "username"},
        {data: "delete_yn"},
        {data: "is_active"}
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
