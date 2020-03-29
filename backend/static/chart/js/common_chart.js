function destroy_chart(box_id, chart_id){
    $('#' + box_id).html(''); // this is my <canvas> element
    $('#' + box_id).append('<canvas id="' + chart_id + '" height="450" width="1500"></canvas>');
}

function draw_chart(id, url, param){
    $.post( url, param)
    .done(function( data ) {
        var x_axis = data.x_axis;
        var y_axis = data.y_axis;
        var ctx = document.getElementById(id).getContext('2d');
        var myChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: x_axis,
                datasets: [
                    {
                        label: '가입자',
                        data: y_axis.regist,
                        backgroundColor: 'rgba(255, 99, 132, 0.2)',
                        borderColor: 'rgba(255, 99, 132, 1)',
                        borderWidth: 1
                    },
                    {
                        label: '활성화',
                        data: y_axis.active,
                        backgroundColor: 'rgba(0, 123, 255, 0.2)',
                        borderColor: 'rgba(0, 123, 255, 1)',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
				title: {
					display: false,
					text: '#'
				},
				tooltips: {
					mode: 'index',
					intersect: false,
				},
				hover: {
					mode: 'nearest',
					intersect: true
				},
                elements: {
                     line: {
                          fill: false 
                    } 
                },
				scales: {
					xAxes: [{
						display: true,
						scaleLabel: {
							display: true,
							labelString: '월'
						}
					}],
					yAxes: [{
						display: true,
						scaleLabel: {
							display: true,
							labelString: '명'
						},
                        ticks: {
                            suggestedMin: 0,
                            suggestedMax: 10,
                            stepSize: 1
                        }
					}]
				}
            }
        });
    })
}


