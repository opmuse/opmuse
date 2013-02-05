define(['jquery', 'inheritance', 'ajaxify', 'bind', 'jquery.fileupload', 'domReady!'], function($, inheritance, ajaxify) {

    var instance = null;

    var Upload = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Upload allowed!');
            }

            var that = this;

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

                        if (['application/zip', 'application/rar'].indexOf(this.type) != -1) {
                            fileDom.find('[name=archive_password]').show();
                        }

                        $("#fileupload .files").append(fileDom);

                        that.files.push({
                            file: this,
                            dom: fileDom
                        });
                    });
                },
                progressall: function (event, data) {
                    var progress = parseInt((data.loaded / data.total) * 100, 10);

                    $('#fileupload .files tr:visible .progress').addClass('active').find('.bar').eq(0).css(
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

            if (that.files.length > 0) {
                var file = that.files[0];

                var archivePassword = $(file.dom).find('[name=archive_password]').val();

                var url = $("#fileupload").attr("action") + "?archive_password=" + archivePassword;

                $('#fileupload').fileupload('send', { files: file.file, url: url })
                    .success(function (result, textStatus, jqXHR) {
                        $(file.dom).remove();

                        var resultDom = $(result);

                        that.files.splice(0, 1);

                        ajaxify.load(resultDom);

                        $("#upload .uploaded .tracks").append(
                            resultDom.find('.track')
                        );

                        $("#upload .uploaded .messages").append(
                            resultDom.find('.message')
                        );

                        that.send();
                    }).error(function (jqXHR, textStatus, errorThrown) {
                        ajaxify.setErrorPageInDom(jqXHR.responseText);
                    });
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
