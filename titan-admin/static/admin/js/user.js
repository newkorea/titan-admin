var csrf_token = $('#csrf_token').html();
getUserCount();
var datatable = $('#user-inform').DataTable({
    dom: '<"top"Blf>rtp<"bottom"i>',
    paging: true,
    ordering: true,
    info: false,
    filter: false,
    lengthChange: false,
    order: [[0, "desc"]],
    stateSave: false,
    stateLoadCallback: function() { return null; },
    pagingType: "full_numbers",
    scrollX: false,
    scrollCollapse: false,
    processing: true,
    serverSide: true,
    drawCallback: function () {},
    createdRow: function (row, data) {
        if (data.is_expired == 1) {
            $(row).addClass('row-expired');
        }
    },
    ajax: {
        url: "/api/v1/read/user_datatables",
        type: "POST",
        dataType: "json",
        data: {
            csrfmiddlewaretoken: csrf_token,
            id: function() { return $('#filter_id').val() },
            email: function() { return $('#filter_email').val() },
            username: function() { return $('#filter_name').val() },
            delete: function() { return $('#filter_delete').val() },
            active: function() { return $('#filter_active').val() },
            regist_ip: function() { return $('#filter_ip').val() },
            staff: function() { return $('#filter_staff').val() }
        },
    },
    columns: [
        {data: "id"},
        {data: "email"},
        {data: "username"},
        {data: "delete_yn"},
        {data: "is_active"},
        {data: "black_yn"},
        {data: "is_staff"},
        {data: "regist_ip"},
        {data: "regist_date"},
        {data: "id"},
        {data: "id"},
        {data: "id"},
        {data: "id"},
        {data: "id"},
        {data: "id"},
        {data: "id"},
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
            render: function (data) {
                return data;
            }
        },
        {
            targets: 2,
            visible: true,
            render: function (data) {
                return data;
            }
        },
        {
            targets: 3,
            visible: true,
            render: function (data) {
                return data;
            }
        },
        {
            targets: 4,
            visible: true,
            render: function (data) {
                return data;
            }
        },
        {
            targets: 5,
            visible: true,
            render: function (data) {
            	if(data == "Y") {
            		return "차단"
            	} else if(data == "X") {
            		return "연장불가"
            	} else {
                	return "정상";
            	}
            }
        },
        {
            targets: 6,
            visible: true,
            render: function (data) {
                return data;
            }
        },
        {
            targets: 7,
            visible: true,
            render: function (data) {
                return data;
            }
        },
        {
            targets: 8,
            visible: true,
            render: function (data) {
                return data;
            }
        },
        {
            targets: 9,
            visible: true,
            orderable: false,
            render: function (data) {
                return '<button onclick="view_user_detail('+ data +')" class="btn btn-outline b-primary text-primary">정보</button>';
            }
        },
        {
            targets: 10,
            visible: true,
            orderable: false,
            render: function (data) {
                return '<button onclick="open_manage_modal('+ data +')" class="btn btn-outline b-info text-info btn-sm" style="font-size:11px;padding:2px 8px;">관리</button>';
            }
        },
        {
            targets: 11,
            visible: true,
            orderable: false,
            render: function (data) {
                return '<button onclick="show_login_logs('+ data +')" class="btn btn-outline b-primary text-primary btn-sm" style="font-size:11px;padding:2px 8px;">로그인</button>';
            }
        },
        {
            targets: 12,
            visible: true,
            orderable: false,
            render: function (data) {
                return '<button onclick="show_fail_logs('+ data +')" class="btn btn-outline b-danger text-danger btn-sm" style="font-size:11px;padding:2px 8px;">실패</button>';
            }
        },
        {
            targets: 13,
            visible: true,
            orderable: false,
            render: function (data) {
                return '<button onclick="show_disconnect_logs('+ data +')" class="btn btn-outline b-warning text-warning btn-sm" style="font-size:11px;padding:2px 8px;">강제종료</button>';
            }
        },
        {
            targets: 14,
            visible: true,
            orderable: false,
            render: function (data) {
                return '<button onclick="show_connection_logs('+ data +')" class="btn btn-outline b-accent text-accent btn-sm" style="font-size:11px;padding:2px 8px;">접속</button>';
            }
        },
        {
            targets: 15,
            visible: true,
            orderable: false,
            render: function (data) {
                return '<button onclick="show_user_diagnosis('+ data +')" class="btn btn-outline b-success text-success btn-sm" style="font-size:11px;padding:2px 8px;"><i class="fa fa-stethoscope"></i> 분석</button>';
            }
        },
        {
            targets: 16,
            visible: true,
            orderable: false,
            render: function (data) {
                return '<button onclick="delete_user('+ data +')" class="btn btn-outline b-danger text-danger btn-sm" style="font-size:11px;padding:2px 8px;">탈퇴</button>';
            },
        },
	          {
           targets: 17,
           visible: true,
           orderable: false,
           render: function (data) {
           return '<button onclick="force_logout(' + data + ')" class="btn btn-outline b-danger text-danger btn-sm" style="font-size:11px;padding:2px 8px;">퇴출</button>';
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

function getUserCount(){
    $.post( "/api/v1/read/user_count", {
        csrfmiddlewaretoken: csrf_token
    }).done(function (data) {
        var countData = data.result;
        $("#active_users").html("구매한 회원수: " + countData.purchase_user + "명");
        $("#session_one_users").html("1세션: " + countData.session_one_user + "명");
        $("#session_two_users").html("2세션: " + countData.session_two_user + "명");
        $("#session_three_users").html("3세션: " + countData.session_three_user + "명");
        $("#session_four_users").html("4세션: " + countData.session_four_user + "명");
        $("#session_five_users").html("5세션: " + countData.session_five_user + "명");
        $("#session_six_users").html("6세션: " + countData.session_six_user + "명");
        $("#expired_users").html("만료: " + countData.expired_user + "명");
        $("#deleted_users").html("삭제: " + countData.deleted_user + "명");
    });
}
// 정보 버튼 클릭
function view_user_detail(user_id){
    $.post( "/api/v1/read/user_detail", {
        csrfmiddlewaretoken: csrf_token,
        user_id: user_id
    }).done(function (data) {
        var user = data.result;
        swal.fire({
            title: '추가정보',
            html: ''+
                  '<div class="form-group tal">'+
                  '<label class="fz12">번호</label>'+
                  '<input type="text" class="form-control" value="' + user.id + '" readonly>'+
                  '</div>'+
                  '<div class="form-group tal">'+
                  '<label class="fz12">이메일</label>'+
                  '<input type="text" class="form-control" value="' + user.email + '" readonly>'+
                  '</div>'+
                  '<div class="form-group tal">'+
                  '<label class="fz12">본인 추천인 코드</label>'+
                  '<input type="text" class="form-control" value="' + user.rec + '" readonly>'+
                  '</div>'+
                  '<div class="form-group tal">'+
                  '<label class="fz12">가입시 입력한 추천인 코드</label>'+
                  '<input type="text" class="form-control" value="' + user.regist_rec + '" readonly>'+
                  '</div>'+
                  '',
            confirmButtonColor: swalColor('base'),
        }).then(function () { /* pass */ });
    });
}

// 서비스 버튼 클릭
function manage_service_time(user_id){
    $.post( "/api/v1/read/user_service_time", {
        csrfmiddlewaretoken: csrf_token,
        user_id: user_id,
    }).done(function (data) {
        var service_time = data.result;
        swal.fire({
            title: '서비스 시간 변경',
            html: ''+
                  '<div class="form-group tal">'+
                  '<label class="fz12">현재 사용자 시간</label>'+
                  '<input type="text" class="form-control" value="' + service_time + '" readonly>'+
                  '</div>'+
                  '<div class="form-group tal">'+
                  '<label class="fz12">변경할 사용자 시간</label>'+
                  '<input id="change_time" type="text" class="form-control" value="' + service_time + '">'+
                  '</div>'+
                  '<div class="form-group tal">'+
                  '<label class="fz12">변경 사유</label>'+
                  '<input id="change_reason" type="text" class="form-control" value="">'+
                  '</div>',
            confirmButtonText: '수정',
            cancelButtonText: '취소',
            confirmButtonColor: swalColor('base'),
            showCancelButton: true,
        }).then(function (result) {
            if (result.value) {
                var change_time = $("#change_time").val();
                var change_reason = $("#change_reason").val();
                $.post("/api/v1/update/user_service_time", {
                    csrfmiddlewaretoken: csrf_token,
                    change_time: change_time,
                    change_reason: change_reason,
                    user_id: user_id
                }).done(function (data) {
                    if (data.result == 200) {
                        Swal.fire({
                          title: data.title,
                          text: data.text,
                          type: 'success',
                          confirmButtonColor: swalColor('success')
                        })
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
    })
}

// 세션 버튼 클릭
function manage_session(user_id){
    $.post( "/api/v1/read/user_session", {
        csrfmiddlewaretoken: csrf_token,
        user_id: user_id
    }).done(function (data) {
        var session = data.result;
        swal.fire({
            title: '세션 변경',
            html: ''+
                  '<div class="form-group tal">'+
                  '<label class="fz12">현재 사용자 세션</label>'+
                  '<input type="text" class="form-control" value="' + session + '" readonly>'+
                  '</div>'+
                  '<div class="form-group tal">'+
                  '<label class="fz12">변경할 사용자 세션</label>'+
                  '<select id="change_session" class="form-control">'+
                    '<option value="1">1</option>'+
                    '<option value="2">2</option>'+
                    '<option value="3">3</option>'+
                    '<option value="4">4</option>'+
                    '<option value="5">5</option>'+
                    '<option value="6">6</option>'+
                  '</select>'+
                  '</div>'+
                  '<div class="form-group tal">'+
                  '<label class="fz12">변경 사유</label>'+
                  '<input id="change_reason" type="text" class="form-control" value="">'+
                  '</div>',
                confirmButtonText: '수정',
                cancelButtonText: '취소',
                confirmButtonColor: swalColor('base'),
                showCancelButton: true
          }).then(function (result) {
              if (result.value) {
                  var change_session = $("#change_session").val();
                  var change_reason = $("#change_reason").val();
                  $.post("/api/v1/update/user_session", {
                      csrfmiddlewaretoken: csrf_token,
                      user_id: user_id,
                      change_session: change_session,
                      change_reason: change_reason
                  }).done(function (data) {
                      if (data.result == 200) {
                          Swal.fire({
                            title: data.title,
                            text: data.text,
                            type: 'success',
                            confirmButtonColor: swalColor('success')
                          })
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

// 비번 버튼 클릭
function change_password(user_id){
    $.post( "/api/v1/read/user_password", {
        csrfmiddlewaretoken: csrf_token,
        user_id: user_id
    }).done(function (data) {
        var password = data.result;
    	swal.fire({
            title: '비밀번호 변경',
            html: ''+
                  '<div class="form-group tal">'+
              	  '<label class="fz12">변경할 비밀번호</label>'+
              	  '<input id="change_password" type="text" class="form-control" value="">'+
                  '</div>'+
                  '<div class="form-group tal">'+
                  '<label class="fz12">변경 사유</label>'+
                  '<input id="change_reason" type="text" class="form-control" value="">'+
                  '</div>'+
                  '<div class="form-group tal">'+
                  '<label class="fz12">encrypted Password</label>'+
                  '<input type="text" class="form-control" value="' + password + '" readonly>'+
                  '</div>',
                confirmButtonText: '수정',
                cancelButtonText: '취소',
                confirmButtonColor: swalColor('base'),
                showCancelButton: true
          }).then(function (result) {
              if (result.value) {
                  var change_password = $("#change_password").val();
                  var change_reason = $("#change_reason").val();
                  $.post("/api/v1/update/user_password", {
                      csrfmiddlewaretoken: csrf_token,
                      user_id: user_id,
                      change_password: change_password,
                      change_reason: change_reason
                  }).done(function (data) {
                      if (data.result == 200) {
                          Swal.fire({
                            title: data.title,
                            text: data.text,
                            type: 'success',
                            confirmButtonColor: swalColor('success')
                          })
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
// 활성화 버튼 클릭
function change_active(user_id){
    swal.fire({
        title: '활성화 상태 변경',
        html: ''+
              '<div class="form-group tal">'+
              '<label class="fz12">변경할 활성화 상태</label>'+
              '<select id="change_active" class="form-control">'+
                '<option value="1">활성화</option>'+
                '<option value="0">비활성화</option>'+
              '</select>'+
              '</div>'+
              '<div class="form-group tal">'+
              '<label class="fz12">변경 사유</label>'+
              '<input id="change_reason" type="text" class="form-control" value="">'+
              '</div>',
        confirmButtonText: '수정',
        cancelButtonText: '취소',
        confirmButtonColor: swalColor('base'),
        showCancelButton: true
    }).then(function (result) {
        if (result.value) {
            var change_active = $("#change_active").val();
            var change_reason = $("#change_reason").val();
            $.post("/api/v1/update/user_active", {
                csrfmiddlewaretoken: csrf_token,
                user_id: user_id,
                change_active: change_active,
                change_reason: change_reason
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

// 탈퇴 버튼 클릭
function delete_user(user_id){
    Swal.fire({
      title: '경고',
      html: '회원 탈퇴 시 다시 되돌릴 수 없습니다<br>정말 계속 하시겠습니까...?'+
      '<div class="form-group tal">'+
      '<label class="fz12">탈퇴 사유</label>'+
      '<input id="change_reason" type="text" class="form-control" value="">'+
      '</div>',
      type: 'error',
      confirmButtonText: '회원탈퇴',
      cancelButtonText: '취소',
      confirmButtonColor: swalColor('error'),
      showCancelButton: true
    }).then(function (result) {
        var change_reason = $("#change_reason").val();
        if (result.value) {
            $.post("/api/v1/delete/user", {
                csrfmiddlewaretoken: csrf_token,
                user_id: user_id,
                change_reason: change_reason
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

// 검색하기 버튼 클릭
function reload_data(){
    datatable.ajax.reload();
}

function force_logout(user_id) {
    $.post("/api/v1/read/user_detail", {
        csrfmiddlewaretoken: csrf_token,
        user_id: user_id
    }).done(function (data) {
        var user = data.result;

        $.post("/api/v1/read/session_list", {
            csrfmiddlewaretoken: csrf_token,
            email: user.email
        }).done(function (res) {
            let html = '';

            // 앱/웹 세션 분리
            const appSessions = res.sessions.filter(function(s) { return !s.is_web; });
            const webSessions = res.sessions.filter(function(s) { return s.is_web; });

            function parseDeviceOS(deviceType, deviceOS) {
                if (!deviceOS) return '-';
                var ua = deviceOS;
                var dtype = (deviceType || '').toLowerCase();

                // Android: "Dalvik/2.1.0 (Linux; U; Android 16; SM-S9360 Build/...)"
                if (dtype === 'android' || ua.indexOf('Android') !== -1) {
                    var parts = [];
                    var verMatch = ua.match(/Android\s+([\d.]+)/);
                    if (verMatch) parts.push('Android ' + verMatch[1]);
                    // 모델명: "Android 16; SM-S9360 Build/" → SM-S9360
                    var modelMatch = ua.match(/;\s*([^;)]+?)\s*Build\//);
                    if (modelMatch) parts.push(modelMatch[1].trim());
                    if (parts.length > 0) return parts.join(', ');
                }

                // iOS: "TitanVPN/2.3.4 (titan.networks.vpn; build:2; iOS 18.7.4) Alamofire/..."
                if (dtype === 'ios' || ua.indexOf('iOS') !== -1) {
                    var iosMatch = ua.match(/iOS\s+([\d.]+)/);
                    if (iosMatch) return 'iOS ' + iosMatch[1];
                }

                // Windows: "RestSharp/..." or others
                if (dtype === 'windows') {
                    var winMatch = ua.match(/Windows\s+NT\s+([\d.]+)/);
                    if (winMatch) {
                        var ntVer = {'10.0':'10/11', '6.3':'8.1', '6.2':'8', '6.1':'7'};
                        return 'Windows ' + (ntVer[winMatch[1]] || winMatch[1]);
                    }
                    // RestSharp 등 라이브러리만 있으면
                    if (ua.indexOf('RestSharp') !== -1) return 'Windows (RestSharp)';
                    return 'Windows';
                }

                // macOS
                if (dtype === 'macos' || ua.indexOf('Mac OS') !== -1 || ua.indexOf('macOS') !== -1) {
                    var macMatch = ua.match(/Mac OS X\s+([\d_.]+)/);
                    if (macMatch) return 'macOS ' + macMatch[1].replace(/_/g, '.');
                    return 'macOS';
                }

                // fallback: 괄호 안 전체 또는 앞 40자
                var fb = ua.match(/\(([^)]+)\)/);
                return fb ? fb[1].substring(0, 60) : ua.substring(0, 40);
            }

            function renderSessionCard(sess, idx, label) {
                const mins = sess.remaining_seconds ? Math.floor(sess.remaining_seconds/60) : 0;
                const dt = sess.device_type || '-';
                const av = sess.app_version || '-';
                const dip = sess.device_ip || '-';
                const loc = [sess.device_country, sess.device_city].filter(Boolean).join(' ') || '-';
                const isp = sess.device_isp || '-';
                const lt = sess.login_time || '-';
                let osInfo = '-';
                if (sess.device_os) {
                    osInfo = parseDeviceOS(sess.device_type, sess.device_os);
                }

                const isServerIp = sess.is_server_ip;
                const isWeb = sess.is_web;
                const ipBanBtn = isServerIp
                    ? `<button class="btn btn-sm btn-secondary" disabled title="⚠️ VPN서버 IP — 차단하면 이 서버의 모든 유저가 차단됩니다">🌐IP차단(서버IP)</button>`
                    : `<button class="btn btn-sm btn-dark" onclick="ban_device('${user.email}','${sess.key}','ip')" title="이 IP 전체 차단 — 같은 IP의 다른 사용자도 영향">🌐IP차단</button>`;
                const ipDisplay = isServerIp
                    ? `${dip} <span class="badge badge-danger" style="font-size:10px;">⚠️서버IP</span>`
                    : dip;

                // 웹/앱에 따른 스타일
                let borderColor = isServerIp ? '#ffc107' : (isWeb ? '#17a2b8' : '#ddd');
                let bgColor = isServerIp ? '#fffdf0' : (isWeb ? '#f0f9ff' : '#fafafa');

                let card = `
                  <div style="border:1px solid ${borderColor}; border-radius:8px; padding:10px 14px; margin-bottom:10px; background:${bgColor}; text-align:left;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                      <span style="font-weight:bold; font-size:13px;">${label} ${idx+1}</span>
                      <div>`;

                if (!isWeb) {
                    card += `<button class="btn btn-sm btn-info" onclick="ban_device('${user.email}','${sess.key}','device')" title="이 기기(UUID)만 차단 — 다른 기기/사용자 영향 없음">📱기기차단</button>
                        <button class="btn btn-sm btn-warning" onclick="ban_device('${user.email}','${sess.key}','session')" title="이 계정 전체 차단 — 다른 기기에서도 사용 불가">🚫계정차단</button>
                        ${ipBanBtn}`;
                }

                card += `<button class="btn btn-sm btn-danger" onclick="delete_session('${sess.key}')">퇴출</button>
                      </div>
                    </div>`;

                if (isServerIp && !isWeb) {
                    card += '<div style="background:#fff3cd;border:1px solid #ffc107;border-radius:4px;padding:4px 8px;margin-bottom:6px;font-size:11px;color:#856404;">⚠️ 접속IP가 VPN 서버 IP입니다. IP차단 시 이 서버를 경유하는 모든 유저가 차단됩니다. 계정차단 또는 기기차단을 이용하세요.</div>';
                }

                card += `<table style="width:100%; font-size:12px; border-collapse:collapse;">
                      <tr><td style="color:#888; width:80px; padding:2px 4px;">세션키</td><td style="padding:2px 4px; word-break:break-all; font-size:11px;">${sess.key}</td></tr>
                      <tr><td style="color:#888; padding:2px 4px;">만료</td><td style="padding:2px 4px;"><span class="badge badge-info">${sess.expire}</span> <small class="text-muted">(남은 ${mins}분)</small></td></tr>`;

                if (!isWeb) {
                    card += `<tr><td style="color:#888; padding:2px 4px;">기기</td><td style="padding:2px 4px;"><span class="badge badge-primary">${dt}</span> <span class="badge badge-secondary">${av}</span></td></tr>
                      <tr><td style="color:#888; padding:2px 4px;">OS</td><td style="padding:2px 4px;">${osInfo}</td></tr>
                      <tr><td style="color:#888; padding:2px 4px;">접속IP</td><td style="padding:2px 4px;">${ipDisplay}</td></tr>
                      <tr><td style="color:#888; padding:2px 4px;">위치</td><td style="padding:2px 4px;">${loc}</td></tr>
                      <tr><td style="color:#888; padding:2px 4px;">ISP</td><td style="padding:2px 4px;">${isp}</td></tr>
                      <tr><td style="color:#888; padding:2px 4px;">로그인</td><td style="padding:2px 4px;">${lt}</td></tr>`;
                }

                card += `</table>`;

                // NAS 연결 정보 표시
                if (!isWeb && sess.nas_connections && sess.nas_connections.length > 0) {
                    card += `<div style="margin-top:8px; border-top:1px dashed #ccc; padding-top:8px;">
                        <div style="font-weight:bold; font-size:12px; color:#6f42c1; margin-bottom:4px;">🔌 NAS 연결 (${sess.nas_connections.length}개)</div>`;
                    sess.nas_connections.forEach(function(nc) {
                        card += `
                        <div style="background:linear-gradient(135deg, #667eea 0%, #764ba2 100%); color:#fff; border-radius:6px; padding:8px 10px; margin-bottom:6px; font-size:11px;">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                                <span style="font-weight:bold; font-size:12px;">🖥️ ${nc.server_name || nc.nasipaddress}</span>
                                <button class="btn btn-sm btn-danger" style="font-size:10px; padding:1px 8px;" onclick="disconnect_nas(${nc.radacctid}, '${user.email}')">연결끊기</button>
                            </div>
                            <table style="width:100%; color:#fff;">
                                <tr><td style="width:60px; opacity:0.8;">프로토콜</td><td><span style="background:rgba(255,255,255,0.2); padding:1px 6px; border-radius:3px;">${nc.protocol}</span></td></tr>
                                <tr><td style="opacity:0.8;">시작시간</td><td>${nc.acctstarttime}</td></tr>
                                <tr><td style="opacity:0.8;">서버IP</td><td>${nc.nasipaddress}</td></tr>
                                <tr><td style="opacity:0.8;">통신사</td><td>${nc.server_telecom || '-'}</td></tr>
                            </table>
                        </div>`;
                    });
                    card += `</div>`;
                }

                card += `</div>`;
                return card;
            }

            // 앱 세션 섹션
            if (appSessions.length > 0) {
                html += `<div style="margin-bottom:12px;"><span style="font-weight:700; font-size:14px; color:#28a745;">📱 앱 로그인 (${appSessions.length}개)</span></div>`;
                appSessions.forEach(function(sess, idx) {
                    html += renderSessionCard(sess, idx, '앱 세션');
                });
            }

            // 웹 세션 섹션
            if (webSessions.length > 0) {
                html += `<div style="margin-bottom:8px; margin-top:${appSessions.length > 0 ? '16' : '0'}px; padding-top:${appSessions.length > 0 ? '12' : '0'}px; ${appSessions.length > 0 ? 'border-top:2px solid #dee2e6;' : ''}">
                    <span style="font-weight:700; font-size:14px; color:#17a2b8;">🌐 웹사이트 로그인 (${webSessions.length}개)</span>
                    <button class="btn btn-sm btn-outline-danger ml-2" onclick="delete_web_sessions('${user.email}')" title="웹 세션만 모두 퇴출">웹 전체 퇴출</button>
                </div>`;
                webSessions.forEach(function(sess, idx) {
                    html += renderSessionCard(sess, idx, '웹 세션');
                });
            }

            // 세션에 매칭 안 된 NAS 연결 표시
            const allNas = res.nas_connections || [];
            const matchedNasIds = new Set();
            res.sessions.forEach(function(s) {
                (s.nas_connections || []).forEach(function(nc) { matchedNasIds.add(nc.radacctid); });
            });
            const unmatchedNas = allNas.filter(function(nc) { return !matchedNasIds.has(nc.radacctid); });
            if (unmatchedNas.length > 0) {
                html += `<div style="margin-top:12px; padding-top:10px; border-top:2px solid #dee2e6;">
                    <span style="font-weight:700; font-size:14px; color:#6f42c1;">🔌 세션 미매칭 NAS 연결 (${unmatchedNas.length}개)</span>
                </div>`;
                unmatchedNas.forEach(function(nc) {
                    html += `
                    <div style="background:linear-gradient(135deg, #667eea 0%, #764ba2 100%); color:#fff; border-radius:6px; padding:8px 10px; margin-top:6px; font-size:11px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                            <span style="font-weight:bold; font-size:12px;">🖥️ ${nc.server_name || nc.nasipaddress}</span>
                            <button class="btn btn-sm btn-danger" style="font-size:10px; padding:1px 8px;" onclick="disconnect_nas(${nc.radacctid}, '${user.email}')">연결끊기</button>
                        </div>
                        <table style="width:100%; color:#fff;">
                            <tr><td style="width:60px; opacity:0.8;">프로토콜</td><td><span style="background:rgba(255,255,255,0.2); padding:1px 6px; border-radius:3px;">${nc.protocol}</span></td></tr>
                            <tr><td style="opacity:0.8;">시작시간</td><td>${nc.acctstarttime}</td></tr>
                            <tr><td style="opacity:0.8;">클라이언트IP</td><td>${nc.client_ip}</td></tr>
                            <tr><td style="opacity:0.8;">서버IP</td><td>${nc.nasipaddress}</td></tr>
                            <tr><td style="opacity:0.8;">통신사</td><td>${nc.server_telecom || '-'}</td></tr>
                        </table>
                    </div>`;
                });
            }

            // 하단 버튼
            if (res.sessions.length > 0) {
                html += `
                  <div class="text-center mt-3">
                    <button class="btn btn-danger" onclick="delete_all_sessions('${user.email}')">모든 세션 퇴출</button>
                    <button class="btn btn-secondary ml-2" onclick="show_ban_history('${user.email}')">차단이력</button>
                  </div>`;
            } else {
                html += `
                  <div style="text-align:center;padding:20px;color:#888;">현재 활성 세션이 없습니다</div>
                  <div class="text-center mt-2">
                    <button class="btn btn-sm btn-info" onclick="ban_device('${user.email}','','device')">📱기기차단</button>
                    <button class="btn btn-sm btn-warning ml-1" onclick="ban_device('${user.email}','','session')">🚫계정차단</button>
                    <button class="btn btn-sm btn-dark ml-1" onclick="ban_device('${user.email}','','ip')">🌐IP차단</button>
                    <button class="btn btn-secondary ml-2" onclick="show_ban_history('${user.email}')">차단이력</button>
                  </div>`;
            }

            // 요약 표시
            const totalNas = allNas.length;
            let summaryHtml = `<div style="text-align:center; margin-bottom:10px; font-size:12px; color:#666;">
                총 ${res.sessions.length}개 세션 — 📱앱 ${appSessions.length}개 | 🌐웹 ${webSessions.length}개${totalNas > 0 ? ' | 🔌NAS ' + totalNas + '개' : ''}
            </div>`;

            Swal.fire({
                title: user.email + ' - 세션 목록',
                html: summaryHtml + html || '세션 없음',
                confirmButtonText: '닫기',
                confirmButtonColor: swalColor('base'),
                width: '600px'
            });
        });
    });
}

function delete_session(key) {
    $.post("/api/v1/delete/session", {
        csrfmiddlewaretoken: csrf_token,
        session_key: key
    }).done(function (res) {
        if (res.result === 200) {
            Swal.fire('성공', '세션 퇴출 완료', 'success');
        } else {
            Swal.fire('오류', '삭제 실패', 'error');
        }
    });
}

function disconnect_nas(radacctid, email) {
    Swal.fire({
        title: 'NAS 연결 끊기',
        text: '이 VPN 연결을 강제 종료하시겠습니까?',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        confirmButtonText: '연결 끊기',
        cancelButtonText: '취소'
    }).then(function(result) {
        if (result.isConfirmed) {
            $.post("/api/v1/delete/disconnect_nas", {
                csrfmiddlewaretoken: csrf_token,
                radacctid: radacctid,
                email: email
            }).done(function (res) {
                if (res.result === 200) {
                    Swal.fire('성공', 'NAS 연결 종료 완료', 'success');
                } else {
                    Swal.fire('오류', res.message || '연결 종료 실패', 'error');
                }
            }).fail(function() {
                Swal.fire('오류', '서버 통신 실패', 'error');
            });
        }
    });
}

function delete_all_sessions(email) {
    $.post("/api/v1/delete/all_sessions", {
        csrfmiddlewaretoken: csrf_token,
        email: email
    }).done(function (res) {
        if (res.result === 200) {
            Swal.fire('성공', '총 ' + res.deleted + '개의 세션을 퇴출했습니다.', 'success');
        } else {
            Swal.fire('오류', '모든 세션 삭제 실패', 'error');
        }
    });
}

function delete_web_sessions(email) {
    Swal.fire({
        title: '웹 세션 전체 퇴출',
        text: '이 사용자의 웹사이트 로그인 세션만 모두 퇴출합니다. 앱 세션은 유지됩니다.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        confirmButtonText: '웹 세션 퇴출',
        cancelButtonText: '취소'
    }).then(function(result) {
        if (result.isConfirmed) {
            $.post("/api/v1/delete/web_sessions", {
                csrfmiddlewaretoken: csrf_token,
                email: email
            }).done(function (res) {
                if (res.result === 200) {
                    Swal.fire('성공', '웹 세션 ' + res.deleted + '개를 퇴출했습니다.', 'success');
                } else {
                    Swal.fire('오류', '웹 세션 삭제 실패', 'error');
                }
            });
        }
    });
}

// ===== 통합 관리 모달 (서비스+세션+비번+활성) =====
function open_manage_modal(user_id) {
    $.post("/api/v1/read/user_manage_info", {
        csrfmiddlewaretoken: csrf_token,
        user_id: user_id
    }).done(function (data) {
        if (data.result !== 200) {
            Swal.fire('오류', '정보 조회 실패', 'error');
            return;
        }
        var activeText = data.is_active == 1 ? '활성화' : '비활성화';
        Swal.fire({
            title: data.email + ' 관리',
            width: 520,
            html:
                '<div style="text-align:left;font-size:13px;">' +
                // 서비스 시간
                '<div class="form-group" style="margin-bottom:12px;">' +
                '<label style="font-weight:700;font-size:12px;">📅 서비스 시간</label>' +
                '<input id="mng_service_time" type="text" class="form-control" value="' + data.service_time + '">' +
                '</div>' +
                // 세션
                '<div class="form-group" style="margin-bottom:12px;">' +
                '<label style="font-weight:700;font-size:12px;">🔗 세션 수</label>' +
                '<select id="mng_session" class="form-control">' +
                '<option value="1"' + (data.session == '1' ? ' selected' : '') + '>1</option>' +
                '<option value="2"' + (data.session == '2' ? ' selected' : '') + '>2</option>' +
                '<option value="3"' + (data.session == '3' ? ' selected' : '') + '>3</option>' +
                '<option value="4"' + (data.session == '4' ? ' selected' : '') + '>4</option>' +
                '<option value="5"' + (data.session == '5' ? ' selected' : '') + '>5</option>' +
                '<option value="6"' + (data.session == '6' ? ' selected' : '') + '>6</option>' +
                '</select>' +
                '</div>' +
                // 비밀번호 (기존 — 앱 로그인만)
                '<div class="form-group" style="margin-bottom:12px;">' +
                '<label style="font-weight:700;font-size:12px;">🔑 비밀번호 변경 (현재: ' + data.password + ')</label>' +
                '<input id="mng_password" type="text" class="form-control" placeholder="변경할 비밀번호 (빈칸이면 변경 안함)">' +
                '</div>' +
                // 비밀번호 직접 변경 (앱+VPN 동시)
                '<div class="form-group" style="margin-bottom:12px;background:#fff8e1;padding:10px;border-radius:6px;border:1px solid #ffe082;">' +
                '<label style="font-weight:700;font-size:12px;color:#e65100;">🔐 비밀번호 직접 변경 (앱+VPN 동시적용)</label>' +
                '<div style="font-size:11px;color:#888;margin-bottom:4px;">이메일 인증 없이 관리자가 직접 변경합니다. 앱 로그인 + VPN 접속 비밀번호 모두 변경됩니다.</div>' +
                '<input id="mng_password_direct" type="text" class="form-control" placeholder="새 비밀번호 입력 (8자 이상, 영문+숫자 등 2종 조합)">' +
                '</div>' +
                // 활성
                '<div class="form-group" style="margin-bottom:12px;">' +
                '<label style="font-weight:700;font-size:12px;">✅ 활성 상태 (현재: ' + activeText + ')</label>' +
                '<select id="mng_active" class="form-control">' +
                '<option value="1"' + (data.is_active == 1 ? ' selected' : '') + '>활성화</option>' +
                '<option value="0"' + (data.is_active == 0 ? ' selected' : '') + '>비활성화</option>' +
                '</select>' +
                '</div>' +
                // 변경사유
                '<div class="form-group">' +
                '<label style="font-weight:700;font-size:12px;">📝 변경 사유</label>' +
                '<input id="mng_reason" type="text" class="form-control" placeholder="변경 사유 입력">' +
                '</div>' +
                '</div>',
            confirmButtonText: '저장',
            cancelButtonText: '취소',
            confirmButtonColor: '#007bff',
            showCancelButton: true,
        }).then(function (result) {
            if (!result.value) return;
            var reason = $('#mng_reason').val();
            var promises = [];

            // 서비스 시간 변경
            if ($('#mng_service_time').val() !== data.service_time) {
                promises.push($.post("/api/v1/update/user_service_time", {
                    csrfmiddlewaretoken: csrf_token,
                    user_id: user_id,
                    change_time: $('#mng_service_time').val(),
                    change_reason: reason
                }));
            }
            // 세션 변경
            if ($('#mng_session').val() !== data.session) {
                promises.push($.post("/api/v1/update/user_session", {
                    csrfmiddlewaretoken: csrf_token,
                    user_id: user_id,
                    change_session: $('#mng_session').val(),
                    change_reason: reason
                }));
            }
            // 비밀번호 변경 (기존 — 앱 로그인만)
            if ($('#mng_password').val()) {
                promises.push($.post("/api/v1/update/user_password", {
                    csrfmiddlewaretoken: csrf_token,
                    user_id: user_id,
                    change_password: $('#mng_password').val(),
                    change_reason: reason
                }));
            }
            // 비밀번호 직접 변경 (앱+VPN 동시)
            if ($('#mng_password_direct').val()) {
                promises.push($.post("/api/v1/update/user_password_direct", {
                    csrfmiddlewaretoken: csrf_token,
                    user_id: user_id,
                    new_password: $('#mng_password_direct').val(),
                    change_reason: reason
                }));
            }
            // 활성 변경
            if ($('#mng_active').val() != data.is_active) {
                promises.push($.post("/api/v1/update/user_active", {
                    csrfmiddlewaretoken: csrf_token,
                    user_id: user_id,
                    change_active: $('#mng_active').val(),
                    change_reason: reason
                }));
            }

            if (promises.length === 0) {
                Swal.fire('알림', '변경 사항이 없습니다.', 'info');
                return;
            }
            $.when.apply($, promises).done(function() {
                Swal.fire('성공', '변경 완료!', 'success');
                reload_data();
            }).fail(function() {
                Swal.fire('오류', '일부 변경 실패', 'error');
            });
        });
    });
}

// ===== 로그 모달 공통 =====
function openLogModal(title) {
    $('#log-modal-title').text(title);
    $('#log-modal-body').html('<div style="text-align:center;padding:40px;color:#888;"><i class="fa fa-spinner fa-spin"></i> 로딩 중...</div>');
    $('#log-modal-overlay').addClass('show');
}
function closeLogModal() {
    $('#log-modal-overlay').removeClass('show');
}

function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
    return (bytes / 1073741824).toFixed(2) + ' GB';
}

// ===== 로그인 로그 =====
function show_login_logs(user_id) {
    openLogModal('로그인 로그 (최근 50건)');
    $.post("/api/v1/read/user_login_logs", {
        csrfmiddlewaretoken: csrf_token,
        user_id: user_id
    }).done(function (res) {
        if (res.result === 200 && res.logs && res.logs.length > 0) {
            var html = '<table class="log-tbl"><thead><tr>';
            html += '<th>#</th><th>시간</th><th>이메일</th><th>앱버전</th><th>기기</th><th>IP</th><th>국가</th><th>도시</th><th>ISP</th><th>로드밸런서</th><th>API서버</th>';
            html += '</tr></thead><tbody>';
            res.logs.forEach(function(log, i) {
                html += '<tr>';
                html += '<td>' + (i+1) + '</td>';
                html += '<td>' + log.login_time + '</td>';
                html += '<td>' + log.email + '</td>';
                html += '<td>' + log.app_version + '</td>';
                html += '<td>' + log.device_type + '</td>';
                html += '<td>' + log.device_ip + '</td>';
                html += '<td>' + log.country + '</td>';
                html += '<td>' + log.city + '</td>';
                html += '<td class="wrap">' + log.isp + '</td>';
                html += '<td>' + log.load_balancer + '</td>';
                html += '<td>' + log.api_url + '</td>';
                html += '</tr>';
            });
            html += '</tbody></table>';
            $('#log-modal-body').html(html);
        } else {
            $('#log-modal-body').html('<div style="text-align:center;padding:40px;color:#888;">로그인 로그가 없습니다.</div>');
        }
    }).fail(function() {
        $('#log-modal-body').html('<div style="text-align:center;padding:40px;color:#dc3545;">데이터 로드 실패</div>');
    });
}

// ===== 접속실패 로그 =====
function show_fail_logs(user_id) {
    openLogModal('접속실패 로그 (최근 50건)');
    $.post("/api/v1/read/user_fail_logs", {
        csrfmiddlewaretoken: csrf_token,
        user_id: user_id
    }).done(function (res) {
        if (res.result === 200 && res.logs && res.logs.length > 0) {
            var html = '<table class="log-tbl"><thead><tr>';
            html += '<th>#</th><th>시간</th><th>프로토콜</th><th>서버</th><th>플랫폼</th><th>앱버전</th><th>IP</th><th>위치</th><th>기기</th>';
            html += '</tr></thead><tbody>';
            res.logs.forEach(function(log, i) {
                html += '<tr>';
                html += '<td>' + (i+1) + '</td>';
                html += '<td>' + log.failed_time + '</td>';
                html += '<td>' + log.protocol + '</td>';
                html += '<td>' + log.server_name + '</td>';
                html += '<td>' + log.platform + '</td>';
                html += '<td>' + log.app_version + '</td>';
                html += '<td>' + log.ip + '</td>';
                html += '<td>' + log.location + '</td>';
                html += '<td class="wrap">' + log.device + '</td>';
                html += '</tr>';
            });
            html += '</tbody></table>';
            $('#log-modal-body').html(html);
        } else {
            $('#log-modal-body').html('<div style="text-align:center;padding:40px;color:#888;">접속실패 로그가 없습니다.</div>');
        }
    }).fail(function() {
        $('#log-modal-body').html('<div style="text-align:center;padding:40px;color:#dc3545;">데이터 로드 실패</div>');
    });
}

// ===== 강제종료 로그 =====
function show_disconnect_logs(user_id) {
    openLogModal('강제종료 로그 (최근 50건)');
    $.post("/api/v1/read/user_disconnect_logs", {
        csrfmiddlewaretoken: csrf_token,
        user_id: user_id
    }).done(function (res) {
        if (res.result === 200 && res.logs && res.logs.length > 0) {
            var html = '<table class="log-tbl"><thead><tr>';
            html += '<th>#</th><th>시간</th><th>프로토콜</th><th>서버</th><th>통신사</th><th>세션</th><th>접속수</th><th>이전IP</th><th>새IP</th>';
            html += '</tr></thead><tbody>';
            res.logs.forEach(function(log, i) {
                html += '<tr>';
                html += '<td>' + (i+1) + '</td>';
                html += '<td>' + log.disconnected_time + '</td>';
                html += '<td>' + log.protocol + '</td>';
                html += '<td>' + log.server_name + '</td>';
                html += '<td>' + log.telecom + '</td>';
                html += '<td>' + log.session + '</td>';
                html += '<td>' + log.connected_count + '</td>';
                html += '<td>' + log.old_ip + '</td>';
                html += '<td>' + log.new_ip + '</td>';
                html += '</tr>';
            });
            html += '</tbody></table>';
            $('#log-modal-body').html(html);
        } else {
            $('#log-modal-body').html('<div style="text-align:center;padding:40px;color:#888;">강제종료 로그가 없습니다.</div>');
        }
    }).fail(function() {
        $('#log-modal-body').html('<div style="text-align:center;padding:40px;color:#dc3545;">데이터 로드 실패</div>');
    });
}

// ===== 서버접속 로그 =====
function show_connection_logs(user_id) {
    openLogModal('서버접속 로그 (최근 50건)');
    $.post("/api/v1/read/user_connection_logs", {
        csrfmiddlewaretoken: csrf_token,
        user_id: user_id
    }).done(function (res) {
        if (res.result === 200 && res.logs && res.logs.length > 0) {
            var html = '<table class="log-tbl"><thead><tr>';
            html += '<th>#</th><th>접속시작</th><th>접속종료</th><th>NAS IP</th><th>프로토콜</th><th>클라이언트IP</th><th>할당IP</th><th>수신</th><th>송신</th>';
            html += '</tr></thead><tbody>';
            res.logs.forEach(function(log, i) {
                var stopText = log.stop_time || '<span style="color:#28a745;font-weight:700;">접속중</span>';
                html += '<tr>';
                html += '<td>' + (i+1) + '</td>';
                html += '<td>' + log.start_time + '</td>';
                html += '<td>' + stopText + '</td>';
                html += '<td>' + log.nas_ip + '</td>';
                html += '<td>' + log.nas_type + '</td>';
                html += '<td>' + log.client_ip + '</td>';
                html += '<td>' + log.private_ip + '</td>';
                html += '<td>' + formatBytes(log.input_bytes) + '</td>';
                html += '<td>' + formatBytes(log.output_bytes) + '</td>';
                html += '</tr>';
            });
            html += '</tbody></table>';
            $('#log-modal-body').html(html);
        } else {
            $('#log-modal-body').html('<div style="text-align:center;padding:40px;color:#888;">서버접속 로그가 없습니다.</div>');
        }
    }).fail(function() {
        $('#log-modal-body').html('<div style="text-align:center;padding:40px;color:#dc3545;">데이터 로드 실패</div>');
    });
}

// ===== 접속금지 (기기/세션/IP 차단) =====
function ban_device(email, session_key, ban_type) {
    var typeLabel = {session: '계정 차단', device: '기기(UUID) 차단', ip: 'IP 차단'}[ban_type] || ban_type;
    Swal.fire({
        title: '접속금지 - ' + typeLabel,
        html:
            '<div style="text-align:left;font-size:13px;">' +
            '<p><b>대상:</b> ' + email + '</p>' +
            '<p><b>차단유형:</b> ' + typeLabel + '</p>' +
            (ban_type === 'device' ? '<p style="color:#17a2b8;font-size:12px;">📱 기기(UUID) 차단<br>✅ 이 기기에서만 로그인 불가 (다른 기기 정상)<br>✅ 다른 사용자 영향 없음<br>⚠️ iOS 재설치 시 UUID가 바뀌어 우회 가능<br>⚠️ Android는 재설치해도 차단 유지</p>' : '') +
            (ban_type === 'ip' ? '<p style="color:#dc3545;font-size:12px;">🌐 IP 차단<br>⚠️ 같은 IP(공유기/회사)의 <b>다른 정상 사용자도 차단됨</b><br>⚠️ IP가 바뀌면 우회 가능<br>→ 확실히 이 IP 전체를 막아야 할 때만 사용하세요</p>' : '') +
            (ban_type === 'session' ? '<p style="color:#FF8C00;font-size:12px;">🚫 계정 차단<br>⚠️ 이 계정의 <b>모든 기기에서 로그인 불가</b><br>⚠️ 다른 기기에서 정상 사용 중이어도 차단됨<br>→ 이 계정 자체를 막아야 할 때 사용하세요</p>' : '') +
            '<div class="form-group">' +
            '<label style="font-weight:700;font-size:12px;">차단 사유</label>' +
            '<input id="ban_reason" type="text" class="form-control" placeholder="차단 사유를 입력하세요">' +
            '</div>' +
            '</div>',
        confirmButtonText: '접속금지 처리',
        cancelButtonText: '취소',
        confirmButtonColor: '#dc3545',
        showCancelButton: true,
    }).then(function(result) {
        if (!result.value) return;
        var reason = $('#ban_reason').val();
        $.post("/api/v1/create/ban_device", {
            csrfmiddlewaretoken: csrf_token,
            email: email,
            session_key: session_key,
            ban_type: ban_type,
            reason: reason
        }).done(function(res) {
            if (res.result === 200) {
                Swal.fire('성공', res.msg, 'success');
                reload_data();
            } else {
                Swal.fire('오류', res.msg || '차단 실패', 'error');
            }
        }).fail(function() {
            Swal.fire('오류', '서버 통신 실패', 'error');
        });
    });
}

// ===== 차단 이력 보기 =====
function show_ban_history(email) {
    $.post("/api/v1/read/banned_devices", {
        csrfmiddlewaretoken: csrf_token,
        email: email
    }).done(function(res) {
        if (res.result !== 200) {
            Swal.fire('오류', '조회 실패', 'error');
            return;
        }
        var bans = res.bans;
        if (!bans || bans.length === 0) {
            Swal.fire('정보', '차단 이력이 없습니다.', 'info');
            return;
        }
        var html = '';
        bans.forEach(function(ban) {
            var typeLabel = {session: '계정차단', device: '기기(UUID)차단', ip: 'IP차단'}[ban.ban_type] || ban.ban_type;
            var groupTag = ban.ban_group ? ' <span class="badge badge-warning" style="font-size:10px;">그룹:'+ban.ban_group.substring(0,10)+'</span>' : '';
            var statusBadge = ban.is_active == 1
                ? '<span class="badge badge-danger">차단중</span>'
                : '<span class="badge badge-secondary">해제됨</span>';
            html += '<div style="border:1px solid #ddd; border-radius:8px; padding:10px 14px; margin-bottom:10px; background:' + (ban.is_active == 1 ? '#fff5f5' : '#f8f9fa') + '; text-align:left;">';
            html += '<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">';
            html += '<span>' + statusBadge + ' <span class="badge badge-info">' + typeLabel + '</span>' + groupTag + '</span>';
            if (ban.is_active == 1) {
                html += '<button class="btn btn-sm btn-outline-success" onclick="unban_device(' + ban.id + ',\'' + email + '\')">해제</button>';
            }
            html += '</div>';
            html += '<table style="width:100%; font-size:12px; border-collapse:collapse;">';
            if (ban.device_uuid) html += '<tr><td style="color:#888;width:80px;padding:2px 4px;">UUID</td><td style="padding:2px 4px;word-break:break-all;font-size:11px;">' + ban.device_uuid + '</td></tr>';
            if (ban.device_ip) html += '<tr><td style="color:#888;padding:2px 4px;">IP</td><td style="padding:2px 4px;">' + ban.device_ip + '</td></tr>';
            if (ban.device_type) html += '<tr><td style="color:#888;padding:2px 4px;">기기</td><td style="padding:2px 4px;">' + ban.device_type + '</td></tr>';
            if (ban.reason) html += '<tr><td style="color:#888;padding:2px 4px;">사유</td><td style="padding:2px 4px;">' + ban.reason + '</td></tr>';
            html += '<tr><td style="color:#888;padding:2px 4px;">처리자</td><td style="padding:2px 4px;">' + ban.banned_by + '</td></tr>';
            html += '<tr><td style="color:#888;padding:2px 4px;">차단일</td><td style="padding:2px 4px;">' + ban.regist_date + '</td></tr>';
            if (ban.modify_date) html += '<tr><td style="color:#888;padding:2px 4px;">해제일</td><td style="padding:2px 4px;">' + ban.modify_date + '</td></tr>';
            html += '</table></div>';
        });

        Swal.fire({
            title: email + ' - 차단 이력',
            html: html,
            confirmButtonText: '닫기',
            confirmButtonColor: swalColor('base'),
            width: '650px'
        });
    });
}

// ===== 차단 해제 =====
function unban_device(ban_id, email) {
    Swal.fire({
        title: '차단 해제',
        text: '정말로 이 차단을 해제하시겠습니까?',
        type: 'warning',
        confirmButtonText: '해제',
        cancelButtonText: '취소',
        confirmButtonColor: '#28a745',
        showCancelButton: true,
    }).then(function(result) {
        if (!result.value) return;
        $.post("/api/v1/update/unban_device", {
            csrfmiddlewaretoken: csrf_token,
            ban_id: ban_id
        }).done(function(res) {
            if (res.result === 200) {
                Swal.fire('성공', res.msg, 'success');
                // 차단 이력 다시 열기
                show_ban_history(email);
            } else {
                Swal.fire('오류', res.msg || '해제 실패', 'error');
            }
        });
    });
}

// ========================================================
// ===== 사용자 종합 진단 (분석 버튼) =====
// ========================================================
function show_user_diagnosis(user_id) {
    openLogModal('고객 종합 진단');
    $.post("/api/v1/read/user_diagnosis", {
        csrfmiddlewaretoken: csrf_token,
        user_id: user_id
    }).done(function (res) {
        if (res.result !== 200) {
            $('#log-modal-body').html('<div style="text-align:center;padding:40px;color:#dc3545;">' + (res.msg || '데이터 로드 실패') + '</div>');
            return;
        }
        var d = res.data;
        var acct = d.account;
        var sub = d.subscription;
        var smap = d.server_map || {};
        var html = '';

        // ── 서버 이름 조회 헬퍼 ──
        function sname(ip) { return smap[ip] ? smap[ip] : ip; }

        // ── 1. 계정 + 구독 요약 카드 ──
        var expBadge = '';
        if (sub.expired === true) expBadge = '<span style="background:#dc3545;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700;">만료</span>';
        else if (sub.expired === false) expBadge = '<span style="background:#28a745;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700;">유효 (' + sub.days_left + '일)</span>';
        else expBadge = '<span style="background:#ffc107;color:#333;padding:2px 8px;border-radius:10px;font-size:11px;">미확인</span>';

        var deployBadge = acct.v2ray_deployed == 1
            ? '<span style="color:#28a745;font-weight:700;">배포됨</span>'
            : '<span style="color:#999;">미배포</span>';

        html += '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;">';
        // 계정 카드
        html += '<div style="flex:1;min-width:280px;background:#f8f9fa;border-radius:8px;padding:14px;border:1px solid #e9ecef;">';
        html += '<div style="font-weight:700;font-size:14px;margin-bottom:8px;color:#495057;"><i class="fa fa-user"></i> 계정 정보</div>';
        html += '<table style="width:100%;font-size:12px;">';
        html += '<tr><td style="color:#888;width:90px;padding:3px 0;">이메일</td><td style="font-weight:600;">' + acct.email + '</td></tr>';
        html += '<tr><td style="color:#888;padding:3px 0;">사용자명</td><td>' + acct.username + '</td></tr>';
        html += '<tr><td style="color:#888;padding:3px 0;">구독만료</td><td>' + (sub.expiry || '-') + ' ' + expBadge + '</td></tr>';
        html += '<tr><td style="color:#888;padding:3px 0;">동시접속</td><td><b>' + (sub.max_sessions || '-') + '</b>개</td></tr>';
        html += '<tr><td style="color:#888;padding:3px 0;">V2RAY UUID</td><td style="font-size:10px;word-break:break-all;">' + (acct.v2ray_uuid || '-') + ' ' + deployBadge + '</td></tr>';
        html += '</table></div>';

        // 현재 상태 카드
        var activeCount = d.active_sessions.length;
        var statusColor = activeCount > 0 ? '#28a745' : '#dc3545';
        var statusText = activeCount > 0 ? '접속 중 (' + activeCount + '세션)' : '미접속';
        html += '<div style="flex:1;min-width:280px;background:#f8f9fa;border-radius:8px;padding:14px;border:1px solid #e9ecef;">';
        html += '<div style="display:flex;justify-content:space-between;align-items:center;font-weight:700;font-size:14px;margin-bottom:8px;color:#495057;">';
        html += '<span><i class="fa fa-signal"></i> 현재 상태</span>';
        if (activeCount > 0) {
            html += '<button id="btn-kick-all" onclick="kickAllSessions(\'' + acct.email + '\')" style="background:#dc3545;color:#fff;border:none;padding:3px 10px;border-radius:5px;font-size:10px;font-weight:600;cursor:pointer;"><i class="fa fa-power-off"></i> 전체 강제종료</button>';
        }
        html += '</div>';
        html += '<div style="font-size:24px;font-weight:700;color:' + statusColor + ';margin:8px 0;">' + statusText + '</div>';
        if (activeCount > 0) {
            d.active_sessions.forEach(function(s) {
                var sessMin = Math.floor(s.session_sec / 60);
                html += '<div id="sess-card-' + s.radacctid + '" style="background:#fff;border-radius:6px;padding:8px 10px;margin-top:6px;border:1px solid #dee2e6;font-size:11px;">';
                html += '<div style="display:flex;justify-content:space-between;align-items:center;">';
                html += '<span><b>' + s.protocol + '</b> → ' + sname(s.nas_ip) + '</span>';
                html += '<span style="display:flex;align-items:center;gap:6px;">';
                html += '<span style="color:#888;">' + sessMin + '분</span>';
                html += '<button onclick="kickOneSession(' + s.radacctid + ',\'' + (acct.email || '') + '\',this)" style="background:#ff5252;color:#fff;border:none;padding:1px 6px;border-radius:3px;font-size:9px;cursor:pointer;" title="이 세션 강제종료"><i class="fa fa-times"></i></button>';
                html += '</span>';
                html += '</div>';
                html += '<div style="color:#666;margin-top:3px;">IP: ' + s.client_ip + ' → ' + s.private_ip;
                html += ' | ↓' + formatBytes(s.input_bytes) + ' ↑' + formatBytes(s.output_bytes) + '</div>';
                html += '</div>';
            });
        }
        // 최근 기기 정보
        if (d.device_history.length > 0) {
            var dev = d.device_history[0];
            html += '<div style="margin-top:10px;font-size:11px;color:#666;">';
            html += '<i class="fa fa-mobile"></i> 최근 기기: <b>' + dev.type + '</b> | ' + dev.isp + ' | ' + dev.city + ', ' + dev.country;
            html += ' <span style="color:#aaa;">(' + dev.time + ')</span>';
            html += '</div>';
        }
        html += '</div>';
        html += '</div>';

        // ── 2. 최근 접속 실패 ──
        if (d.recent_failures.length > 0) {
            html += '<div style="margin-bottom:16px;">';
            html += '<div style="font-weight:700;font-size:13px;margin-bottom:8px;color:#dc3545;"><i class="fa fa-exclamation-triangle"></i> 최근 접속 실패 (' + d.recent_failures.length + '건)</div>';
            html += '<table class="log-tbl"><thead><tr>';
            html += '<th>시간</th><th>프로토콜</th><th>서버</th><th>플랫폼</th><th>기기</th><th>IP</th><th>위치</th><th>앱버전</th>';
            html += '</tr></thead><tbody>';
            d.recent_failures.forEach(function(f) {
                // 오늘 실패는 빨간 배경
                var today = new Date().toISOString().substring(0, 10);
                var isToday = f.time.substring(0, 10) === today;
                var trStyle = isToday ? ' style="background:#fff5f5;"' : '';
                html += '<tr' + trStyle + '>';
                html += '<td>' + f.time + '</td>';
                html += '<td><b>' + f.protocol + '</b></td>';
                html += '<td>' + f.server_name + '</td>';
                html += '<td>' + f.platform + '</td>';
                html += '<td class="wrap">' + f.device + '</td>';
                html += '<td>' + f.ip + '</td>';
                html += '<td class="wrap">' + f.location + '</td>';
                html += '<td>' + f.app_version + '</td>';
                html += '</tr>';
            });
            html += '</tbody></table></div>';
        }

        // ── 3. 최근 세션 이력 ──
        if (d.recent_sessions.length > 0) {
            html += '<div style="margin-bottom:16px;">';
            html += '<div style="font-weight:700;font-size:13px;margin-bottom:8px;color:#495057;"><i class="fa fa-history"></i> 최근 세션 이력 (' + d.recent_sessions.length + '건)</div>';
            html += '<table class="log-tbl"><thead><tr>';
            html += '<th>상태</th><th>시작</th><th>종료</th><th>프로토콜</th><th>서버</th><th>시간</th><th>클라이언트IP</th><th>수신</th><th>송신</th><th>종료사유</th>';
            html += '</tr></thead><tbody>';
            d.recent_sessions.forEach(function(s) {
                var statusBadge = '';
                if (s.status === 'active') statusBadge = '<span style="background:#28a745;color:#fff;padding:1px 6px;border-radius:8px;font-size:10px;">접속중</span>';
                else if (s.status === 'success') statusBadge = '<span style="background:#17a2b8;color:#fff;padding:1px 6px;border-radius:8px;font-size:10px;">성공</span>';
                else statusBadge = '<span style="background:#dc3545;color:#fff;padding:1px 6px;border-radius:8px;font-size:10px;">실패</span>';

                var duration = '';
                if (s.session_sec > 0) {
                    if (s.session_sec >= 3600) duration = Math.floor(s.session_sec / 3600) + '시간 ' + Math.floor((s.session_sec % 3600) / 60) + '분';
                    else if (s.session_sec >= 60) duration = Math.floor(s.session_sec / 60) + '분';
                    else duration = s.session_sec + '초';
                }

                html += '<tr>';
                html += '<td>' + statusBadge + '</td>';
                html += '<td>' + s.start_time + '</td>';
                html += '<td>' + (s.stop_time || '-') + '</td>';
                html += '<td><b>' + s.protocol + '</b></td>';
                html += '<td>' + sname(s.nas_ip) + ' <span style="color:#aaa;font-size:10px;">(' + s.nas_ip + ')</span></td>';
                html += '<td>' + duration + '</td>';
                html += '<td>' + s.client_ip + '</td>';
                html += '<td>' + formatBytes(s.input_bytes) + '</td>';
                html += '<td>' + formatBytes(s.output_bytes) + '</td>';
                html += '<td>' + s.terminate_cause + '</td>';
                html += '</tr>';
            });
            html += '</tbody></table></div>';
        }

        // ── 4. 기기 이력 ──
        if (d.device_history.length > 1) {
            html += '<div style="margin-bottom:16px;">';
            html += '<div style="font-weight:700;font-size:13px;margin-bottom:8px;color:#495057;"><i class="fa fa-mobile"></i> 기기 이력 (최근 ' + d.device_history.length + '건)</div>';
            html += '<table class="log-tbl"><thead><tr>';
            html += '<th>시간</th><th>기기</th><th>ISP</th><th>도시</th><th>국가</th>';
            html += '</tr></thead><tbody>';
            d.device_history.forEach(function(dev) {
                html += '<tr>';
                html += '<td>' + dev.time + '</td>';
                html += '<td>' + dev.type + '</td>';
                html += '<td class="wrap">' + dev.isp + '</td>';
                html += '<td>' + dev.city + '</td>';
                html += '<td>' + dev.country + '</td>';
                html += '</tr>';
            });
            html += '</tbody></table></div>';
        }

        // ── 결과 없으면 안내 ──
        if (!d.active_sessions.length && !d.recent_sessions.length && !d.recent_failures.length) {
            html += '<div style="text-align:center;padding:30px;color:#888;">접속 기록이 없습니다.</div>';
        }

        $('#log-modal-body').html(html);
    }).fail(function() {
        $('#log-modal-body').html('<div style="text-align:center;padding:40px;color:#dc3545;">데이터 로드 실패</div>');
    });
}

// ── 개별 세션 강제종료 ──
function kickOneSession(radacctid, email, btn) {
    if (!confirm('이 세션을 강제종료하시겠습니까?')) return;
    var $btn = $(btn);
    $btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i>');
    $.ajax({
        url: '/api/v1/delete/disconnect_nas',
        type: 'POST',
        data: { radacctid: radacctid, email: email, csrfmiddlewaretoken: csrf_token },
        success: function(res) {
            if (res.result === 200) {
                $('#sess-card-' + radacctid).css({opacity: '0.3', pointerEvents: 'none'});
                $btn.html('<i class="fa fa-check"></i>').css('background', '#28a745');
            } else {
                alert(res.message || '실패');
                $btn.prop('disabled', false).html('<i class="fa fa-times"></i>');
            }
        },
        error: function() {
            alert('서버 오류');
            $btn.prop('disabled', false).html('<i class="fa fa-times"></i>');
        }
    });
}

// ── 전체 세션 강제종료 ──
function kickAllSessions(email) {
    if (!confirm('이 사용자의 모든 활성 세션을 강제종료하시겠습니까?\n(실제 VPN 서버에서 연결을 끊습니다)')) return;
    var $btn = $('#btn-kick-all');
    $btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> 처리중...');

    // 모든 활성 세션의 radacctid를 수집
    var cards = $('[id^="sess-card-"]');
    var ids = [];
    cards.each(function() {
        var id = $(this).attr('id').replace('sess-card-', '');
        ids.push(id);
    });

    var done = 0, success = 0, total = ids.length;
    if (total === 0) { $btn.html('완료'); return; }

    ids.forEach(function(rid) {
        $.ajax({
            url: '/api/v1/delete/disconnect_nas',
            type: 'POST',
            data: { radacctid: rid, email: email, csrfmiddlewaretoken: csrf_token },
            success: function(res) {
                if (res.result === 200) {
                    success++;
                    $('#sess-card-' + rid).css({opacity: '0.3', pointerEvents: 'none'});
                }
            },
            complete: function() {
                done++;
                if (done >= total) {
                    $btn.html('<i class="fa fa-check"></i> ' + success + '/' + total + '건 완료').css('background', '#28a745');
                }
            }
        });
    });
}
