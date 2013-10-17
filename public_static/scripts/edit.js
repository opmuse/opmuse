define(['jquery', 'inheritance', 'ajaxify', 'typeahead', 'sprintf', 'domReady!'], function($, inheritance, ajaxify) {
    var instance = null;

    var Edit = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Edit allowed!');
            }

            var that = this;

            $('#main').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        initTypeahead: function () {
            this.createTypeahead("artist");
            this.createTypeahead("album");
            this.createTypeahead("track");
        },
        createTypeahead: function (type) {
            $(sprintf("#edit input[name=%ss]", type)).typeahead('destroy');
            $(sprintf("#edit input[name=%ss]:not(.locked)", type)).each(function () {
                var input = this;

                $(input).typeahead({
                    remote: {
                        url: sprintf('/library/search/api/%s?query=%%QUERY', type),
                        filter: function (parsedResponse) {
                            var originalValue = $(input).data('originalValue');
                            var index = parsedResponse.indexOf(originalValue);

                            if (index != -1) {
                                parsedResponse.splice(index, 1);
                            }

                            return parsedResponse;
                        }
                    }
                });
            });
        },
        internalInit: function () {
            var that = this;

            that.initTypeahead();

            $("#edit form button").click(function (event) {
                var form = $(this).closest('form');
                var data = $(form).serialize();

                // serialize the button too..
                var name = $(this).attr('name');

                if (typeof name != 'undefined' && name !== null) {
                    data += "&" + name + "=" + name;
                }

                $.ajax($(form).attr('action'), {
                    type: 'post',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    data: data,
                    success: function (data) {
                        ajaxify.setPageInDom(data);
                    },
                    error: function (xhr) {
                        ajaxify.setErrorPageInDom(xhr.responseText);
                    }
                });

                return false;
            });

            $("#edit .lock").unbind('click.ajaxify')
                .unbind('click.edit')
                .bind('click.edit',
                    function (event) {
                        var type = null;

                        if ($(this).is(".album")) {
                            type = 'album';
                        } else if ($(this).is(".artist")) {
                            type = 'artist';
                        } else if ($(this).is(".date")) {
                            type = 'date';
                        } else if ($(this).is(".disc")) {
                            type = 'disc';
                        }

                        var selector = "#edit input." + type;

                        if ($(this).hasClass('locked')) {
                            $(selector)
                                .removeAttr("readonly")
                                .unbind('keyup.lock, blur.lock')
                                .removeClass('locked');

                            $(this).removeClass('locked');
                        } else {
                            $(selector).addClass('locked');
                            $(this).addClass('locked');

                            $($(selector).attr("readonly", "readonly").get(0))
                                .removeAttr("readonly").removeClass("locked")
                                .bind('keyup.lock, blur.lock',
                                    function (event) {
                                        $(selector).val($(this).val());
                                    }
                                ).blur();
                        }

                        that.initTypeahead();

                        return false;
                    }
                );

                $("#edit input").unbind('focus.marker').bind('focus.marker', function (event) {
                    $("#edit tr").removeClass("active");
                    $(this).closest("tr").addClass("active");
                });
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Edit();
        }

        return instance;
    })();

});

