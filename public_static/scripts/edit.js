define(['jquery', 'inheritance', 'ajaxify', 'domReady!'], function($, inheritance, ajaxify) {
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
        internalInit: function () {
            var that = this;

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

                        var selector = "#edit input." + type + ":not(.lock)";

                        if ($(this).hasClass('locked')) {
                            $(selector)
                                .removeAttr("readonly")
                                .unbind('keyup.lock, blur.lock');

                            $(this).removeClass('locked');
                        } else {
                            $($(selector).attr("readonly", "readonly").get(0)).removeAttr("readonly")
                                .bind('keyup.lock, blur.lock',
                                    function (event) {
                                        $(selector).val($(this).val());
                                    }
                                ).blur();
                            $(this).addClass('locked');
                        }

                        return false;
                    }
                );

                $("#edit input").unbind('focus.marker').bind('focus.marker', function (event) {
                    $("#edit tr").removeClass("info");
                    $(this).closest("tbody").find("tr").addClass("info");
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
