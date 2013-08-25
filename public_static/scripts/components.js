define(['jquery', 'inheritance', 'blur', 'domReady!'], function($, inheritance) {

    var instance = null;

    var Components = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Components allowed!');
            }

            var that = this;

            $('#main').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            var that = this;

            $(".album-container .album-labels, " +
              ".album-container .add-album, " +
              ".artist-container .artist-labels").hover(
                function (event) {
                    that.blur($(this).closest('.album-container, .artist-container'));
                },
                function (event) {
                    that.unblur($(this).closest('.album-container, .artist-container'));
                }
            );

            $(".album-container, .artist-container, .cover-container").hover(function (event) {
                that.blur(this);
            }, function (event) {
                that.unblur(this);
            });
        },
        blur: function (element) {
            $(element).find('img').blurjs({
                radius: 1
            });
        },
        unblur: function (element) {
            $(element).find('img').blurjs('remove');
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Components();
        }

        return instance;
    })();
});

