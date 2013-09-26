define(['jquery', 'inheritance', 'bind', 'domReady!'], function($, inheritance) {

    var instance = null;

    var DirTable = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of DirTable allowed!');
            }

            var that = this;

            $('#main').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            $("table.dir_table .other-files-header .other-files-header-title").click(function () {
                $(this).closest(".other-files-header").find(".other-files-toggle").click();
                return false;
            });
        }
    });

    return (function() {
        if (instance === null) {
            instance = new DirTable();
        }

        return instance;
    })();
});
