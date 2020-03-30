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
                datasets: y_axis
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
                        }
					}]
				}
            }
        });
    })
}


