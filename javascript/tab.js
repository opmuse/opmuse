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
import 'bootstrap';

class Tab {
    constructor() {
        var that = this;

        $('#main').on('ajaxifyInit', function(event) {
            that.internalInit();
        });

        that.internalInit();
    }
    internalInit() {
            $('[data-toggle=tab] a, [data-toggle=pill] a').click(function(event) {
                $(this).tab('show');
                return false;
            });

            this.setActive('pill');
            this.setActive('tab');
        }
        /**
         * if there's no active tab/pill set first tab/pill as active...
         */
    setActive(type) {
        var nav = $('[data-toggle=tab]').closest('.nav-' + type + 's');
        var content = nav.siblings('.tab-content');

        if (content.length > 0 && content.find('>li.active').length == 0) {
            var first = content.find(':first-child');
            var id = first.attr('id');
            nav.find('[href="#' + id + '"]').tab('show');
        }
    }
}

export default new Tab();
