var csrf_token = $('#csrf_token').html();

$(document).ready( function () {
    $('#event_code').DataTable({
        dom: '<"top"Blf>rtp<"bottom"i>',
        ordering: true,
        info: false,
        filter: false,
        lengthChange: false,
        order: [[0, "desc"]],
        pagingType: "full_numbers",
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
        }
    });
} );

// 룰 삭제하기
function delete_role(seq){
    Swal.fire({
        title: '경고',
        html: '등록된 룰을 삭제하시겠습니까?',
        type: 'error',
        confirmButtonText: '삭제',
        cancelButtonText: '취소',
        confirmButtonColor: swalColor('error'),
        showCancelButton: true
    }).then(function (result) {
        if (result.value) {
            $.post( "api/v1/delete/regist_ban", {
                 csrfmiddlewaretoken: csrf_token,
                 seq: seq
            }).done(function( data ) {
               if (data.result == 200) {
                    Swal.fire({
                        title: data.title,
                        text: data.text,
                        type: 'success',
                        confirmButtonColor: swalColor('success')
                    })
                    location.reload();
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
    })
}

// 룰 추가하기
function add_role(){
    swal.fire({
        title: '차단 룰',
        html: ''+
            '<div class="form-group tal">'+
            '<label class="fz12">차단타입</label>'+
            '<select id="ban_type" class="form-control">'+
            '<option value="DM">도메인</option>'+
            '<option value="IP">아이피</option>'+
            '</select>'+
            '</div>'+
            '<div class="form-group tal">'+
            '<label class="fz12">차단내용</label>'+
            '<input id="ban_content" type="text" class="form-control" placeholder="차단할 내용을 입력하십시오">'+
            '</div>'+
            '<div class="form-group tal">'+
            '<label class="fz12">차단이유</label>'+
            '<input id="ban_reason" type="text" class="form-control" placeholder="차단하는 이유를 입력하십시오">'+
            '</div>',
        confirmButtonText: '추가',
        cancelButtonText: '취소',
        confirmButtonColor: swalColor('base'),
        showCancelButton: true
    }).then(function (result) {
        if (result.value) {
            var ban_type = $("#ban_type").val();
            var ban_content = $("#ban_content").val();
            var ban_reason = $("#ban_reason").val();
            console.log('ban_type = ', ban_type)
            console.log('ban_content = ', ban_content)
            console.log('ban_reason = ', ban_reason)
            $.post( "api/v1/create/regist_ban", {
                 csrfmiddlewaretoken: csrf_token,
                 ban_type: ban_type,
                 ban_content: ban_content,
                 ban_reason: ban_reason
            }).done(function( data ) {
               if (data.result == 200) {
                    Swal.fire({
                        title: data.title,
                        text: data.text,
                        type: 'success',
                        confirmButtonColor: swalColor('success')
                    })
                    location.reload();
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
    })
}

// 이벤트 수정하기
function modify_role(seq){
    $.post( "api/v1/read/regist_ban", {
        csrfmiddlewaretoken: csrf_token,
        seq: seq
    }).done(function( data ) {
        if (data.resCode === 200) {
            var rule = data.resData;
            var type = rule.type;
            var content = rule.content;
            var reason = rule.reason;
            
            if (type === 'DM') {
                var selectBox = '<select id="ban_type" class="form-control">'+
                                    '<option value="DM" selected>도메인</option>'+
                                    '<option value="IP">아이피</option>'+
                                '</select>'
            } else if (type === 'IP') {
                var selectBox = '<select id="ban_type" class="form-control">'+
                                    '<option value="DM">도메인</option>'+
                                    '<option value="IP" selected>아이피</option>'+
                                '</select>'
            }

            swal.fire({
            title: '차단 룰',
            html: ''+
                '<div class="form-group tal">'+
                '<label class="fz12">차단타입</label>'+
                selectBox+
                '</div>'+
                '<div class="form-group tal">'+
                '<label class="fz12">차단내용</label>'+
                '<input value="'+content+'" id="ban_content" type="text" class="form-control" placeholder="차단할 내용을 입력하십시오">'+
                '</div>'+
                '<div class="form-group tal">'+
                '<label class="fz12">차단이유</label>'+
                '<input value="'+reason+'" id="ban_reason" type="text" class="form-control" placeholder="차단하는 이유를 입력하십시오">'+
                '</div>',
            confirmButtonText: '수정',
            cancelButtonText: '취소',
            confirmButtonColor: swalColor('base'),
            showCancelButton: true
            }).then(function (result) {
                if (result.value) {
                    var ban_type = $("#ban_type").val();
                    var ban_content = $("#ban_content").val();
                    var ban_reason = $("#ban_reason").val();
                    $.post( "api/v1/update/regist_ban", {
                        csrfmiddlewaretoken: csrf_token,
                        seq: seq,
                        ban_type: ban_type,
                        ban_content: ban_content,
                        ban_reason: ban_reason
                    }).done(function( data ) {
                    if (data.result == 200) {
                            Swal.fire({
                                title: data.title,
                                text: data.text,
                                type: 'success',
                                confirmButtonColor: swalColor('success')
                            })
                            location.reload();
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
            })
        }
    })
}