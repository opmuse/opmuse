/*!
 * Copyright 2012-2015 Mattias Fliesberg
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

define([
        'jquery',
        'opmuse/ajaxify',
        'typeahead.js/dist/bloodhound',
        'typeahead.js/dist/typeahead.jquery'
    ], function ($, ajaxify) {

    'use strict';

    var instance = null;

    class Edit {
        constructor () {
            if (instance !== null) {
                throw Error('Only one instance of Edit allowed!');
            }

            var that = this;

            $('#main').on('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        }
        initTypeahead () {
            this.createTypeahead('artist');
            this.createTypeahead('album');
            this.createTypeahead('track');
        }
        destroyTypeahead (type) {
            $(sprintf('#edit input[name=%ss]', type)).typeahead('destroy');
        }
        createTypeahead (type) {
            this.destroyTypeahead(type);

            $(sprintf('#edit input[name=%ss]:not(.locked)', type)).each(function () {
                var input = this;

                var mySource = new Bloodhound({
                    datumTokenizer: Bloodhound.tokenizers.whitespace,
                    queryTokenizer: Bloodhound.tokenizers.whitespace,
                    remote: {
                        url: sprintf('/search/api/%s?query=%%QUERY', type),
                        filter: function (data) {
                            var originalValue = $(input).data('originalValue');

                            var removeIndex = null;
                            var index;

                            for (index in data) {
                                if (data[index].name == originalValue) {
                                    removeIndex = index;
                                    break;
                                }
                            }

                            if (removeIndex !== null) {
                                data.splice(removeIndex, 1);
                            }

                            return data;
                        }
                    }
                });

                mySource.initialize();

                $(input).typeahead(null,
                    {
                        displayKey: 'name',
                        source: mySource.ttAdapter()
                    }
                );
            });
        }
        internalInit () {
            var that = this;

            that.initTypeahead();

            $('#edit form button').click(function (event) {
                var form = $(this).closest('form');
                var data = $(form).serialize();

                // serialize the button too..
                var name = $(this).attr('name');

                if (typeof name != 'undefined' && name !== null) {
                    data += '&' + name + '=' + name;
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
                        ajaxify.setPageInDom(xhr.responseText);
                    }
                });

                return false;
            });

            $('#edit .lock')
                .off('click.edit')
                .on('click.edit',
                    function (event) {
                        var type = null;

                        var th = $(this).closest('th');

                        if (th.is('.album')) {
                            type = 'album';
                        } else if (th.is('.artist')) {
                            type = 'artist';
                        } else if (th.is('.date')) {
                            type = 'date';
                        } else if (th.is('.disc')) {
                            type = 'disc';
                        }

                        var selector = '#edit input.' + type;

                        if ($(this).hasClass('locked')) {
                            $(selector)
                                .removeAttr('readonly')
                                .off('keyup.lock, blur.lock')
                                .removeClass('locked');

                            $(this).removeClass('locked');
                        } else {
                            that.destroyTypeahead(type);

                            $(selector).addClass('locked');
                            $(this).addClass('locked');

                            $($(selector).attr('readonly', 'readonly').get(0))
                                .removeAttr('readonly').removeClass('locked')
                                .on('keyup.lock, blur.lock',
                                    function (event) {
                                        $(selector).val($(this).val());
                                    }
                                ).blur();
                        }

                        that.createTypeahead(type);

                        return false;
                    }
                );

                $('#edit input').off('focus.marker').on('focus.marker', function (event) {
                    $('#edit tr').removeClass('active');
                    $(this).closest('tr').addClass('active');
                });
        }
    }

    return (function () {
        if (instance === null) {
            instance = new Edit();
        }

        return instance;
    })();

});
