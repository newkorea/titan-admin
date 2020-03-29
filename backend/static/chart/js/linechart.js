/* 차트의 x축과 y축 변수 선언 */
var x_axis = [];
var y_axis = [];

reload_data(url);


function reload_data(url){
  var filter_datas = new Array();
  $(".form-control option:selected").each(function(){
    filter_datas.push(this.value);
  });
  line_chart(url, filter_datas);
}


/* 라인차트를 그려주는 함수 (매개변수로 url과 검색필터 데이터를 받는다)*/
function line_chart(url, filter_datas){
  var csrf_token = $('#csrf_token').html();
  $.post( url, {
      csrfmiddlewaretoken: csrf_token,
      filter_datas: filter_datas,
  })
  .done(function( data ) {
    x_axis = data.x_axis;
    y_axis = data.y_axis;

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

function click_search(){
  reload_data(url);
}