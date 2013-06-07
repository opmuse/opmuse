define(['inheritance'], function(inheritance) {

    var instance = null;

    var Logger = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Logger allowed!');
            }
        },
        log: function (message) {
            if (typeof console != 'undefined' && console !== null) {
                console.log(message);
            }
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Logger();
        }

        return instance;
    })();
});
