// 기본 값 설정
function set_selectbox(){
  var now = new Date();
  var year = now.getFullYear();
  var month = now.getMonth()+1;
  $("#year_selectbox").val(year);
  $("#month_selectbox").val(month);
}

// 검색하기 클릭 시
function click_search(){
    var url = '/api/v1/read/use_traffic_monthsum'
    var csrf_token = $('#csrf_token').html();
    var year = $('#year_selectbox').val();
    var month = $('#month_selectbox').val();
    var param = {
        csrfmiddlewaretoken: csrf_token,
        year: year,
        month: month
       
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
            if (value.acctoutputoctets >= 20) {
                var html =  ''+
                '<tr>'+
                '    <th>'+value.username+'</th>'+
                '    <td style="color: red">'+value.acctoutputoctets+' GB</td>'+
                '    <td style="color: red">'+value.acctinputoctets+' GB</td>'+
                '</tr>'
            } else if (10 <= value.acctoutputoctets && value.acctoutputoctets < 20) {
                var html =  ''+
                '<tr>'+
                '    <th>'+value.username+'</th>'+
            '    <td style="color: #dca707">'+value.acctoutputoctets+' GB</td>'+
            '    <td style="color: #dca707">'+value.acctinputoctets+' GB</td>'+
                '</tr>'
            } else if (1 <= value.acctoutputoctets && value.acctoutputoctets < 10) {
                var html =  ''+
                '<tr>'+
                '    <th>'+value.username+'</th>'+
             '    <td style="color: blue">'+value.acctoutputoctets+' GB</td>'+
             '    <td style="color: blue">'+value.acctinputoctets+' GB</td>'+
                '</tr>'
            } else {
                var html =  ''+
                '<tr>'+
                '    <th>'+value.username+'</th>'+
                '    <td>'+value.acctoutputoctets+' GB</td>'+
                '    <td>'+value.acctinputoctets+' GB</td>'+
                '</tr>'
            }
            
            $('#add_point').append(html)
        });
    });    
}

// 초기화 영역
set_selectbox();
click_search();
