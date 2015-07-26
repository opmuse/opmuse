/*!
 * Copyright 2012-2015 Mattias Fliesberg
 *
 * This file is part of opmuse.
 *
 * opmuse is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * opmuse is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with opmuse.  If not, see <http://www.gnu.org/licenses/>.
 */

define([
        'jquery',
        'inheritance',
        'ajaxify',
        'jquery.fileupload',
        'typeahead',
        'sprintf',
        'bootstrap/popover',
        'domReady!'
    ], function ($, inheritance, ajaxify) {

    'use strict';

    var instance = null;

    var Upload = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Upload allowed!');
            }

            var that = this;

            // 'upload session' used by backend to not cause conflicts between
            // different tabs and such.
            that.session = Math.floor(Math.random() * 1000);

            that.parallelUploads = 4;
            that.activeUploads = 0;
            that.archives = ['application/zip', 'application/rar', 'application/x-rar'];
            that.audio = ['application/x-flac', 'audio/flac', 'audio/mp3', 'audio/x-ms-wma',
                'audio/mp4a-latm', 'audio/ogg', 'audio/x-ape', 'audio/x-musepack', 'audio/wav',
                'audio/mpeg', 'audio/mp4', 'audio/x-m4a'];

            this.files = [];
            this.names = [];

            $('#main').on('ajaxifyInit', function (event) {
                that.internalInit();
            });

            this.totalSize = 0;
            this.totalLoaded = 0;

            that.internalInit();
        },
        typeahead: function (input) {
            var that = this;

            var mySource = new Bloodhound({
                datumTokenizer: function (data) {
                    return Bloodhound.tokenizers.whitespace(data.name);
                },
                queryTokenizer: Bloodhound.tokenizers.whitespace,
                local: that.names
            });

            mySource.initialize();

            var dataSet = {
                displayKey: 'name',
                source: mySource.ttAdapter()
            };

            $(input).typeahead(null, dataSet);
        },
        internalInit: function () {
            var that = this;

            if ($('#fileupload').data('initialized')) {
                return;
            }

            $('#fileupload').data('initialized', true);

            $('#fileupload').fileupload({
                singleFileUploads: false,
                multipart: false,
                add: function (event, data) {
                    var files = [];

                    var artistNameFallback = sprintf('Unknown Artist %d', Math.floor(Math.random() * 1000));

                    $.each(data.files, function () {
                        var file = this;

                        var fileDom = $('#fileupload .files .tmpl').clone().removeClass('tmpl').data('file', file);

                        fileDom.data('artistNameFallback', artistNameFallback);

                        fileDom.find('.filename').text(file.name);

                        fileDom.find('.file-remove').click(function () {
                            var tr = $(this).closest('tr');

                            var file = tr.data('file');
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

                            files.unshift([fileDom, file]);
                        } else if (that.audio.indexOf(file.type) != -1) {
                            fileDom.addClass('audio-file');

                            that.names.push({'name': $(fileDom).data('file').name});

                            $('#fileupload .files > .other-file:visible').each(function () {
                                var audioFile = $(this).find('[name=audio_file]');

                                audioFile.typeahead('destroy');
                                that.typeahead(audioFile);
                            });

                            files.unshift([fileDom, file]);
                        } else {
                            var audioFile = fileDom.find('[name=audio_file]');

                            var prevFile = null;

                            $(data.files).each(function () {
                                var file = this;

                                if (that.audio.indexOf(file.type) != -1) {
                                    prevFile = file;
                                    return false;
                                }
                            });

                            if (prevFile !== null) {
                                audioFile.val(prevFile.name);
                            }

                            fileDom.addClass('other-file');

                            audioFile.show();

                            audioFile.typeahead('destroy');
                            that.typeahead(audioFile);

                            files.push([fileDom, file]);
                        }

                        that.totalSize += file.size;
                    });

                    for (var index in files) {
                        var file = files[index];

                        var fileDom = file[0];
                        file = file[1];

                        $('#fileupload .files').append(fileDom);

                        that.files.push({
                            file: file,
                            dom: fileDom
                        });
                    }
                },
                progress: function (event, data) {
                    var loaded = $(data.fileDom).data('loaded');

                    if (typeof loaded == 'undefined' || loaded === null) {
                        loaded = 0;
                    }

                    $(data.fileDom).data('loaded', data.loaded);

                    that.totalLoaded += data.loaded - loaded;

                    var progress = parseInt((data.loaded / data.total) * 100, 10);
                    var totalProgress = parseInt((that.totalLoaded / that.totalSize) * 100, 10);

                    $('.total-progress.progress').addClass('active').find('.progress-bar').eq(0).css(
                        'width',
                        totalProgress + '%'
                    );

                    $(data.fileDom).find('.progress').addClass('active').find('.progress-bar').eq(0).css(
                        'width',
                        progress + '%'
                    );
                }
            });

            $('#fileupload .start').click(function (event) {
                $('#upload .uploaded .tracks').contents().remove();
                $('#upload .uploaded .messages').contents().remove();

                that.send(true);

                return false;
            });

            $('#fileupload .edit-invalid').click(function (event) {
                var ids = [];

                $('.uploaded .tracks .track').each(function () {
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
        done: function () {
            this.totalSize = 0;
            this.totalLoaded = 0;

            setTimeout(function () {
                $('.total-progress.progress').removeClass('active').find('.progress-bar')
                    .eq(0).css('width', '0%');
            }, 3000);
        },
        send: function (start) {
            var that = this;

            // first start the session in the backend, then start the actual upload
            if (start === true) {
                $.ajax(sprintf('%s?session=%d', $('#fileupload').data('url-start'), that.session), {
                    success: function (data, textStatus, xhr) {
                        that.send();
                    },
                    error: function (xhr) {
                        $('.total-progress.progress').addClass('progress-bar-danger')
                        .popover({
                            html: true,
                            trigger: 'hover',
                            placement: 'bottom',
                            container: '#upload',
                            title: 'Error occured while starting upload.',
                            content: $(xhr.responseText).find('#content').contents()
                        });
                    }
                });

                return;
            }

            var count = that.parallelUploads - that.activeUploads;

            that.names.splice(0, that.names.length);

            for (var index = 0; index < count; index++) {
                if (index >= that.files.length) {
                    break;
                }

                var file = that.files.splice(0, 1)[0];

                var archivePassword = $(file.dom).find('[name=archive_password]').val();
                var audioFile = $(file.dom).find('[name=audio_file]').val();
                var artistNameFallback = $(file.dom).data('artistNameFallback');

                var url = sprintf('%s?archive_password=%s&audio_file=%s&session=%d&artist_name_fallback=%s',
                    $('#fileupload').attr('action'), encodeURIComponent(archivePassword),
                    encodeURIComponent(audioFile), that.session, encodeURIComponent(artistNameFallback));

                that.activeUploads++;

                var done = false;

                if (index == that.files.length - 1) {
                    done = true;
                }

                (function (file, done) {
                    $('#fileupload').fileupload('send', { files: file.file, url: url, fileDom: file.dom })
                        .success(function (result, textStatus, jqXHR) {
                            that.activeUploads--;

                            $(file.dom).remove();

                            var resultDom = $(result);

                            ajaxify.load(resultDom);

                            var tracks = $('#upload .uploaded .tracks');

                            tracks.contents().remove();

                            tracks.append(
                                resultDom.find('.tracks-hierarchy')
                            );

                            $('#upload .uploaded .messages').append(
                                resultDom.find('.message')
                            );

                            if (done) {
                                that.done();
                            } else {
                                that.send();
                            }
                        }).error(function (jqXHR, textStatus, errorThrown) {
                            that.activeUploads--;

                            $(file.dom).addClass('danger').find('.progress-bar')
                                .removeClass('progress-bar-success').addClass('progress-bar-danger');

                            $(file.dom).popover({
                                html: true,
                                trigger: 'hover',
                                placement: 'bottom',
                                container: '#upload',
                                title: sprintf('Error occured while uploading <strong>%s</strong>.', file.file.name),
                                content: $(jqXHR.responseText).find('#content').contents()
                            });

                            if (done) {
                                that.done();
                            } else {
                                that.send();
                            }
                        });
                })(file, done);
            }
        }
    });

    return (function () {
        if (instance === null) {
            instance = new Upload();
        }

        return instance;
    })();
});
