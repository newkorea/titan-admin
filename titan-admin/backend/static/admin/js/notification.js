var csrf_token = $('#csrf_token').html();
var datatable = $('#notification-inform').DataTable({
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
        url: "/api/v1/read/get_notifications",
        type: "POST",
        dataType: "json",
        data: {
            csrfmiddlewaretoken: csrf_token,
            platform: function() { return $('#filter_platform').val() },
            start_at: function() { return $('#filter_start').val() },
            end_at: function() { return $('#filter_end').val() },
        },
    },
    columns: [
        {data: "id"},
        {data: "content_ko"},
        {data: "content_en"},
        {data: "content_zh"},
        {data: "platform"},
        {data: "end_date"},
        {data: "user"},
        {data: "id"},
        {data: "id"}
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
            orderable: false,
            render: function (data) {
                return data.substring(0, 50) + "...";
            }
        },
        {
            targets: 2,
            visible: true,
            orderable: false,
            render: function (data) {
                return data.substring(0, 100) + "...";
            }
        },
        {
            targets: 3,
            visible: true,
            orderable: false,
            render: function (data) {
                return data.substring(0, 100) + "...";
            }
        },
        {
            targets: 4,
            visible: true,
            orderable: false,
            render: function (data) {
                return data;
            }
        },
        {
            targets: 5,
            visible: true,
            orderable: false,
            render: function (data) {
                return data;
            }
        },
        {
            targets: 6,
            visible: true,
            orderable: false,
            render: function (data) {
                var data = data.split('@');
                var platform = data[0];
                var id = data[1];
            	if (platform == "User")
            	{
            		return '<button onclick="get_user('+ id +')" class="btn btn-outline b-primary text-accent" style="margin:5px;">목록</button>' + 
            		'<button onclick="add_user('+ id +')" class="btn btn-outline b-accent text-accent" style="margin:5px;">추가</button>';
            	} else 
                 	return "";
            }
        },
        {
            targets: 7,
            visible: true,
            orderable: false,
            render: function (data) {
                return '<button onclick="change_notification('+ data +')" class="btn btn-outline b-success text-success">수정</button>';
            }
        },
        {
            targets: 8,
            visible: true,
            orderable: false,
            render: function (data) {
                return '<button onclick="delete_notification('+ data +')" class="btn btn-outline b-danger text-danger">삭제</button>';
            },
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


function change_notification(notification_id){
	$.post( "/api/v1/read/notification_detail", {
        csrfmiddlewaretoken: csrf_token,
        notification_id: notification_id
    }).done(function (data) {
    	isAll = "";
    	isUser = "";
    	isWindows = "";
    	isMacOS = "";
    	isAndroid = "";
    	isIOS = "";
    	if(data.data.platform == "All")
    		isAll = "selected";
    	else if(data.data.platform == "User") 
    		isUser = "selected";
    	else if(data.data.platform == "Windows") 
    		isWindows = "selected";
    	else if(data.data.platform == "MacOS") 
    		isMacOS = "selected";
    	else if(data.data.platform == "Android") 
    		isAndroid = "selected";
    	else if(data.data.platform == "iOS") 
    		isIOS = "selected";
        swal.fire({
	        title: '알림 변경',
	        html: ''+
	          '<div class="form-group tal">'+
              '<label>플랫폼</label>'+
		      '<select class="form-control" id="platform" name="platform">'+
		        '<option value="All" '+  isAll +'>All</option>'+
		        '<option value="User" '+ isUser +'>User</option>'+
		        '<option value="Windows" '+ isWindows +'>Windows</option>'+
		        '<option value="MacOS" '+ isMacOS +'>MacOS</option>'+
		        '<option value="Android" '+ isAndroid +'>Android</option>'+
		        '<option value="iOS" '+ isIOS +'>iOS</option>'+
		      '</select>'+
              '</div>'+
              '<div class="form-group tal">'+
              '<label class="fz12">알림내용(한국어)</label>'+
              '<input id="end_date" type="date" class="form-control" value="' + data.data.end_date+'"/>'+
              '</div>'+
              '<div class="form-group tal">'+
              '<label class="fz12">알림내용(한국어)</label>'+
              '<textarea id="content_ko" type="text" class="form-control" style="height:100px;">'+ data.data.content_ko+'</textarea>'+
              '</div>'+
              '<div class="form-group tal">'+
              '<label class="fz12">알림내용(영어)</label>'+
              '<textarea id="content_en" type="text" class="form-control" style="height:100px;">'+ data.data.content_en+'</textarea>'+
              '</div>'+
              '<div class="form-group tal">'+
              '<label class="fz12">알림내용(중극어)</label>'+
              '<textarea id="content_zh" type="text" class="form-control" style="height:100px;">'+ data.data.content_zh+'</textarea>'+
              '</div>',
	        confirmButtonText: '수정',
	        cancelButtonText: '취소',
	        confirmButtonColor: swalColor('base'),
	        showCancelButton: true
	    }).then(function (result) {
	        if (result.value) {
	            var app_name = $("#app_name").val();
	            var content_ko = $("#content_ko").val();
	            var content_en = $("#content_en").val();
	            var content_zh = $("#content_zh").val();
	            var platform = $("#platform").val();
	            var end_date = $("#end_date").val();
           		var currentDate = new Date();
            	var endDate = new Date(end_date);
            	
	            if (content_ko == "" || content_en == "" || content_zh == "" || end_date == "") {
	            	return;
	        	} else if (currentDate.getTime() >= endDate.getTime()) {
	        		Swal.fire({
	                  title: '',
	                  text: '종료 날짜를 이전 시간으로 설정할 수 없습니다.',
	                  type: 'error',
	                  confirmButtonColor: swalColor('error')
	                })
	        	} else {
		            $.post("/api/v1/update/notification", {
		                csrfmiddlewaretoken: csrf_token,
		                notification_id: notification_id,
		                content_ko: content_ko,
		                content_en: content_en,
		                content_zh: content_zh,
		                end_date: end_date,
		                platform: platform
		            }).done(function (data) {
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
		                      title: '',
		                      text: '오류',
		                      type: 'error',
		                      confirmButtonColor: swalColor('error')
		                    })
		                }
		            })
		        }
	        }
	    })
    })
}

