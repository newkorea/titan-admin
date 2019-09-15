var csrf_token = $('#csrf_token').html();
var app = new Vue({
    el: '#vue',
    delimiters: ['[[', ']]'],
    created () {
        var main_sel = $('#main_sel').val();
        var sub_sel = $('#sub_sel').val();
        var send_yn = $('#send_yn').val();
        var target_date = $('#target_date').val();

        // inject now
        Date.prototype.yyyymmdd = function() {
        var mm = this.getMonth() + 1;
        var dd = this.getDate();
        return [this.getFullYear(), '-', (mm>9 ? '' : '0') + mm, '-', (dd>9 ? '' : '0') + dd].join('');
        };
        var date = new Date();
        var now = date.yyyymmdd()
        console.log('now -> ', now);
        var target_date = now;

        console.log('--------------------------')
        console.log('main_sel -> ', main_sel);
        console.log('sub_sel -> ', sub_sel);
        console.log('send_yn -> ', send_yn);
        console.log('target_date -> ', target_date);
        console.log('--------------------------')

        $.post( "/api_support_getContent", {
            csrfmiddlewaretoken: csrf_token,
            main_sel: main_sel,
            sub_sel: sub_sel,
            send_yn: send_yn,
            target_date: target_date
        })
        .done(function( data ) {
            console.log('data.result -> ', data.result);
            app.items = data.result;
        })
    },
    data: {
        items: [],
        select_id: 0,
        select_store: {},
        send_yn: 'N'
    },
    methods: {
        allReset: function(){
            app.onChange();
        },
        selectItem: function(e){
            id = e.currentTarget.id;
            console.log('id -> ', id);

            this.select_id = id;

            $.post( "/api_support_getSelectContent", {
                csrfmiddlewaretoken: csrf_token,
                id: id
            })
            .done(function( data ) {
                console.log('data.result -> ', data.result);
                app.select_store = data.result;
            })
        },
        onChange: function(){
            var send_yn = $('#send_yn').val();
            this.send_yn = send_yn;
            this.select_id = 0;
            app.loadItem();
        },
        deleteItem: function(e){
            console.log('delete select -> ', e[0][0]);
            var id = e[0][0];
            Swal.fire({
                title: '알림',
                text: '정말로 삭제하시겠습니까?.',
                type: 'warning',
                confirmButtonColor: swalColor('warning'),
                showCancelButton: true,
                confirmButtonText: '삭제',
                cancelButtonText: "취소"
            }).then(function (result){
                if (result.value) {
                    $.post("/api_support_deleteItem", {
                        csrfmiddlewaretoken: csrf_token,
                        id: id,
                    })
                    .done(function (data) {
                        if (data.result == '200') {
                            Swal.fire({
                                title: '알림',
                                text: '성공적으로 삭제되었습니다.',
                                type: 'success',
                                confirmButtonColor: swalColor('success')
                            })
                            app.select_id = 0;
                            app.loadItem();
                        }
                    })

                }
            })
        },
        sendItem: function(e){
            var subject = $('.su-con-r').find('input[name=support_subject]').val();
            var content = $('.su-con-r').find('textarea[name=support_content]').val();
            var id = e[0][0];
            var email = e[0][1];

            if(content == ''){
                Swal.fire({
                    title: '알림',
                    text: '내용을 입력해주세요.',
                    type: 'error',
                    confirmButtonColor: swalColor('error')
                })
                return 0;
            }
            console.log('sendItem select -> ', e[0][0]);
            console.log('sendItem email -> ', email);
            console.log('content -> ', content);
            console.log('subject -> ', subject);

            Swal.fire({
                title: '알림',
                text: '문의를 처리하시겠습니까?',
                type: 'warning',
                confirmButtonColor: swalColor('warning'),
                showCancelButton: true,
                confirmButtonText: '처리',
                cancelButtonText: "취소"
            }).then(function (result) {
                if (result.value) {

                    $('#btn_send').hide();

                    $.post("/api_support_sendItem", {
                        csrfmiddlewaretoken: csrf_token,
                        id: id,
                        email: email,
                        subject: subject,
                        content: content,
                    })
                    .done(function (data) {
                        if (data.result == '200') {
                            Swal.fire({
                                title: '알림',
                                text: '성공적으로 문의가 처리되었습니다.',
                                type: 'success',
                                confirmButtonColor: swalColor('success')
                            })
                            app.select_id = 0;
                            app.loadItem();
                        }
                        else {
                            Swal.fire({
                                title: '알림',
                                text: '알 수 없는 오류발생 관리자에게 문의하세요.',
                                type: 'error',
                                confirmButtonColor: swalColor('error')
                            })
                        }
                    })

                }
            })
        },
        loadItem: function(){
            var main_sel = $('#main_sel').val();
            var sub_sel = $('#sub_sel').val();
            var send_yn = $('#send_yn').val();
            var target_date = $('#target_date').val();

            console.log('--------------------------')
            console.log('main_sel -> ', main_sel);
            console.log('sub_sel -> ', sub_sel);
            console.log('send_yn -> ', send_yn);
            console.log('target_date -> ', target_date);
            console.log('--------------------------')

            $.post( "/api_support_getContent", {
                csrfmiddlewaretoken: csrf_token,
                main_sel: main_sel,
                sub_sel: sub_sel,
                send_yn: send_yn,
                target_date: target_date
            })
            .done(function( data ) {
                console.log('data.result -> ', data.result);
                app.items = data.result;
            })
        }
    }
})

