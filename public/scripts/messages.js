define(['jquery', 'inheritance', 'bind', 'lib/bootstrap/bootstrap-alert', 'domReady!'], function($, inheritance) {

    var instance = null;

    var Messages = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Messages allowed!');
            }

            var that = this;

            $('body').ajaxComplete(function (event, xhr) {
                var header = xhr.getResponseHeader('X-Opmuse-Message');

                if (header !== null) {
                    var message = JSON.parse(header);

                    var dom = $('.message.tmpl').clone()
                        .removeClass('tmpl')
                        .addClass('alert-' + message.type);

                    dom.find('.text').text(message.text);

                    dom.appendTo('#messages').alert();
                }
            });

        }
    });

    return (function() {
        if (instance === null) {
            instance = new Messages();
        }

        return instance;
    })();
});
