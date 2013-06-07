define(['jquery', 'inheritance', 'ajaxify', 'domReady!'], function($, inheritance, ajaxify) {
    var instance = null;

    var You = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of You allowed!');
            }

            var that = this;

            $('#main').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            var that = this;

            $("#you form button").click(function (event) {
                var form = $(this).closest('form');
                var data = $(form).serialize();

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
        }
    });

    return (function() {
        if (instance === null) {
            instance = new You();
        }

        return instance;
    })();

});

