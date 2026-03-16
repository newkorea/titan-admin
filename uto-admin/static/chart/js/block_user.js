// 검증 클릭 시
function click_validate(){
    var url = '/api/v1/read/block_user'
    var csrf_token = $('#csrf_token').html();
    var user_list = $('#user_list').val();

    if (user_list === '') {
        $('#user_list').focus();
        return false;
    }

    var param = {
        csrfmiddlewaretoken: csrf_token,
        user_list: user_list
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
                '<tr class="target_user" id="'+value.id+'">'+
                '    <td>'+value.id+'</td>'+
                '    <th>'+value.email+'</th>'+
                '    <td>'+value.regist_date+'</td>'+
                '    <td>'+value.expire_date+'</td>'+
                '    <td>'+value.regist_ip+'</td>'+
                '    <td>'+value.is_active+'</td>'+
                '</tr>'
            $('#add_point').append(html)
        });
    });    
}


// 검증 클릭 시
function click_block(){
    var block_list = []
    for (var i=0; i<$('.target_user').length; i++) {
        block_list.push($('.target_user').eq(i).attr('id'));
    }
    
    var url = '/api/v1/update/block_user'
    var csrf_token = $('#csrf_token').html();
    var param = {
        csrfmiddlewaretoken: csrf_token,
        block_list: block_list
    }
    $.post(url, param)
    .done(function( data ) {
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
    });    
}