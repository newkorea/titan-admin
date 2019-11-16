var csrf_token = $('#csrf_token').html();
var app = new Vue({
  el: '#vue',
  delimiters: ['[[', ']]'],
  created () {
    $.post( "/api_dealer_read", {
       csrfmiddlewaretoken: $('#csrf_token').html(),
       year: $('#filter_year').val()
     })
    .done(function( data ) {
      app.items = data.result;
      app.amount_krw = data.amount_krw;
      app.amount_usd = data.amount_usd;
      app.amount_cny = data.amount_cny;
    });
  },
  data: {
    items: [],
    sum_amount: 0,
  },
  methods: {
    click_search: function(){
      $.post( "/api_dealer_read", {
         csrfmiddlewaretoken: $('#csrf_token').html(),
         year: $('#filter_year').val()
       })
      .done(function( data ) {
        app.items = data.result;
        app.amount_krw = data.amount_krw;
        app.amount_usd = data.amount_usd;
        app.amount_cny = data.amount_cny;
      });
    }
  }
})
