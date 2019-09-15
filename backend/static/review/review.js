
  var csrf_token = $('#csrf_token').html();
  var app = new Vue({
    el: '#vue',
    delimiters: ['[[', ']]'],
    created () {
      $.post( "/api_review_read", {
            csrfmiddlewaretoken: csrf_token,
            language: this.language,
        })
        .done(function( data ) {
            app.items = data.result;
            app.loadItem();
        });
    },
    data: {
      tests : [
          { value: 1, text: '★☆☆☆☆' },
          { value: 2, text: '★★☆☆☆' },
          { value: 3, text: '★★★☆☆' },
          { value: 4, text: '★★★★☆' },
          { value: 5, text: '★★★★★' },
      ],
      items: [],
      language: 'en'
    },
    methods: {
      // 언어 선택(state update) 및 내용 로드(based state)
      selectLanguage: function(e){
        var language = e.currentTarget.value;
        this.language = language;

        this.loadItem();
      },
      // 내용 로드(based state)
      loadItem: function(){
          vStar = new Array();
          var nId = 0;
          $.ajax({
              url: "/api_review_read",
              type: "POST",
              async: false, // ture: 비동기, false: 동기
              data: {
                  csrfmiddlewaretoken: csrf_token,
                  language: this.language,
              },
              dataType: "json",
              success: function(data){
                  app.items = data.result;
                  for(var i = 0; i<data.result.length; i++){
                      nId++;
                      vStar[i] = data.result[i].star;
                      $('#'+nId).find('select[id=starbox]').val(vStar[i]).prop("selected", "selected");
                  }
              }
          });
      },
      // 아이템 삭제 후 내용 로드(based state)
      deleteItem: function(seq){
        var seq = seq[0][0];
        $.post( "/api_review_del", {
            csrfmiddlewaretoken: csrf_token,
            seq: seq,
        })
        .done(function( data ) {
            if (data.result == '200') {
                Swal.fire({
                    title: '삭제완료',
                    text: '정상적으로 삭제되었습니다.',
                    type: 'success',
                    confirmButtonColor: swalColor('error')
                })
                app.loadItem();
            }
        });
      },
      addItem: function(){
          if(this.items.length == 6){
              Swal.fire({
                  title: '알림',
                  text: '리뷰추가는 6개까지 가능합니다.',
                  type: 'error',
                  confirmButtonColor: swalColor('error')
              });
              return 0;
          }
          $.ajax({
              url: "/api_review_count",
              type: "POST",
              async: false, // ture: 비동기, false: 동기
              data: {
                  csrfmiddlewaretoken: csrf_token,
                  language: this.language,
              },
              dataType: "json",
              success: function(data){
                  length = data.result;
              }
          });
          if(length < this.items.length){
              Swal.fire({
                  title: '알림',
                  text: '기존에 작성하던 리뷰를 저장 후에 추가해주세요.',
                  type: 'error',
                  confirmButtonColor: swalColor('error')
              });
              return 0;
          }

        var tmp = {
          content: '',
          id: 0,
          idx: this.items.length + 1,
          star: 1,
          username: ''
        }

        this.items.push(tmp);

      },
      // 내용 업데이트 및 삽입
      saveItem: function(seq, idx){
        var seq = seq[0][0];
        var language = this.language;
        var starbox = $('#'+idx).find('#starbox option:selected').val();
        if(starbox == '★☆☆☆☆')
            starbox = '1';
        else if(starbox == '★★☆☆☆')
            starbox = '2';
        else if(starbox == '★★★☆☆')
            starbox = '3';
        else if(starbox == '★★★★☆')
            starbox = '4';
        else if(starbox == '★★★★★')
            starbox = '5';

        var username = $('#'+idx).find('input[name=username]').val();
        var content = $('#'+idx).find('textarea[name=content]').val();
        if(username == ''){
            $('#'+idx).find('input[name=username]').focus();
            return 0;
          }
       if(content == ''){
           $('#'+idx).find('textarea[name=content]').focus();
           return 0;
       }
        $.post( "/api_review_save", {
            csrfmiddlewaretoken: csrf_token,
            seq: seq,
            username: username,
            content: content,
            starbox: starbox,
            language: language,
        })
        .done(function( data ) {
            if (data.result == '200') {
                Swal.fire({
                    title: '저장완료',
                    text: '정상적으로 저장되었습니다.',
                    type: 'success',
                    confirmButtonColor: "#22b66e"
                }).then(function (result) {
                        if (result.value) {
                            app.loadItem();
                        }
                    }
                )
            }
        });

      },
    }
  })
