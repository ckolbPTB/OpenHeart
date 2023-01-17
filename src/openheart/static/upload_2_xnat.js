$(document).ready(function() {
	$('#form_upload_2_xnat345').on('submit', function(event) {
		event.preventDefault();
		var formData = new FormData($('form')[0]);
		$.ajax({
			xhr : function() {
				var xhr = new window.XMLHttpRequest();
				xhr.upload.addEventListener('progress', function(e) {
					if (e.lengthComputable) {
						var percent = Math.round((e.loaded / e.total) * 100);
						$('#progress_upload_2_xnat').attr('aria-valuenow', percent).css('width', percent + '%').text(percent + '%');
					}
				});
				return xhr;
			},
			type : 'POST',
			url : '/upload/check',
			data : formData,
			processData : false,
			contentType : false,
			success: function (response) {
                    window.location = "check";
            },
            failure: function (response) {
                alert(response.d);
            }
		});
	});
});