// 탈퇴 버튼 클릭
function delete_notification(notification_id){
    Swal.fire({
      title: '경고',
      html: '삭제시 다시 되돌릴 수 없습니다<br>정말 계속 하시겠습니까...?'+
      '<div class="form-group tal">'+
      '</div>',
      type: 'error',
      confirmButtonText: '삭제',
      cancelButtonText: '취소',
      confirmButtonColor: swalColor('error'),
      showCancelButton: true
    }).then(function (result) {
        if (result.value) {
            $.post("/api/v1/delete/notification", {
                csrfmiddlewaretoken: csrf_token,
                notification_id: notification_id,
            }).done(function (data) {
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
            })
        }
    })
}
function add_notification(){
    var csrf_token = $('#csrf_token').html();
    Swal.fire({
        title: '알림 추가',
        html: '' +
              '<div class="form-group tal">'+
              '<label>플랫폼</label>'+
		      '<select class="form-control" id="platform" name="platform">'+
		        '<option value="All">All</option>'+
		        '<option value="User">User</option>'+
		        '<option value="Windows">Windows</option>'+
		        '<option value="MacOS">MacOS</option>'+
		        '<option value="Android">Android</option>'+
		        '<option value="iOS">iOS</option>'+
		      '</select>'+
              '</div>'+
              '<div class="form-group tal">'+
              '<label class="fz12">종료 날짜</label>'+
              '<input id="end_date" type="date" class="form-control"/>'+
              '</div>'+
              '<div class="form-group tal">'+
              '<label class="fz12">알림내용(한국어)</label>'+
              '<textarea id="content_ko" type="text" class="form-control" style="height:100px;" required></textarea>'+
              '</div>'+
              '<div class="form-group tal">'+
              '<label class="fz12">알림내용(영어)</label>'+
              '<textarea id="content_en" type="text" class="form-control" style="height:100px;" required></textarea>'+
              '</div>'+
              '<div class="form-group tal">'+
              '<label class="fz12">알림내용(중극어)</label>'+
              '<textarea id="content_zh" type="text" class="form-control" style="height:100px;" required></textarea>'+
              '</div>',
        confirmButtonText: '등록',
        cancelButtonText: "닫기",
        confirmButtonColor: swalColor('base'),
        showCancelButton: true
    }).then(function (result){
        if (result.value) {
            var content_ko = $('#content_ko').val();
            var content_en = $('#content_en').val();
            var content_zh = $('#content_zh').val();
            var end_date = $('#end_date').val();
            var platform = $('#platform').val();
            var currentDate = new Date();
            var endDate = new Date(end_date);
            if (content_ko == "" || content_en == "" || content_zh == "" || end_date == "") {
            	return;
        	} else if (currentDate.getTime() >= endDate.getTime()) {
        		Swal.fire({
                  title: '',
                  text: '종료 날짜를 이전 시간으로 설정할 수 없습니다.',
                  type: 'error',
                  confirmButtonColor: swalColor('error')
                })
        	} else {
	            $.post("/api/v1/create/notification", {
	                csrfmiddlewaretoken: csrf_token,
	                content_ko: content_ko,
	                content_en: content_en,
	                content_zh: content_zh,
	                end_date: end_date,
	                platform: platform
	            })
	            .done(function (data) {
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
	                      title: '',
	                      text: '등록된 알림입니다.',
	                      type: 'error',
	                      confirmButtonColor: swalColor('error')
	                    })
	                }
	            })
        	}
        }
    })
}
function add_user(notification_id){
    var csrf_token = $('#csrf_token').html();
    Swal.fire({
        title: '사용자 추가',
        html: '' +
              '<div class="form-group tal">'+
              '<label class="fz12">이메일</label>'+
              '<input id="email" type="text" class="form-control" />'+
              '</div>',
        confirmButtonText: '추가',
        cancelButtonText: "닫기",
        confirmButtonColor: swalColor('base'),
        showCancelButton: true
    }).then(function (result){
        if (result.value) {
            var email = $('#email').val();
            if (email == "") {
            	return;
        	} else {
	            $.post("/api/v1/create/add_user", {
	                csrfmiddlewaretoken: csrf_token,
	                notification_id: notification_id,
	                email: email
	            })
	            .done(function (data) {
	                if (data.result == 200) {
	                    Swal.fire({
	                      title: data.title,
	                      text: data.text,
	                      type: 'success',
	                      confirmButtonColor: swalColor('success')
	                    })
	                    reload_data();
	                } else if(data.result == 400) {	                	
	                    Swal.fire({
	                      title: '',
	                      text: '이 이메일이 추가되었습니다.',
	                      type: 'error',
	                      confirmButtonColor: swalColor('error')
	                    })
	                } else if(data.result == 600) {	                	
	                    Swal.fire({
	                      title: '',
	                      text: '이메일이 존재하지 않습니다.',
	                      type: 'error',
	                      confirmButtonColor: swalColor('error')
	                    })
	                } else {
	                    Swal.fire({
	                      title: '',
	                      text: '오류가 발생하였습니다.',
	                      type: 'error',
	                      confirmButtonColor: swalColor('error')
	                    })
	                }
	            })
        	}
        }
    })
}
function get_user(notification_id){
    var csrf_token = $('#csrf_token').html();
    $.post("/api/v1/read/get_user", {
        csrfmiddlewaretoken: csrf_token,
        notification_id: notification_id
    })
    .done(function (data) {
        var result = data.data;
        var html_template = '';
        $.each(result, function( index, value) {
            var email = value.email;
            html_template += '<div>' + email + '</div>'
        });
        swal.fire({
            title: '이메일 목록',
            html: ''+ html_template + '',
            confirmButtonColor: swalColor('base'),
        }).then(function () { /* pass */ });
    })
}
// 검색하기 버튼 클릭
function reload_data(){
    datatable.ajax.reload();
}
