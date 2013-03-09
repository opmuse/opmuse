define(['jquery', 'inheritance', 'bind', 'domReady!'], function($, inheritance) {

    var instance = null;

    var Covers = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Covers allowed!');
            }

            var that = this;

            $('#main').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            var that = this;

            $("a.remove-cover").unbind('click.ajaxify').unbind('click.covers')
                .bind('click.covers', function (event) {
                    var href = $(this).attr('href');
                    var img = $(this).closest('.cover-container').find('img');
                    $.ajax(href, {
                        success: function (data, textStatus, xhr) {
                            that.refreshImg(img);

                            setTimeout(function () {
                                that.refreshImg(img);
                            }, 1000 * 5);
                        },
                        error: function (xhr) {
                        },
                    });

                    return false;
            });
        }, refreshImg: function (img) {
            img.attr('src', img.attr('src') + "&refresh=" + Math.random());
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Covers();
        }

        return instance;
    })();
});
