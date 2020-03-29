// 기본 값 설정
function set_selectbox(){
  var now = new Date();
  var year = now.getFullYear();
  var month = now.getMonth()+1;
  $("#year_selectbox").val(year);
  $("#month_selectbox").val(month);
}

// 검색하기 클릭 시
function click_search(){
    var csrf_token = $('#csrf_token').html();
    var year = $('#year_selectbox').val();
    var month = $('#month_selectbox').val();
    var param = {
        csrfmiddlewaretoken: csrf_token,
        year: year,
        month: month
    }
    destroy_chart('chart_box', 'userChart');
    draw_chart('userChart', '/api/v1/read/dd_user_chart', param);
}

// 초기화 영역
set_selectbox();
click_search();
