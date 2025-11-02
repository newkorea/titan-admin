var csrf_token = $('#csrf_token').html();
var endpoint = $('#endpoint').val();
var param = {
    csrfmiddlewaretoken: csrf_token
}

destroy_chart('chart_box', 'userChart');
draw_chart('userChart', endpoint, param, 'bar');