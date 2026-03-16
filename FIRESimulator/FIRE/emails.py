from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.timezone import now
from django.conf import settings

def welcome_email(user):
    subject = "Welcome to FI Planner!"
    message = f"Hi {user.username}, \n\nThanks for signing up! We're glad to have you!"
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]
    context = {
        'user': user,
        'landing_url': 'http://127.0.0.1:8000/myplans/'
    }
    html_content = render_to_string("emails/welcome_email.html", context)
    text_content = strip_tags(html_content)
    try:
        email = EmailMultiAlternatives(subject, text_content, from_email, recipient_list)
        email.attach_alternative(html_content, "text/html")
        email.send()
    except Exception as e:
        print(e)

