define(['jquery', 'inheritance', 'ajaxify', 'bind', 'jquery.fileupload', 'domReady!'], function($, inheritance, ajaxify) {

    var instance = null;

    var Upload = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Upload allowed!');
            }

            var that = this;

            that.parallelUploads = 2;
            that.activeUploads = 0;
            that.archives = ['application/zip', 'application/rar', 'application/x-rar'];

            this.files = [];

            $('#main').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            var that = this;

            if ($('#fileupload').data('initialized')) {
                return;
            }

            $('#fileupload').data('initialized', true);

            $('#fileupload').fileupload({
                multipart: false,
                add: function (event, data) {
                    $.each(data.files, function () {

                        var fileDom = $("#fileupload .files .tmpl").clone().removeClass("tmpl");
                        fileDom.find('.filename').text(this.name);

                        if (that.archives.indexOf(this.type) != -1) {
                            fileDom.find('[name=archive_password]').show();
                        }

                        $("#fileupload .files").append(fileDom);

                        that.files.push({
                            file: this,
                            dom: fileDom
                        });
                    });
                },
                progress: function (event, data) {
                    var progress = parseInt((data.loaded / data.total) * 100, 10);

                    $(data.fileDom).find('.progress').addClass('active').find('.bar').eq(0).css(
                        'width',
                        progress + '%'
                    );
                }
            });

            $('#fileupload .start').click(function (event) {
                $("#upload .uploaded .tracks .track").remove();
                $("#upload .uploaded .messages .message").remove();
                that.send();
                return false;
            });

            $("#fileupload .edit-invalid").click(function (event) {
                var ids = [];

                $(".uploaded .tracks .track").each(function () {
                    var invalid = $(this).data('track-invalid');
                    var id = $(this).data('track-id');

                    if (invalid !== null) {
                        ids.push(id);
                    }
                });

                if (ids.length > 0) {
                    ajaxify.setPage('/tag/' + ids.join(','));
                }

                return false;
            });
        },
        send: function () {
            var that = this;

            var count = that.parallelUploads - that.activeUploads;

            for (var index = 0; index < count; index++) {

                if (index >= that.files.length) {
                    break;
                }

                var file = that.files.splice(0, 1)[0];

                var archivePassword = $(file.dom).find('[name=archive_password]').val();

                var url = $("#fileupload").attr("action") + "?archive_password=" + archivePassword;

                that.activeUploads++;

                (function (file) {
                    $('#fileupload').fileupload('send', { files: file.file, url: url, fileDom: file.dom })
                        .success(function (result, textStatus, jqXHR) {
                            that.activeUploads--;

                            $(file.dom).remove();

                            var resultDom = $(result);

                            ajaxify.load(resultDom);

                            $("#upload .uploaded .tracks").append(
                                resultDom.find('.track')
                            );

                            $("#upload .uploaded .messages").append(
                                resultDom.find('.message')
                            );

                            that.send();
                        }).error(function (jqXHR, textStatus, errorThrown) {
                            that.activeUploads--;
                            ajaxify.setErrorPageInDom(jqXHR.responseText);
                        });
                })(file);
            }
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Upload();
        }

        return instance;
    })();
});