/*
$( function() {
    $( "#datetimepicker2" ).datepicker({
        dateFormat: 'yy-mm-dd',
        yearSuffix: "년",
        monthNamesShort: ['1','2','3','4','5','6','7','8','9','10','11','12'],
        monthNames: ['1월','2월','3월','4월','5월','6월','7월','8월','9월','10월','11월','12월'],
        dayNamesMin: ['일','월','화','수','목','금','토'],
        dayNames: ['일요일','월요일','화요일','수요일','목요일','금요일','토요일'],
        showMonthAfterYear: true
    });
} );
*/

function makeSubOption(group_code){
    var csrf_token = $('#csrf_token').html();
    $.post( "/api_support_getSubOption", {
         csrfmiddlewaretoken: csrf_token,
         group_code: group_code
    })
    .done(function( data ) {
        var r = data.result;

        $('#sub_sel').empty();

        console.log('r.length -> ', r.length);

        op_txt = "<option value='0'>전체</option>";
        $('#sub_sel').append(op_txt);
        for(var i=0; i<r.length; i++){
            op_txt = "<option value='"+r[i]['code']+"'>"+ r[i]['name'] +"</option>";
            $('#sub_sel').append(op_txt);
        }

    });
}

$( document ).ready(function() {
    // inject now
    Date.prototype.yyyymmdd = function() {
    var mm = this.getMonth() + 1;
    var dd = this.getDate();
    return [this.getFullYear(), '-', (mm>9 ? '' : '0') + mm, '-', (dd>9 ? '' : '0') + dd].join('');
    };
    var date = new Date();
    var now = date.yyyymmdd()
    console.log('now -> ', now);
    $('#target_date').val(now);

    var value = $('#main_sel').val();
    makeSubOption(value);

    /*
    $('.summernote').summernote({
        height: 300,
        lang: 'ko-KR',
        popover: {
            image: [],
            link: [],
            air: []
        },
    });
    */
});

$('#main_sel').change(function() {
    var value = $(this).val();
    console.log('hello -> ', value);

    makeSubOption(value);
});

function imgViewer(img){
    console.log('img -> ', img);
    img1= new Image();
    img1.src=(img);
    imgControll(img);
}
function imgControll(img){
    if((img1.width!=0)&&(img1.height!=0)){
    viewImage(img);
    }
    else{
    controller="imgControll('"+img+"')";
    intervalID=setTimeout(controller,20);
    }
}
function viewImage(img){
    W=img1.width;
    H=img1.height;
    O="width="+W+",height="+H+",scrollbars=yes";
    imgWin=window.open("","",O);
    imgWin.document.write("<html><head><title>kmooc image viewer</title></head>");
    imgWin.document.write("<body topmargin=0 leftmargin=0>");
    imgWin.document.write("<img src="+img+" onclick='self.close()' style='cursor:pointer;' title='클릭 시 창이 닫힙니다.'>");
    imgWin.document.close();
}
