"""
Email sending via SendGrid HTTPS API (more reliable than SMTP on Render).

Why HTTPS API instead of SMTP?
  Render's free tier sometimes blocks/throttles outbound port 587.
  SendGrid's API uses port 443 (HTTPS) which always works.
"""

import os
import logging

from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse


logger = logging.getLogger(__name__)


def send_verification_email(request, user):
    """Send a verification email containing both a link AND a 6-digit OTP."""
    profile     = user.profile
    token, otp  = profile.generate_verification_token()

    verify_path = reverse('verify_email', kwargs={'token': token})
    verify_url  = request.build_absolute_uri(verify_path)

    context = {
        'user':       user,
        'shop_name':  profile.shop.name,
        'verify_url': verify_url,
        'otp':        otp,
    }

    subject  = f'Verify your email — {profile.shop.name}'
    text_msg = render_to_string('emails/verify_email.txt', context)
    html_msg = render_to_string('emails/verify_email.html', context)

    # ── Try HTTPS API first (works on Render free tier) ──
    api_key = os.environ.get('SENDGRID_API_KEY', '')
    if api_key:
        try:
            _send_via_sendgrid_api(
                api_key  = api_key,
                to_email = user.email,
                subject  = subject,
                text_body= text_msg,
                html_body= html_msg,
            )
            logger.info(f'Verification email sent to {user.email} via SendGrid API')
            return
        except Exception as e:
            logger.error(f'SendGrid API failed: {e}. Falling back to SMTP.')

    # ── Fallback: standard Django SMTP ──
    from django.core.mail import EmailMultiAlternatives
    email = EmailMultiAlternatives(
        subject     = subject,
        body        = text_msg,
        from_email  = settings.DEFAULT_FROM_EMAIL,
        to          = [user.email],
    )
    email.attach_alternative(html_msg, 'text/html')
    email.send(fail_silently=False)


def _send_via_sendgrid_api(api_key, to_email, subject, text_body, html_body):
    """Send via SendGrid's HTTPS API. Requires `sendgrid` package."""
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content

    # Parse "Sport Shop Nepal <noreply@example.com>" into name + email
    from_raw = settings.DEFAULT_FROM_EMAIL
    if '<' in from_raw and '>' in from_raw:
        from_name  = from_raw.split('<')[0].strip().strip('"')
        from_email = from_raw.split('<')[1].split('>')[0].strip()
    else:
        from_name  = ''
        from_email = from_raw

    message = Mail(
        from_email = Email(from_email, from_name) if from_name else Email(from_email),
        to_emails  = To(to_email),
        subject    = subject,
    )
    message.add_content(Content('text/plain', text_body))
    message.add_content(Content('text/html',  html_body))

    sg = SendGridAPIClient(api_key)
    response = sg.send(message)

    if response.status_code >= 400:
        raise RuntimeError(
            f'SendGrid API returned {response.status_code}: {response.body}'
        )