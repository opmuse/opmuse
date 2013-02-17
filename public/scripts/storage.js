define(['jquery', 'inheritance', 'sprintf', 'domReady!'], function($, inheritance) {

    var instance = null;

    var Storage = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Storage allowed!');
            }

            this.storage = localStorage;
            this.typeKeyFormat = '__type__.%s';
        },
        set: function (key, value) {
            this.storage.setItem(key, value);
            this.storage.setItem(sprintf(this.typeKeyFormat, key), typeof value);
        },
        get: function (key) {
            var type = this.storage.getItem(sprintf(this.typeKeyFormat, key));
            var value = this.storage.getItem(key);

            if (type == 'boolean') {
                value = value == 'true' ? true : false;
            } else if (type == 'number') {
                value = parseFloat(value);
            }

            return value;
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Storage();
        }

        return instance;
    })();
});


