# Copyright 2012-2014 Mattias Fliesberg
#
# This file is part of opmuse.
#
# opmuse is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# opmuse is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with opmuse.  If not, see <http://www.gnu.org/licenses/>.

import cherrypy
import logging
from smtplib import SMTP, SMTP_SSL
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class MailError(Exception):
    pass


def debug(msg, traceback=False):
    cherrypy.log.error(msg, context='mail', severity=logging.DEBUG, traceback=traceback)


def log(msg, traceback=False):
    cherrypy.log(msg, context='mail', traceback=traceback)


class Mailer:
    def __init__(self):
        config = cherrypy.tree.apps[''].config['opmuse']

        if 'mail.host' in config:
            self.host = config['mail.host']
        else:
            self.host = 'localhost'

        if 'mail.port' in config:
            self.port = config['mail.port']
        else:
            self.port = 25

        if 'mail.ssl' in config:
            self.ssl = config['mail.ssl']
        else:
            self.ssl = False

        if 'mail.sender' in config:
            self.sender = config['mail.sender']
        else:
            self.sender = "opmuse@%s" % self.host

        if 'mail.user' in config:
            self.user = config['mail.user']
        else:
            self.user = None

        if 'mail.password' in config:
            self.password = config['mail.password']
        else:
            self.password = None

    def send(self, to, subject, plain=None, html=None):
        if plain is None and html is None:
            raise MailError("Either a plain or html message needs to be defined!")

        if self.ssl:
            _SMTP = SMTP_SSL
        else:
            _SMTP = SMTP

        if isinstance(to, list):
            to = ",".join(to)

        with _SMTP(self.host, self.port) as smtp:
            if self.user is not None and self.password is not None:
                smtp.login(self.user, self.password)

            message = MIMEMultipart('alternative')

            if plain is not None:
                part = MIMEText(plain, 'plain')
                message.attach(part)

            if html is not None:
                part = MIMEText(html, 'html')
                message.attach(part)

            message['Subject'] = subject
            message['From'] = self.sender
            message['To'] = to

            smtp.send_message(message)

        log("Sent message to %s" % to)


mailer = Mailer()
