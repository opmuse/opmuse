define(['jquery', 'inheritance', 'bootstrap/popover', 'domReady!'], function($, inheritance) {

    var instance = null;

    var Download = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Download allowed!');
            }

            var that = this;

            $('#main').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            $('.download').unbind('click.ajaxify')

            $('.download').each(function () {
                var button = this;

                var url = $(button).attr("href");

                var ext = url.split(".").pop();

                var options = {
                    html: true,
                    placement: "top",
                    trigger: "hover",
                    container: "#main",
                };

                if (['png', 'jpg', 'gif', 'jpeg'].indexOf(ext) != -1) {
                    options.content = $("<img>").attr("src", url);
                    $(button).popover(options);
                } else if (['txt', 'sfv', 'nfo', 'm3u', 'cue', 'log'].indexOf(ext) != -1) {
                    $.ajax(url, {
                        success: function (data) {
                            options.content = $("<pre>").append(data);
                            $(button).popover(options);
                        }
                    });
                }
            });
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Download();
        }

        return instance;
    })();
});

