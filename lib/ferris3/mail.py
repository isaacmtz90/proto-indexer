from . import settings, template
from google.appengine.api import mail, app_identity
import logging


def send(recipient, subject, body, sender=None, reply_to=None, **kwargs):
    """
    Sends an html email to ``recipient`` with the given ``subject`` and ``body``.

    If sender is none, it's automatically set to ``settings['email_sender']``,
    If the setting is not configured, then the default ``noreply@[appid].appspotmail.com`` is used.

    Any additionally arguments are passed to ``mail.send_mail``, such as headers.
    """
    try:
        sender = sender if sender else settings.get('email_sender', None)
    except settings.ConfigurationError:
        sender = None
    if not sender:
        sender = "noreply@%s.appspotmail.com" % app_identity.get_application_id()
        logging.info("No sender configured, using the default one: %s" % sender)

    res = mail.send_mail(
        sender=sender,
        to=recipient,
        subject=subject,
        body=body,
        html=body,
        reply_to=reply_to if reply_to else sender,
        **kwargs)
    logging.info('Email sent to %s by %s with subject %s and result %s' % (recipient, sender, subject, res))
    return res


def send_template(recipient, subject, template_name, context=None, theme=None, **kwargs):
    """
    Renders a template using :func:`~ferris3.template.render` and sends an email
    in the same way as :func:`send`.

    For example::

        mail.send_template(
            recipient='jondoe@example.com',
            subject='A Test Email',
            template_name='app/email/test.html',
            context={
                'name': 'George'
            }
        )

    Would render the template ``app/email/test.html`` and email the rendered html.
    """
    name = ('email/' + template_name + '.html', template)
    context = context if context else {}
    body = template.render(name, context, theme=theme)
    res = send(recipient, subject, body, **kwargs)
    return res, body
