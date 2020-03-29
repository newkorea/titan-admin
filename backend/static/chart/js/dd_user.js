/* 주소 설정 */
var url = "/api/v1/read/dd_user_chart"

set_selectbox();

/* 검색필터 현재날짜로 변경 */
function set_selectbox(){
  var now = new Date();
  var year = now.getFullYear();
  var month = now.getMonth()+1;

  console.log("year => ", year)
  console.log("month => ", month);

  $("#year_selectbox").val(year);
  $("#month_selectbox").val(month);
}