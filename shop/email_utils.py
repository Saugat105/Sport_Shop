import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)


def send_verification_email(request, user):
    """
    Send verification email with both a link AND a 6-digit OTP.

    Raises:
        Exception if email fails (so signup view can rollback the user).
    """
    profile = user.profile
    token, otp = profile.generate_verification_token()

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

    email = EmailMultiAlternatives(
        subject     = subject,
        body        = text_msg,
        from_email  = settings.DEFAULT_FROM_EMAIL,
        to          = [user.email],
    )
    email.attach_alternative(html_msg, 'text/html')

    # ── Set a tight timeout so we never hang the request ──
    # Gmail SMTP sometimes takes 5-10s, never 30s. If it does, fail fast.
    connection = email.get_connection()
    if hasattr(connection, 'timeout'):
        connection.timeout = 10  # seconds

    try:
        email.send(fail_silently=False)
        logger.info(f"Verification email sent to {user.email}")
    except Exception as e:
        logger.error(f"Failed to send verification email to {user.email}: {e}")
        raise