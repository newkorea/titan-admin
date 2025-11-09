// 검색하기 클릭 시
function click_search(){
    var url = '/api/v1/read/abuse_user'
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
                '    <th>'+value.row+'</th>'+
                '    <td>'+value.regist_ip+'</td>'+
                '    <td>'+value.cnt+'</td>'+
                '    <td>'+
                '      <button onclick="abuse_detail(&#39;'+value.regist_ip+'&#39;)" class="btn btn-outline b-accent text-accent">이메일 목록</button>'+
                '    </td>'+
                '</tr>'
            $('#add_point').append(html)
        });
    });    
}


function abuse_detail(input_ip) {
    var csrf_token = $('#csrf_token').html();
    $.post( "/api/v1/read/abuse_user_detail", {
        csrfmiddlewaretoken: csrf_token,
        input_ip: input_ip
    }).done(function (data) {
        var result = data.result;
        var html_template = '';
        $.each(result, function( index, value) {
            var email = value.email;
            html_template += '<div>' + email + '</div>'
        });
        swal.fire({
            title: '추가정보',
            html: ''+ html_template + '',
            confirmButtonColor: swalColor('base'),
        }).then(function () { /* pass */ });
    });
}


click_search();