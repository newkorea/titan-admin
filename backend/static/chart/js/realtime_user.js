// 검색하기 클릭 시
function click_search(){
    var url = '/api/v1/read/realtime_user'
    var csrf_token = $('#csrf_token').html();
    var param = {
        csrfmiddlewaretoken: csrf_token
    }
    $.post(url, param)
    .done(function( data ) {
        $('#add_point').html('');
        $('#null_txt').hide();
        var result = data.result
        if (result.length == 0) {
            $('#null_txt').show();
        }
        $.each(result, function( index, value ) {
            var html =  ''+
                '<tr>'+
                '    <td>'+value.sessionid+'</td>'+
                '    <th>'+value.email+'</th>'+
                '    <td>'+value.agent_ip+'</td>'+
                '    <td>'+value.starttime+'</td>'+
                '    <td>'+value.client_ip+'</td>'+
                '    <td>'+value.private_ip+'</td>'+
                '</tr>'
            $('#add_point').append(html)
        });
    });    
}

// 초기화 영역
click_search();
