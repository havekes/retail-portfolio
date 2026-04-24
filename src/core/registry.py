from svcs import Registry

from src.core.email import EmailService


def register_core_services(registry: Registry) -> None:
    registry.register_value(EmailService, EmailService())
