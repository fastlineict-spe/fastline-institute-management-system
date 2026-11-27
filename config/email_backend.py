import ssl
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend


class EmailBackend(SMTPEmailBackend):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.verify_flags &= ~ssl.VERIFY_X509_STRICT
