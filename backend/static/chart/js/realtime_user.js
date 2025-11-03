// 검색하기 클릭 시
var csrf_token = '';
function click_search(){
    var url = '/api/v1/read/realtime_user'
    csrf_token = $('#csrf_token').html();
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
                '    <td>'+value.nas_type+'</td>'+
                '<td><button onclick="disconnect(\''+value.acctuniqueid+'\')" class="btn btn-outline b-danger text-danger ml-1">FORCE STOP</button></td>'+
                '</tr>'
            $('#add_point').append(html)
        });
    });    
}

function update_db(acctuniqueid) {
    Swal.fire({
        title: '경고',
        html: "Are you sure to force disconnect<br>Will you continue...?",
        type: 'error',
        confirmButtonText: 'Yes',
        cancelButtonText: 'Cancel',
        confirmButtonColor: swalColor('error'),
        showCancelButton: true
    }).then(function (result) {
        if (result.value) {
            $.post("/api/v1/update/user_status", {
                csrfmiddlewaretoken: csrf_token,
                acctuniqueid: acctuniqueid
            }).done(function (data) {
                if (data.result == 200) {
                    Swal.fire({
                        title: data.title,
                        text: data.text,
                        type: 'success',
                        confirmButtonColor: swalColor('success')
                    })
                    click_search();
                }
                else {
                    Swal.fire({
                        title: data.title,
                        text: data.text,
                        type: 'error',
                        confirmButtonColor: swalColor('error')
                    })
                }
            })
        }
    })
}
	
function disconnect(acctuniqueid) {
    Swal.fire({
        title: '경고',
        html: "Are you sure to force disconnect<br>Will you continue...?",
        type: 'error',
        confirmButtonText: 'Yes',
        cancelButtonText: 'Cancel',
        confirmButtonColor: swalColor('error'),
        showCancelButton: true
    }).then(function (result) {
        if (result.value) {
            $.post("/api/v1/update/user_disconnect", {
                csrfmiddlewaretoken: csrf_token,
                acctuniqueid: acctuniqueid
            }).done(function (data) {
                if (data.result == 200) {
                    Swal.fire({
                        title: data.title,
                        text: data.text,
                        type: 'success',
                        confirmButtonColor: swalColor('success')
                    })
                    click_search();
                }
                else {
                    Swal.fire({
                        title: data.title,
                        text: data.text,
                        type: 'error',
                        confirmButtonColor: swalColor('error')
                    })
                }
            })
        }
    })
}

// 초기화 영역
click_search();
