define(['jquery', 'inheritance', 'ajaxify', 'domReady!'], function($, inheritance, ajaxify) {
    var instance = null;

    var Tag = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Tag allowed!');
            }

            var that = this;

            $('#content').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            var that = this;

            $("#tag form").submit(function () {
                $.ajax($(this).attr('action'), {
                    type: 'post',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    data: $(this).serialize(),
                    success: function (data) {
                        ajaxify.setPageInDom(data);
                    },
                    error: function (xhr) {
                        ajaxify.setErrorPageInDom(xhr.responseText);
                    }
                });
                return false;
            });

            $("#tag .lock").unbind('click.ajaxify')
                .unbind('click.tag')
                .bind('click.tag',
                    function (event) {
                        var type = null;

                        if ($(this).is(".album")) {
                            type = 'album';
                        } else if ($(this).is(".artist")) {
                            type = 'artist';
                        } else if ($(this).is(".date")) {
                            type = 'date';
                        }

                        var selector = "#tag ." + type + ":not(.lock)";

                        $($(selector).attr("readonly", "readonly").get(0)).removeAttr("readonly")
                            .bind('keyup, blur',
                                function (event) {
                                    $(selector).val($(this).val());
                                }
                            ).blur();

                        return false;
                    }
                );
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Tag();
        }

        return instance;
    })();

});

