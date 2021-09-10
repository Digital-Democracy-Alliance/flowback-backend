# FlowBack was created and project lead by Loke Hagberg. The design was
# made by Lina Forsberg. Emilio Müller helped constructing Flowback.
# Astroneatech created the code. It was primarily financed by David
# Madsen. It is a decision making platform.
# Copyright (C) 2021  Astroneatech AB
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see https://www.gnu.org/licenses/.

from django.dispatch import receiver
from django.template.loader import render_to_string
from django_rest_passwordreset.signals import reset_password_token_created
from django.core.mail import send_mail

from settings.base import EMAIL_HOST_USER

@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, *args, **kwargs):
    """
    Handles password reset tokens
    When a token is created, an e-mail needs to be sent to the user
    :param sender: View Class that sent the signal
    :param instance: View Instance that sent the signal
    :param reset_password_token: Token Model Object
    :param args:
    :param kwargs:
    :return:
    """
    context = {
        'current_user': reset_password_token.user,
        'username': reset_password_token.user.username,
        'reset_password_url': "http://127.0.0.1:8000/generate-password?token={}".format(reset_password_token.key)
    }
    print("reset_password_token.key", reset_password_token.key)

    # render email html
    email_html_message = render_to_string('email_templates/user_reset_password.html', context)
    send_mail(subject="Password Reset for Flowback", from_email=EMAIL_HOST_USER,
              recipient_list=[reset_password_token.user.email], message='', html_message=email_html_message)


