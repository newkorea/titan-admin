$(document).ready( function () {
  $('#dtable').DataTable({
    "order": [[ 0, 'desc' ]],
    "language": {
      "info": "",
      "paginate": {
        "first": "First",
        "last": "Last",
        "previous": "Prev",
        "next": "Next"
      }
    },
  });
  $('.dataTables_length').hide();
  $('#dtable_filter').hide();
});
