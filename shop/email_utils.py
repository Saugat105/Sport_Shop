from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse


def send_verification_email(request, user):
    """Send a verification email containing BOTH a link AND a 6-digit OTP code."""
    profile = user.profile
    token, otp = profile.generate_verification_token()

    # Build the verification URL (for users who prefer clicking the link)
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
    email.send(fail_silently=False)