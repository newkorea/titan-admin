// 검색필터 날짜 초기화
// $('#filter_regist_start').val(getNow());
// $('#filter_regist_end').val(getTomorrow());

var csrf_token = $('#csrf_token').html();
var datatable = $('#price-inform').DataTable({
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
        url: "/api/v1/read/bank",
        type: "POST",
        dataType: "json",
        data: {
            csrfmiddlewaretoken: csrf_token,
            number: function() { return $('#filter_number').val() },
            email: function() { return $('#filter_email').val() },
            username: function() { return $('#filter_username').val() },
            session: function() { return $('#filter_session').val() },
            month: function() { return $('#filter_month').val() },
            status: function() { return $('#filter_status').val() },
            regist_start: function() { return $('#filter_regist_start').val() },
            regist_end: function() { return $('#filter_regist_end').val() }
        },
    },
    columns: [
        {data: "id"},
        {data: "email"},
        {data: "username"},
        {data: "regist_date"},
        {data: "session"},
        {data: "month_type"},
        {data: "krw"},
        {data: "status"},
        {data: "request_date"},
        {data: "cancel"},
        {data: "cancel_date"},
        {data: "accept"},
        {data: "accept_date"},
        {data: "refund"},
        {data: "refund_date"},
        {data: "type"},
    ],
    columnDefs: [
    	{
            targets: 7,
            visible: true,
            orderable: false,
            render: function (data) {
                var data = data.split('@');
                var status = data[0];
                var id = data[1];
                if (status == 'R') {
                    return '<button class="md-btn md-flat mb-2 w-xs text-primary">요청</button>'
               } else if (status == 'C') {
                    return '<button class="md-btn md-flat mb-2 w-xs">관리자취소</button>'
                } else if (status == 'A') {
                    return '<button class="md-btn md-flat mb-2 w-xs text-success">자동승인</button>'
                } else if (status == 'S') {
                    return '<button class="md-btn md-flat mb-2 w-xs text-success">관리자승인</button>'
                } else if (status == 'Z') {
                    return '<button class="md-btn md-flat mb-2 w-xs text-danger">환불</button>'
	            } else if (status == 'U') {
                    return '<button class="md-btn md-flat mb-2 w-xs">사용자취소</button>'
                }
            }
        },
        {
            targets: 9,
            visible: true,
            orderable: false,
            render: function (data) {
            	if(data == null)
            		return "Cancel Is Null"
                var data = data.split('@');
                var status = data[0];
                var id = data[1];
                var username = data[2];
                var product_name = data[3];
                var krw = data[4];
                if (status == 'R' ){
                    return '<button onclick="call_cancel(\''+id+'\', \''+username+'\', \''+product_name+'\', \''+krw+'\')" class="btn btn-outline b-warning text-warning">취소</button>';
                } else {
                    return '';
                }
            }
        },
        {
            targets: 11,
            visible: true,
            orderable: false,
            render: function (data) {
            	if(data == null)
            		return "Accept Is Null"
                var data = data.split('&');
                var status = data[0];
                var id = data[1];
                var username = data[2];
                var product_name = data[3];
                var krw = data[4];
                var session = data[5];
                var email = data[6];
                var black_status = data[7];
                if (status == 'R' ){
                    return '<button onclick="call_accept(\''+id+'\', \''+username+'\', \''
                    	+product_name+'\', \''+krw+'\', \''+session+'\', \''+email+'\',\''+black_status+'\')" class="btn btn-outline b-success text-success">승인</button>';
                } else {
                    return '';
                }
            }
        },
        {
            targets: 13,
            visible: true,
            orderable: false,
            render: function (data) {
            	if(data == null)
            		return "Refund Is Null"
                var data = data.split('@');
                var status = data[0];
                var id = data[1];
                var username = data[2];
                var product_name = data[3];
                var krw = data[4];
                if (status == 'A' || status == 'S') {
                    return '<button onclick="call_refund(\''+id+'\', \''+username+'\', \''+product_name+'\', \''+krw+'\')" class="btn btn-outline b-danger text-danger">환불</button>';
                } else {
                    return '';
                }
            }
        },
        {
            targets: 15,
            visible: true,
            orderable: false,
            render: function (data) {
                if (data == 'A') {
                    return '알리페이';
                } else if (data == 'W') {
                    return '위쳇페이';
                } else if (data == 'V') {
                    return '가상화폐';
                } else {
                    return '무통장';
                }
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

// 결제 등록
function enroll_ready(){
    var csrf_token = $('#csrf_token').html();
    Swal.fire({
        title: '결제요청 등록',
        html: '' +
              '<div class="form-group tal">'+
              '<label class="fz12">사용자 이메일</label>'+
              '<input id="note_email" type="text" class="form-control" value="">'+
              '</div>'+
              '<div class="form-group tal">'+
              '<label class="fz12">세션</label>'+
              '<select id="note_session" class="form-control">'+
              '  <option value="1">1 세션</option>'+
              '  <option value="2">2 세션</option>'+
              '  <option value="3">3 세션</option>'+
              '  <option value="4">4 세션</option>'+
              '  <option value="5">5 세션</option>'+
              '  <option value="6">6 세션</option>'+
              '</select>'+
              '</div>'+
              '<div class="form-group tal">'+
              '<label class="fz12">개월</label>'+
              '<select id="note_month" class="form-control">'+
              '  <option value="1">1 개월</option>'+
              '  <option value="2">2 개월</option>'+
              '  <option value="3">3 개월</option>'+
              '  <option value="6">6 개월</option>'+
              '  <option value="12">12 개월</option>'+
              '</select>'+
              '</div>'+
              '<div class="form-group tal">'+
              '<label class="fz12">결제방식</label>'+
              '<select id="note_type" class="form-control">'+
              '  <option value="W">위쳇페이</option>'+
			  '  <option value="A">알리페이</option>'+
			  '  <option value="M">무통장</option>'+
  			  '  <option value="V">가상화폐</option>'+
              '</select>'+
              '</div>',
        confirmButtonText: '등록',
        cancelButtonText: "닫기",
        confirmButtonColor: swalColor('base'),
        showCancelButton: true
    }).then(function (result){
        if (result.value) {
            var note_email = $('#note_email').val();
            var note_session = $('#note_session').val();
            var note_month = $('#note_month').val();
            var note_type = $('#note_type').val();
            $.post("/api/v1/create/bank", {
                csrfmiddlewaretoken: csrf_token,
                note_email: note_email,
                note_session: note_session,
                note_month: note_month,
                note_type: note_type
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

// 결제 취소
function call_cancel(id, username, product_name, krw){
    var csrf_token = $('#csrf_token').html();
    Swal.fire({
        title: '결제요청 취소',
        html: '' +
        '<div style="font-size: 12px; margin-top: 10px;">사용자명</div>' +
        '<div style="font-weight: bold; color: red;">'+username+'</div>' +
        '<div style="font-size: 12px; margin-top: 10px;">상품명</div>' +
        '<div style="font-weight: bold; color: red;">'+product_name+'</div>' +
        '<div style="font-size: 12px; margin-top: 10px;">가격</div>' +
        '<div style="font-weight: bold; color: red;">'+krw+'원</div>' +
        '<div style="margin-top: 10px;">결제요청을 취소하시겠습니까?</div>',
        confirmButtonColor: swalColor('warning'),
        showCancelButton: true,
        confirmButtonText: '취소처리',
        cancelButtonText: "닫기"
    }).then(function (result){
        if (result.value) {
            $.post("/api/v1/update/bank", {
                csrfmiddlewaretoken: csrf_token,
                id: id,
                type: 'C'
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

// 결제 승인
function call_accept(id, username, product_name, krw, newsession, email, status){
	if (status == "X") {
		var html = '' +
        '<div style="font-size: 12px; margin-top: 10px;">사용자명</div>' +
        '<div style="font-weight: bold; color: red;">'+username+'</div>' +
        '<div style="font-size: 12px; margin-top: 10px;">상품명</div>' +
        '<div style="font-weight: bold; color: red;">'+product_name+'</div>' +
        '<div style="font-size: 12px; margin-top: 10px;">가격</div>' +
        '<div style="font-weight: bold; color: red;">'+krw+'원</div>' +
        '<div style="margin-top: 10px;color:red;">죄송하지만 지금 사용하시는 지역이 곧 차단될 예정이라<br> 더이상 추가 연장이 불가합니다. </div>';
        
        Swal.fire({
	        title: '연장불가고객',
	        html: html,
	        confirmButtonColor: swalColor('success'),
	        showCancelButton: false,
	        confirmButtonText: '닫기',
	        cancelButtonText: "닫기"
	    }).then(function (result){
	    })
	    	return;
	}
    var csrf_token = $('#csrf_token').html();
    
    $.post("/api/v1/check/session", {
        csrfmiddlewaretoken: csrf_token,
        email: email,
        session: newsession
    })
    .done(function (data) {
    	var html = '' +
	        '<div style="font-size: 12px; margin-top: 10px;">사용자명</div>' +
	        '<div style="font-weight: bold; color: red;">'+username+'</div>' +
	        '<div style="font-size: 12px; margin-top: 10px;">상품명</div>' +
	        '<div style="font-weight: bold; color: red;">'+product_name+'</div>' +
	        '<div style="font-size: 12px; margin-top: 10px;">가격</div>' +
	        '<div style="font-weight: bold; color: red;">'+krw+'원</div>' +
	        '<div style="margin-top: 10px;">결제요청을 승인하시겠습니까?</div>';
        if (data.result == 200) {         
    		 html = '' +
		        '<div style="font-size: 12px; margin-top: 10px;">사용자명</div>' +
		        '<div style="font-weight: bold; color: red;">'+username+'</div>' +
		        '<div style="font-size: 12px; margin-top: 10px;">상품명</div>' +
		        '<div style="font-weight: bold; color: red;">'+product_name+'</div>' +
		        '<div style="font-size: 12px; margin-top: 10px;">가격</div>' +
		        '<div style="font-weight: bold; color: red;">'+krw+'원</div>' +
		        '<div style="margin-top: 10px;">결제요청을 승인하시겠습니까?</div>' +
		        '<div style="margin-top: 10px;color:blue;font-weight: bold;font-size: 16px;">' + 
		     	'원래 '+ data.old_session +' session 인데 '+ newsession + ' session 으로 변경됩니다. 주의해주세요!</div>';
        }
        
        Swal.fire({
	        title: '결제요청 승인',
	        html: html,
	        confirmButtonColor: swalColor('success'),
	        showCancelButton: true,
	        confirmButtonText: '승인처리',
	        cancelButtonText: "닫기"
	    }).then(function (result){
	        if (result.value) {
	            $.post("/api/v1/update/bank", {
	                csrfmiddlewaretoken: csrf_token,
	                id: id,
	                type: 'S'
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
	                      title: data.title,
	                      text: data.text,
	                      type: 'error',
	                      confirmButtonColor: swalColor('error')
	                    })
	                }
	            })
	        }
	    })
    })
}

// 결제 환불
function call_refund(id, username, product_name, krw){
    var csrf_token = $('#csrf_token').html();
    Swal.fire({
        title: '결제 환불',
        html: '' +
        '<div style="font-size: 12px; margin-top: 10px;">사용자명</div>' +
        '<div style="font-weight: bold; color: red;">'+username+'</div>' +
        '<div style="font-size: 12px; margin-top: 10px;">상품명</div>' +
        '<div style="font-weight: bold; color: red;">'+product_name+'</div>' +
        '<div style="font-size: 12px; margin-top: 10px;">가격</div>' +
        '<div style="font-weight: bold; color: red;">'+krw+'원</div>' +
        '<div style="margin-top: 10px;">결제를 환불하시겠습니까?</div>',
        confirmButtonColor: swalColor('error'),
        showCancelButton: true,
        confirmButtonText: '환불처리',
        cancelButtonText: "닫기"
    }).then(function (result){
        if (result.value) {
            $.post("/api/v1/update/bank", {
                csrfmiddlewaretoken: csrf_token,
                id: id,
                type: 'Z'
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

// 처리되지 않은 일감 클릭
function ready_list() {
    $.post("/api/v1/read/ready_data", {
        csrfmiddlewaretoken: csrf_token
    })
    .done(function (data) {
        var ready_list = data.ready_list;
        var total = data.total;
        swal.fire({
            title: '처리되지 않은 일감',
            html: ''+
                  '<div class="form-group tal">'+
                  '<label class="fz12">번호</label>'+
                  '<input type="text" class="form-control" value="' + ready_list + '" readonly>'+
                  '</div>'+
                  '<div class="form-group tal">'+
                  '<label class="fz12">처리되지 않은 일감 수</label>'+
                  '<input type="text" class="form-control" value="' + total + ' 건" readonly>'+
                  '</div>'+
                  '<div">'+
                  '<label class="fz12">담당자님께서는 처리되지 않은 일감이 없도록 처리해주세요!</label>'+
                  '</div>'+
                  '',
            confirmButtonColor: swalColor('base'),
        }).then(function () { /* pass */ });
    });
}

// 검색하기 버튼 클릭
function reload_data(){
    datatable.ajax.reload();
}

// 25-08-25 C U R 삭제버튼
function deleteByStatus(status) {
    // 콘솔에서 바로 확인용
    console.log('deleteByStatus clicked:', status);

    var csrf_token = $('#csrf_token').html();
    var label = (status === 'R') ? '요청'
             : (status === 'C') ? '관리자취소'
             : (status === 'U') ? '사용자취소'
             : status;

    Swal.fire({
        title: label + ' 건 전체삭제',
        html: '<div style="margin-top:8px;">정말로 <b>status=' + status +
              '</b> 인 모든 건을 삭제처리(D)로 변경하시겠습니까?</div>',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: '변경',
        cancelButtonText: '취소',
        confirmButtonColor: swalColor('error')
    }).then(function (result) {
        if (result.value) {
            $.post('/api/v1/delete/by_status', {
                csrfmiddlewaretoken: csrf_token,
                status: status
            })
            .done(function (res) {
                if (res.result === 200) {
                    Swal.fire('완료', res.text, 'success');
                    // 현재 페이지 유지 갱신
                    datatable.ajax.reload(null, false);
                } else {
                    Swal.fire('실패', res.text || '오류가 발생했습니다', 'error');
                }
            })
            .fail(function (xhr) {
                Swal.fire('실패', '서버 통신 중 오류 (' + xhr.status + ')', 'error');
            });
        }
    });
}
