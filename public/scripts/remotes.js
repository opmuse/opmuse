define(['jquery', 'inheritance', 'ws', 'ajaxify', 'bind', 'domReady!'], function($, inheritance, ws, ajaxify) {

    var instance = null;

    var Remotes = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Remotes allowed!');
            }

            var that = this;

            ws.on('remotes.artist.fetched', function (id) {
                that.load([".remotes_artist_head_" + id, ".remotes_artist_nav_" + id]);
            });

            ws.on('remotes.album.fetched', function (id) {
                that.load([".remotes_album_head_" + id]);
            });

            ws.on('remotes.track.fetched', function (id) {
                that.load([".remotes_track_head_" + id]);
            });
        },
        load: function (selectors) {
            var found = false;

            for (var index in selectors) {
                var selector = selectors[index];

                if ($(selector).length > 0) {
                    found = true;
                    break;
                }
            }

            if (found) {
                $.ajax(document.location.href, {
                    success: function (data, textStatus, xhr) {
                        var page = $($.parseHTML(data));

                        for (var index in selectors) {
                            var selector = selectors[index];

                            (function (selector) {
                                var element = $(selector);

                                element.addClass('remotes-hide').one('transitionend', function (event) {
                                    element.children().remove();
                                    element.append(page.find(selector).children());

                                    ajaxify.load(selector);

                                    $(this).removeClass('remotes-hide');
                                });
                            })(selector);
                        }
                    },
                    error: function (xhr) {
                    }
                });
            }
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Remotes();
        }

        return instance;
    })();
});
