define(['jquery', 'inheritance', 'ajaxify', 'bind', 'jquery.fileupload', 'typeahead',
        'sprintf', 'bootstrap/popover', 'domReady!'], function($, inheritance, ajaxify) {

    var instance = null;

    var Upload = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Upload allowed!');
            }

            var that = this;

            // "upload session" used by backend to not cause conflicts between
            // different tabs and such.
            that.session = Math.floor(Math.random() * 1000);

            that.parallelUploads = 4;
            that.activeUploads = 0;
            that.archives = ['application/zip', 'application/rar', 'application/x-rar'];
            that.audio = ['audio/flac', 'audio/mp3', 'audio/x-ms-wma', 'audio/mp4a-latm',
                'audio/ogg', 'audio/x-ape', 'audio/x-musepack', 'audio/wav', 'audio/mpeg', 'audio/mp4'];

            this.files = [];
            this.names = [];

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

                        var file = this;

                        var fileDom = $("#fileupload .files .tmpl").clone().removeClass("tmpl").data('file', file);

                        fileDom.find('.filename').text(file.name);

                        fileDom.find('.file-remove').click(function () {
                            var tr = $(this).closest("tr");

                            var file = tr.data("file");
                            var index = 0;

                            for (var otherIndex in that.files) {
                                var otherFile = that.files[otherIndex].file;

                                if (file === otherFile) {
                                    break;
                                }

                                index++;
                            }

                            that.files.splice(index, 1);

                            tr.remove();

                            return false;
                        });

                        if (that.archives.indexOf(file.type) != -1) {
                            fileDom.find('[name=archive_password]').show();
                            fileDom.addClass('archive-file');
                        } else if (that.audio.indexOf(file.type) != -1) {
                            fileDom.addClass('audio-file');

                            that.names.push($(fileDom).data('file').name);

                            $("#fileupload .files > .other-file:visible").each(function () {
                                var audioFile = $(this).find('[name=audio_file]');

                                var value = audioFile.val();

                                if (value === '') {
                                    audioFile.val(file.name);
                                }

                                audioFile.typeahead('destroy');
                                audioFile.typeahead({
                                    local: that.names
                                });
                            });
                        } else {
                            var audioFile = fileDom.find('[name=audio_file]');

                            var prevFile = $("#fileupload .files > .audio-file:visible").eq(-1).data('file');

                            if (typeof prevFile != 'undefined' && prevFile !== null) {
                                audioFile.val(prevFile.name);
                            }

                            fileDom.addClass('other-file');

                            audioFile.show();

                            audioFile.typeahead('destroy');
                            audioFile.typeahead({
                                local: that.names
                            });
                        }


                        $("#fileupload .files").append(fileDom);

                        that.files.push({
                            file: file,
                            dom: fileDom
                        });
                    });
                },
                progress: function (event, data) {
                    var progress = parseInt((data.loaded / data.total) * 100, 10);

                    $(data.fileDom).find('.progress').addClass('active').find('.progress-bar').eq(0).css(
                        'width',
                        progress + '%'
                    );
                }
            });

            $('#fileupload .start').click(function (event) {
                $("#upload .uploaded .tracks").contents().remove();
                $("#upload .uploaded .messages").contents().remove();

                that.send(true);

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
                    ajaxify.setPage('/library/edit/' + ids.join(','));
                }

                return false;
            });
        },
        send: function (start) {
            var that = this;

            var count = null;

            // we start with 1 and when that's finished we use parallelUploads
            // the reason is we need to know that the first one is done before
            // running the subsequent ones because we do some init stuff in that
            // one.
            if (typeof start != 'undefined' && start) {
                start = true;
                count = 1;
            } else {
                start = false;
                count = that.parallelUploads - that.activeUploads;
            }

            that.names = [];

            for (var index = 0; index < count; index++) {

                if (index >= that.files.length) {
                    break;
                }

                var file = that.files.splice(0, 1)[0];

                var archivePassword = $(file.dom).find('[name=archive_password]').val();
                var audioFile = $(file.dom).find('[name=audio_file]').val();

                var url = sprintf("%s?archive_password=%s&audio_file=%s&start=%s&session=%d",
                    $("#fileupload").attr("action"), encodeURIComponent(archivePassword), encodeURIComponent(audioFile),
                    start ? "true" : "false", that.session);

                that.activeUploads++;

                (function (file) {
                    $('#fileupload').fileupload('send', { files: file.file, url: url, fileDom: file.dom })
                        .success(function (result, textStatus, jqXHR) {
                            that.activeUploads--;

                            $(file.dom).remove();

                            var resultDom = $(result);

                            ajaxify.load(resultDom);

                            var tracks = $("#upload .uploaded .tracks");

                            tracks.contents().remove();

                            tracks.append(
                                resultDom.find('.tracks-hierarchy')
                            );

                            $("#upload .uploaded .messages").append(
                                resultDom.find('.message')
                            );

                            that.send();
                        }).error(function (jqXHR, textStatus, errorThrown) {
                            that.activeUploads--;

                            $(file.dom).addClass("danger").find(".progress-bar")
                                .removeClass("progress-bar-success").addClass("progress-bar-danger");

                            $(file.dom).popover({
                                html: true,
                                trigger: "hover",
                                placement: 'bottom',
                                container: "#upload",
                                title: sprintf("Error occured while uploading <strong>%s</strong>.", file.file.name),
                                content: $(jqXHR.responseText).find("#content").contents()
                            });

                            that.send();
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
