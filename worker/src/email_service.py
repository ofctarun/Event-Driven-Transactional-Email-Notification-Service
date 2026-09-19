import logging
from typing import Dict, Any, Tuple
from jinja2 import Environment, BaseLoader, TemplateSyntaxError, UndefinedError

logger = logging.getLogger("email_service")

class EmailService:
    def __init__(self):
        # Jinja2 environment that loads templates from strings directly
        self.jinja_env = Environment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True
        )

    def render_template(
        self, 
        subject_template_str: str, 
        body_template_str: str, 
        dynamic_data: Dict[str, Any]
    ) -> Tuple[str, str]:
        """
        Renders both subject and body using Jinja2 with dynamic data.
        Raises TemplateSyntaxError or UndefinedError if template cannot be rendered.
        """
        subject_tmpl = self.jinja_env.from_string(subject_template_str)
        rendered_subject = subject_tmpl.render(**dynamic_data)

        body_tmpl = self.jinja_env.from_string(body_template_str)
        rendered_body = body_tmpl.render(**dynamic_data)

        return rendered_subject, rendered_body

    def send_simulated_email(
        self, 
        recipient_email: str, 
        rendered_subject: str, 
        rendered_body: str, 
        notification_id: str
    ) -> bool:
        """
        Simulates email delivery by producing structured log output.
        """
        divider = "=" * 70
        logger.info(
            f"\n{divider}\n"
            f"[SIMULATED EMAIL DISPATCH]\n"
            f"Notification ID : {notification_id}\n"
            f"Recipient       : {recipient_email}\n"
            f"Subject         : {rendered_subject}\n"
            f"------------------- BODY -------------------\n"
            f"{rendered_body}\n"
            f"{divider}"
        )
        return True

email_service = EmailService()
