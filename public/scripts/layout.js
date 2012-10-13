define(['jquery', 'inheritance', 'bind', 'domReady!'], function($, inheritance) {

    var instance = null;

    var Layout = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Layout allowed!');
            }

            var that = this;

            this.resizeContent();

            $(window).resize(this.resizeContent.bind(this));
            $(window).resize(this.resizeQueue.bind(this));

            $('body').bind('ajaxifyInit', function (event) {
                that.resizeQueue();
            });
        },
        resizeContent: function () {
            this.windowHeight = $(document).height();
            var footerOffset = $("#footer").offset();
            this.footerHeight = this.windowHeight - footerOffset.top;
            var contentOffset = $("#content").offset();
            this.contentHeight = this.windowHeight - contentOffset.top - this.footerHeight;

            $("#content")
                .height(this.contentHeight)
                .trigger("layoutResize");
        },
        resizeQueue: function () {
            $("#top-right")
                .height(this.contentHeight - $("#right").height())
                .trigger("layoutResize");
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Layout();
        }

        return instance;
    })();

});

