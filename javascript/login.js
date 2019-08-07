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

import $ from 'jquery';
import locations from 'opmuse/locations';
import ajaxify from 'opmuse/ajaxify';
import layout from 'opmuse/layout';

class Login {
    constructor() {
        var that = this;

        $('#top').on('ajaxifyInit', function(event) {
            that.internalInit();
        });

        that.internalInit();

        $(document).ajaxComplete(function(event, xhr) {
            var authenticated = JSON.parse(xhr.getResponseHeader('X-Opmuse-Authenticated'));

            // if authenticated state changes (e.g. when you've loaded the
            // page when you're logged in and then your session turns invalid
            // and you try to load another page...)
            if (authenticated !== opmuseGlobals.authenticated) {
                document.location.replace('/');
                return;
            }
        });

        if ($('#login .ophelia-box').is(':visible')) {
            $('#login .ophelia-box').addClass('loaded').one('transitionend', function(event) {
                $('#login .login-box').addClass('loaded').one('transitionend', function(event) {
                    if (!$('html').hasClass('touch')) {
                        $('input[name=login]').focus();
                    }
                });
            });
        } else {
            $('#login .ophelia-box, #login .login-box').addClass('loaded');

            if (!$('html').hasClass('touch')) {
                $('input[name=login]').focus();
            }
        }
    }
    internalInit() {
        if ($('#login').length > 0) {
            $('.login, .home').data('ajaxify', false);
        }

        $('#login form').submit(function() {
            var data = $(this).serialize();
            var action = $(this).attr('action');

            var loginInput = $(this).find('input[name=login]');
            var passwordInput = $(this).find('input[name=password]');

            if (loginInput.val().length === 0) {
                return false;
            }

            var submitButton = $(this).find('button[type=submit]');

            submitButton.attr('disabled', 'disabled');
            submitButton.addClass('disabled');

            // we don't want a ajax redirect but a proper one so
            // we handle it ourselves in success()
            locations.disable();

            $.ajax(action, {
                type: 'post',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                data: data,
                success: function(data, status, xhr) {
                    var location = locations.getLocation(xhr);

                    if (location !== null) {
                        $('#login').addClass('logged-in').one('transitionend', function() {
                            layout.showOverlay();
                            document.location.replace(location);
                        });;
                        return;
                    }

                    submitButton.removeAttr('disabled');
                    submitButton.removeClass('disabled');

                    passwordInput.val('').focus().select();

                    locations.enable();
                },
                error: function(xhr) {
                    ajaxify.setPageInDom(xhr.responseText);
                    locations.enable();
                }
            });
            return false;
        });
    }
}

export default new Login();
