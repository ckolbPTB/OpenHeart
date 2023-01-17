$(document).ready(function() {
	$('#form_upload_zip').on('submit', function(event) {
		event.preventDefault();
		var formData = new FormData($('form')[0]);
		if(document.getElementById('zipFile').files.length == 0) {
            $('#zipFileMsg').html('No file selected!');
            return;
        }
        var filename = document.getElementById('zipFile').files.item(0).name;
        var fileExt = filename.split('.').pop();
        if(fileExt != 'zip') {
            $('#zipFileMsg').html('Selected file is not a zip file!');
            return;
        }

        $('#zipFileMsg').html('');

		$.ajax({
			xhr : function() {
				var xhr = new window.XMLHttpRequest();
				xhr.upload.addEventListener('progress', function(e) {
					if (e.lengthComputable) {
						var percent = Math.round((e.loaded / e.total) * 100);
						$('#progress_upload_zip').attr('aria-valuenow', percent).css('width', percent + '%').text(percent + '%');
					}
				});
				return xhr;
			},
			type : 'POST',
			url : '/upload/uploader',
			data : formData,
			processData : false,
			contentType : false,
            failure: function (response) {
                alert(response.d);
            }
		});
	});
});