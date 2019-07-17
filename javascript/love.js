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
        'opmuse/messages'
    ], function ($, messages) {

    'use strict';

    var instance = null;

    class Love {
        constructor () {
            if (instance !== null) {
                throw Error('Only one instance of Love allowed!');
            }

            var that = this;

            $('#main').on('ajaxifyInit', function (event) {
                that.reload();
            });

            that.internalInit();
        }
        internalInit () {
            var that = this;

            $(document).on('click', '.btn.love',
                function (event) {
                    var url = $(this).attr('href');
                    $.ajax({
                        url: url,
                        success: function () {
                            messages.success('The track is now marked as loved');
                        },
                        error: function () {
                            messages.danger('An error occured while trying ' +
                                            'to mark track as loved');
                        }
                    });
                    return false;
                }
            );

            that.reload();
        }
        reload () {
            var that = this;
            $('.btn.love').data('ajaxify', false);
        }
    }

    return (function () {
        if (instance === null) {
            instance = new Love();
        }

        return instance;
    })();
});
