function common_save(flag){

  console.log('flag -> ', flag);

  try {
    var upload_file = $("#" + flag)[0].files[0];
  }
  catch (e){
    var upload_file = $("#" + flag).val();
  }

  console.log('upload_file -> ', upload_file);

  var formData = new FormData();
  formData.append("csrfmiddlewaretoken", $('#csrf_token').html());
  formData.append("upload_file", upload_file);
  formData.append("flag", flag);

  $.ajax({
    url: '/api_download',
    processData: false,
    contentType: false,
    data: formData,
    type: 'POST',
    success: function(data){
      if(data.result == 200){
        alert('업데이트 완료! \n상태관리를 확인해주세요');
        load_data();
      }
      else{
        alert('서버오류 - 관리자에게 문의하세요');
      }
    }
  });
}

function load_data(){
  var version = $('#version_check').val();

  console.log('version -> ', version);

  $.post( "/api_load_download_data", {
     version: version,
     csrfmiddlewaretoken: $('#csrf_token').html()
   })
  .done(function( data ) {
    for(var i=0; i<data.result.length; i++){
      if(data.result[i]['language'] == 'ko'){
        $('#top_ko').html(data.result[i]['client_name']);
        $('#bot_ko').html(data.result[i]['image_name']);
      }
      if(data.result[i]['language'] == 'en'){
        $('#top_en').html(data.result[i]['client_name']);
        $('#bot_en').html(data.result[i]['image_name']);
      }
      if(data.result[i]['language'] == 'zh'){
        $('#top_zh').html(data.result[i]['client_name']);
        $('#bot_zh').html(data.result[i]['image_name']);
      }
      if(data.result[i]['language'] == 'ja'){
        $('#top_ja').html(data.result[i]['client_name']);
        $('#bot_ja').html(data.result[i]['image_name']);
      }
    }
    console.log(data.result)
  });
}

$( document ).ready(function() {
    load_data();
});
