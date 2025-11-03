var csrf_token = $('#csrf_token').html();

$(document).ready( function () {
    $('#event_code').DataTable({
        dom: '<"top"Blf>rtp<"bottom"i>',
        ordering: true,
        info: false,
        filter: false,
        lengthChange: false,
        order: [[7, "desc"]],
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

// 이벤트 삭제하기
function delete_event(event_code){
    Swal.fire({
        title: '경고',
        html: '이벤트 코드를 삭제하시겠습니까?',
        type: 'error',
        confirmButtonText: '삭제',
        cancelButtonText: '취소',
        confirmButtonColor: swalColor('error'),
        showCancelButton: true
    }).then(function (result) {
        if (result.value) {
            $.post( "api/v1/delete/event_code", {
                 csrfmiddlewaretoken: csrf_token,
                 event_code: event_code
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

// 이벤트 등록하기
function add_event(){
    swal.fire({
        title: '이벤트 코드',
        html: ''+
              '<div class="form-group tal">'+
              '<label class="fz12">이벤트 코드</label>'+
              '<input id="input_event_code" type="text" class="form-control">'+
              '</div>'+
              '<div class="form-group tal">'+
              '<label class="fz12">적용 시작일시 (yyyy-mm-dd hh:mm:ss)</label>'+
              '<input placeholder="yyyy-mm-dd hh:mm:ss" id="input_event_start" type="text" class="form-control" value="2030-01-01 00:00:00">'+
              '</div>'+
              '<div class="form-group tal">'+
              '<label class="fz12">적용 종료일시 (yyyy-mm-dd hh:mm:ss)</label>'+
              '<input placeholder="yyyy-mm-dd hh:mm:ss" id="input_event_end" type="text" class="form-control" value="2030-01-05 12:00:00">'+
              '</div>'+
              '<div class="form-group tal">'+
              '<label class="fz12">무료체험일</label>'+
              '<input placeholder="숫자만 입력하십시오" id="input_event_free_day" type="number" class="form-control">'+
              '</div>'+
              '<div class="form-group tal">'+
              '<label class="fz12">Reward Percent(%)</label>'+
              '<input placeholder="숫자만 입력하십시오" id="input_event_percent" type="number" class="form-control">'+
              '</div>',
            confirmButtonText: '등록',
            cancelButtonText: '취소',
            confirmButtonColor: swalColor('base'),
            showCancelButton: true
    }).then(function (result) {
        if (result.value) {
            var event_code = $("#input_event_code").val();
            var event_start = $("#input_event_start").val();
            var event_end = $("#input_event_end").val();
            var event_free_day = $("#input_event_free_day").val();
            var event_percent = $("#input_event_percent").val();
	        if(event_percent == '' || 0 > event_percent) {
	        	Swal.fire({
                        title: "알림",
                        text: "Please inpurt correct percentage",
                        type: 'error',
                        confirmButtonColor: swalColor('success')
                    })
	        } else {
	        	$.post( "api/v1/create/event_code", {
	                 csrfmiddlewaretoken: csrf_token,
	                 event_code: event_code,
	                 event_start: event_start,
	                 event_end: event_end,
	                 event_free_day: event_free_day,
	                 event_reward_percent: event_percent
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
        }
    })
}

// 이벤트 수정하기
function modify_event(event_code){
    $.post( "api/v1/read/event_code", {
        csrfmiddlewaretoken: csrf_token,
        event_code: event_code
    }).done(function( data ) {
        if (data.resCode === 200) {
            var event = data.resData;
            var event_code = event.event_code;
            var start = event.start;
            var end = event.end;
            var reward_percent = event.reward_percent;
            var free_day = event.free_day;
            swal.fire({
            title: '이벤트 코드',
            html: ''+
                '<div class="form-group tal">'+
                '<label class="fz12">이벤트 코드</label>'+
                '<input readonly id="input_event_code" type="text" class="form-control" value="'+event_code+'">'+
                '</div>'+
                '<div class="form-group tal">'+
                '<label class="fz12">적용 시작일시 (yyyy-mm-dd hh:mm:ss)</label>'+
                '<input placeholder="yyyy-mm-dd hh:mm:ss" id="input_event_start" type="text" class="form-control" value="'+start+'">'+
                '</div>'+
                '<div class="form-group tal">'+
                '<label class="fz12">적용 종료일시 (yyyy-mm-dd hh:mm:ss)</label>'+
                '<input placeholder="yyyy-mm-dd hh:mm:ss" id="input_event_end" type="text" class="form-control" value="'+end+'">'+
                '</div>'+
                '<div class="form-group tal">'+
                '<label class="fz12">무료체험일</label>'+
                '<input placeholder="숫자만 입력하십시오" id="input_event_free_day" type="number" class="form-control" value="'+free_day+'">'+
                '</div>'+
                '<div class="form-group tal">'+
                '<label class="fz12">Reward Percent(%)</label>'+
                '<input placeholder="숫자만 입력하십시오" id="input_reward_setting" type="number" class="form-control" value="'+reward_percent+'">'+
                '</div>'+
                '<div style="font-size: 14px;">'+
                '* 삭제 된 이벤트를 수정할 경우 복구 처리 됩니다'+
                '</div>',
                confirmButtonText: '수정',
                cancelButtonText: '취소',
                confirmButtonColor: swalColor('base'),
                showCancelButton: true
            }).then(function (result) {
                if (result.value) {
                    var event_code = $("#input_event_code").val();
                    var event_start = $("#input_event_start").val();
                    var event_end = $("#input_event_end").val();
                    var event_free_day = $("#input_event_free_day").val();
                    var event_reward_setting = $("#input_reward_setting").val();
                    console.log('event_code = ', event_code)
                    console.log('event_start = ', event_start)
                    console.log('event_end = ', event_end)
                    console.log('event_free_day = ', event_free_day)
                    if(event_reward_setting == '' || 0 > event_reward_setting) {
				    	Swal.fire({
				                title: "알림",
				                text: "Please inpurt correct percentage",
				                type: 'error',
				                confirmButtonColor: swalColor('success')
				            })
				    } else {
				    	$.post( "api/v1/update/event_code", {
	                        csrfmiddlewaretoken: csrf_token,
	                        event_code: event_code,
	                        event_start: event_start,
	                        event_end: event_end,
	                        event_free_day: event_free_day,
	                        event_reward_setting: event_reward_setting
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
                }
            })
        }
    })
}

function add_default_setting(){
    $.post( "api/v1/read/reward_setting", {
        csrfmiddlewaretoken: csrf_token
    }).done(function( data ) {
        var reward = data.resData;
        var percent = data.resCode == 200?reward.reward_percent:0;
        var id = data.resCode == 200?reward.id:0;
        
        swal.fire({
        title: 'Default Reward Setting',
        html: ''+
            '<div class="form-group tal">'+
            '<label class="fz12">Reward Percent (%)</label>'+
            '<input placeholder="숫자만 입력하십시오" id="input_reward_setting" type="number" class="form-control" value="' + percent + '">'+
            '<input id="input_reward_id" type="hidden" class="form-control" value="'+id+'">'+
            '</div>',
            confirmButtonText: '설정',
            cancelButtonText: '취소',
            confirmButtonColor: swalColor('base'),
            showCancelButton: true
        }).then(function (result) {
            if (result.value) {
                var percent = $("#input_reward_setting").val();
                var reward_id = $("#input_reward_id").val();
                if(percent == '' || 0 > percent) {
			    	Swal.fire({
		                title: "알림",
		                text: "Please inpurt correct percentage",
		                type: 'error',
		                confirmButtonColor: swalColor('success')
		            })
			    } else {
			    	$.post( "api/v1/update/reward_setting", {
	                    csrfmiddlewaretoken: csrf_token,
	                    percent: percent,
	                    reward_id: reward_id
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
            }
        })
    })
}