// 기본 값 설정
var csrf_token = $('#csrf_token').html();
var datatable = $('#use-traffic').DataTable({
    dom: '<"top"Blf>rtp<"bottom"i>',
    paging: true,
    ordering: false,
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
        url: '/api/v1/read/use_traffic',
        type: "POST",
        dataType: "json",
        data: {
            csrfmiddlewaretoken: csrf_token,
        	year: $('#year_selectbox').val(),
    	    month: $('#month_selectbox').val(),
	        day: $('#day_selectbox').val()
        },
    },
    columns: [
        {data: "username"},
        {data: "acctoutputoctets"},
        {data: "acctinputoctets"}
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
            	return data + "GB"
            }
        },
        {
            targets: 2,
            visible: true,
            render: function (data) {
            	return data + "GB"
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

function reload_data(){
    datatable.ajax.reload();
}

//function set_selectbox(){
//  var now = new Date();
//  var year = now.getFullYear();
//  var month = now.getMonth()+1;
//  var day = current_day('day')
//  $("#year_selectbox").val(year);
//  $("#month_selectbox").val(month);
//  $("#day_selectbox").val(day);
//}

// 검색하기 클릭 시
//function click_search(){
//    var url = '/api/v1/read/use_traffic'
//    var csrf_token = $('#csrf_token').html();
//    var year = $('#year_selectbox').val();
//    var month = $('#month_selectbox').val();
//    var day = $('#day_selectbox').val();
//    var param = {
//        csrfmiddlewaretoken: csrf_token,
//        year: year,
//        month: month,
//        day: day
//    }
//    $.post(url, param)
//    .done(function( data ) {
//        $('#add_point').html('');
//        $('#null_txt').hide();
//        var result = data.result
//        if (result.length == 0) {
//            $('#null_txt').show();
//        }
//        $.each(result, function( index, value ) {
//            if (value.acctoutputoctets >= 20) {
//                var html =  ''+
//                '<tr>'+
//                '    <th>'+value.username+'</th>'+
//                '    <td>'+value.acctstarttime+'</td>'+
//                '    <td>'+value.acctstoptime+'</td>'+
//                '    <td>'+value.nasipaddress+'</td>'+
//                '    <td>'+value.callingstationid+'</td>'+
//                '    <td style="color: red">'+value.acctoutputoctets+' GB</td>'+
//                '</tr>'
//            } else if (10 <= value.acctoutputoctets && value.acctoutputoctets < 20) {
//                var html =  ''+
//                '<tr>'+
//                '    <th>'+value.username+'</th>'+
//                '    <td>'+value.acctstarttime+'</td>'+
//                '    <td>'+value.acctstoptime+'</td>'+
//                '    <td>'+value.nasipaddress+'</td>'+
//                '    <td>'+value.callingstationid+'</td>'+
//                '    <td style="color: #dca707">'+value.acctoutputoctets+' GB</td>'+
//                '</tr>'
//            } else if (1 <= value.acctoutputoctets && value.acctoutputoctets < 10) {
//                var html =  ''+
//                '<tr>'+
//                '    <th>'+value.username+'</th>'+
//                '    <td>'+value.acctstarttime+'</td>'+
//                '    <td>'+value.acctstoptime+'</td>'+
//                '    <td>'+value.nasipaddress+'</td>'+
//                '    <td>'+value.callingstationid+'</td>'+
//                '    <td style="color: blue">'+value.acctoutputoctets+' GB</td>'+
//                '</tr>'
//            } else {
//                var html =  ''+
//                '<tr>'+
//                '    <th>'+value.username+'</th>'+
//                '    <td>'+value.acctstarttime+'</td>'+
//                '    <td>'+value.acctstoptime+'</td>'+
//                '    <td>'+value.nasipaddress+'</td>'+
//                '    <td>'+value.callingstationid+'</td>'+
//                '    <td>'+value.acctoutputoctets+' GB</td>'+
//                '</tr>'
//            }
//            
//            $('#add_point').append(html)
//        });
//    });    
//}

// 초기화 영역
//set_selectbox();
