var regist_today_dt = $('#regist_today_dt').html();
var login_today_dt = $('#login_today_dt').html();
var profit_dt = $('#profit_dt').html();
var refund_dt = $('#refund_dt').html();
var user_count_dt = $('#user_count_dt').html();
var admin_count_dt = $('#admin_count_dt').html();
var cs_count_dt = $('#cs_count_dt').html();
var chongpan_count_dt = $('#chongpan_count_dt').html();
var active_count_dt = $('#active_count_dt').html();
var deactive_count_dt = $('#deactive_count_dt').html();
var delete_count_dt = $('#delete_count_dt').html();
var black_count_dt = $('#black_count_dt').html();


var options = {
  useEasing : true,
  useGrouping : true,
  separator : ',',
  decimal : '.',
  prefix: '',
};

var regist_user_today = new CountUp("regist_user_today", 0, regist_today_dt, 0, 2.5, options);
regist_user_today.start();
var login_today = new CountUp("login_today", 0, login_today_dt, 0, 2.5, options);
login_today.start();
var profit = new CountUp("profit", 0, profit_dt, 0, 2.5, options);
profit.start();
var refund = new CountUp("refund", 0, refund_dt, 0, 2.5, options);
refund.start();
var user_count = new CountUp("user_count", 0, user_count_dt, 0, 2.5, options);
user_count.start();
var admin_count = new CountUp("admin_count", 0, admin_count_dt, 0, 2.5, options);
admin_count.start();
var cs_count = new CountUp("cs_count", 0, cs_count_dt, 0, 2.5, options);
cs_count.start();
var chongpan_count = new CountUp("chongpan_count", 0, chongpan_count_dt, 0, 2.5, options);
chongpan_count.start();
var active_count = new CountUp("active_count", 0, active_count_dt, 0, 2.5, options);
active_count.start();
var deactive_count = new CountUp("deactive_count", 0, deactive_count_dt, 0, 2.5, options);
deactive_count.start();
var delete_count = new CountUp("delete_count", 0, delete_count_dt, 0, 2.5, options);
delete_count.start();
var black_count = new CountUp("black_count", 0, black_count_dt, 0, 2.5, options);
black_count.start();


var ctx = document.getElementById("myChart");
var ctx2 = document.getElementById("myChart2");
var myChart = new Chart(ctx, {
    type: 'bar',
    data: {
        labels: ["남자", "여자"],
        datasets: [
            {
                label: ["성별 별 가입자 수"],
                data: [${ men }, ${female}],
                backgroundColor: [
                    'rgba(255, 99, 132, 0.7)',
                    'rgba(54, 162, 235, 0.7)',
                ],
                borderColor: [
                    'rgba(255,99,132,1)',
                    'rgba(54, 162, 235, 1)',
                ],
                borderWidth: 1
            },
        ]
    },
    options: {
        scales: {
            yAxes: [{
                ticks: {
                    beginAtZero:true
                }
            }]
        },
        legend: {
            display: false
        },
        tooltips: {
            callbacks: {
               label: function(tooltipItem) {
                      return tooltipItem.xLabel;
               }
            }
        }
    }
});

var myChart2 = new Chart(ctx2, {
    type: 'bar',
    data: {
        labels: ["10대", "20대", "30대", "40대", "50대", "60대", "70대", "80대", "기타"],
        datasets: [
            {
                label: ["나이 별 가입자 수"],
                data: ${ ages },
                backgroundColor: [
                    'rgba(153, 102, 255, 0.7)',
                      'rgba(75, 192, 192, 0.7)',
                    'rgba(255, 99, 132, 0.7)',
                      'rgba(54, 162, 235, 0.7)',
                      'rgba(255, 206, 86, 0.7)',
                      'rgba(255, 159, 64, 0.7)'
                ],
                borderColor: [
                    'rgba(153, 102, 255, 1)',
                    'rgba(75, 192, 192, 1)',
                    'rgba(255,99,132,1)',
                    'rgba(54, 162, 235, 1)',
                    'rgba(255, 206, 86, 1)',
                    'rgba(255, 159, 64, 1)'
                ],
                borderWidth: 1
            },
        ]
    },
    options: {
        scales: {
            yAxes: [{
                ticks: {
                    beginAtZero:true
                }
            }]
        },
        legend: {
            display: false
        },
        tooltips: {
            callbacks: {
               label: function(tooltipItem) {
                      return tooltipItem.xLabel;
               }
            }
        }
    }
});
