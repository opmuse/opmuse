/*!
 * Copyright 2012-2013 Mattias Fliesberg
 *
 * This file is part of opmuse.
 *
 * opmuse is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * opmuse is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with opmuse.  If not, see <http://www.gnu.org/licenses/>.
 */

define(['jquery', 'inheritance', 'ajaxify', 'typeahead', 'sprintf', 'domReady!'], function($, inheritance, ajaxify) {

    "use strict";

    var instance = null;

    var Edit = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Edit allowed!');
            }

            var that = this;

            $('#main').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        initTypeahead: function () {
            this.createTypeahead("artist");
            this.createTypeahead("album");
            this.createTypeahead("track");
        },
        createTypeahead: function (type) {
            $(sprintf("#edit input[name=%ss]", type)).typeahead('destroy');
            $(sprintf("#edit input[name=%ss]:not(.locked)", type)).each(function () {
                var input = this;

                $(input).typeahead({
                    remote: {
                        url: sprintf('/library/search/api/%s?query=%%QUERY', type),
                        filter: function (parsedResponse) {
                            var originalValue = $(input).data('originalValue');
                            var index = parsedResponse.indexOf(originalValue);

                            if (index != -1) {
                                parsedResponse.splice(index, 1);
                            }

                            return parsedResponse;
                        }
                    }
                });
            });
        },
        internalInit: function () {
            var that = this;

            that.initTypeahead();

            $("#edit form button").click(function (event) {
                var form = $(this).closest('form');
                var data = $(form).serialize();

                // serialize the button too..
                var name = $(this).attr('name');

                if (typeof name != 'undefined' && name !== null) {
                    data += "&" + name + "=" + name;
                }

                $.ajax($(form).attr('action'), {
                    type: 'post',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    data: data,
                    success: function (data) {
                        ajaxify.setPageInDom(data);
                    },
                    error: function (xhr) {
                        ajaxify.setErrorPageInDom(xhr.responseText);
                    }
                });

                return false;
            });

            $("#edit .lock")
                .unbind('click.edit')
                .bind('click.edit',
                    function (event) {
                        var type = null;

                        var th = $(this).closest("th");

                        if (th.is(".album")) {
                            type = 'album';
                        } else if (th.is(".artist")) {
                            type = 'artist';
                        } else if (th.is(".date")) {
                            type = 'date';
                        } else if (th.is(".disc")) {
                            type = 'disc';
                        }

                        var selector = "#edit input." + type;

                        if ($(this).hasClass('locked')) {
                            $(selector)
                                .removeAttr("readonly")
                                .unbind('keyup.lock, blur.lock')
                                .removeClass('locked');

                            $(this).removeClass('locked');
                        } else {
                            $(selector).addClass('locked');
                            $(this).addClass('locked');

                            $($(selector).attr("readonly", "readonly").get(0))
                                .removeAttr("readonly").removeClass("locked")
                                .bind('keyup.lock, blur.lock',
                                    function (event) {
                                        $(selector).val($(this).val());
                                    }
                                ).blur();
                        }

                        that.initTypeahead();

                        return false;
                    }
                );

                $("#edit input").unbind('focus.marker').bind('focus.marker', function (event) {
                    $("#edit tr").removeClass("active");
                    $(this).closest("tr").addClass("active");
                });
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Edit();
        }

        return instance;
    })();

});

