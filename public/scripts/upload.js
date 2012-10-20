define(['jquery', 'inheritance', 'ajaxify', 'bind', 'jquery.fileupload', 'domReady!'], function($, inheritance, ajaxify) {

    var instance = null;

    var Upload = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Upload allowed!');
            }

            var that = this;

            $('#content').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            this.files = [];
        },
        internalInit: function () {
            var that = this;

            $('#fileupload').fileupload({
                multipart: false,
                add: function (e, data) {
                    $.each(data.files, function () {

                        var fileDom = $("#fileupload .files .tmpl").clone().removeClass("tmpl");
                        fileDom.find('.filename').text(this.name);

                        $("#fileupload .files").append(fileDom);

                        that.files.push({
                            file: this,
                            dom: fileDom
                        });
                    });
                }
            });

            $('#fileupload .start').click(function (event) {
                that.send();
                return false;
            });
        },
        send: function () {
            var that = this;

            if (that.files.length > 0) {
                var file = that.files[0];

                $('#fileupload').fileupload('send', { files: file.file })
                    .success(function (result, textStatus, jqXHR) {
                        $(file.dom).remove();
                        that.files.splice(0, 1);

                        var resultDom = $(result);

                        ajaxify.load(resultDom);

                        $("#upload .uploaded .tracks").append(
                            resultDom.find('.track')
                        );

                        $("#upload .uploaded .messages").append(
                            resultDom.find('.message')
                        );

                        that.send();
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
