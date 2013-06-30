define(['jquery', 'inheritance', 'ajaxify', 'domReady!'], function($, inheritance, ajaxify) {
    var instance = null;

    var Users = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Users allowed!');
            }

            var that = this;

            $('#main').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            var that = this;

            $("#users .users-add-form button").click(function (event) {
                var form = $(this).closest('form');
                var data = $(form).serialize();

                $.ajax($(form).attr('action'), {
                    type: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    data: data,
                    success: function (data) {
                        ajaxify.setPageInDom(data);
                    }
                });

                return false;
            });
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Users();
        }

        return instance;
    })();

});

