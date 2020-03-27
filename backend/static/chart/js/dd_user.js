/* 차트의 x축과 y축 변수 선언 */
var x_axis = [];
var y_axis = [];

/* 현재 월 구하기 */
var now = new Date();
var month = now.getMonth() + 1;
  
  
read_dd_user_chart(month);


function reload_data(){
  var selected_val = $("#month_selectbox option:selected").val();
  month = selected_val;
  read_dd_user_chart(month);
}



function read_dd_user_chart(month){
  var csrf_token = $('#csrf_token').html();
  $.post( "api/v1/read/dd_user_chart", {
      csrfmiddlewaretoken: csrf_token,
      month: month,
  })
  .done(function( data ) {
    /* 특정 달의 일을 x축에 사용자 수는 y축에 넣는다. */
    x_axis = data.list_day;
    y_axis = data.list_value;
    var chart_data = {
      labels: x_axis,
      datasets: [
          {
              label: "My Second dataset",
              fillColor: "rgba(151,187,205,0.2)",
              strokeColor: "rgba(151,187,205,1)",
              pointColor: "rgba(151,187,205,1)",
              pointStrokeColor: "#fff",
              pointHighlightFill: "#fff",
              pointHighlightStroke: "rgba(151,187,205,1)",
              data: y_axis
          }
      ]
  };

  if(window.myLineChart != null){
    window.myLineChart.destroy();
  }
  var ctx = document.getElementById("lineChart").getContext("2d");
  var options = {};
  
  window.myLineChart = new Chart(ctx).Line(chart_data, options);
  });
}