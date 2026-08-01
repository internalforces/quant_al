from unittest.mock import MagicMock, patch

from module.mail import send_email


def _send(port: int) -> None:
    send_email(
        subject="MB Quant signal",
        body="signal summary",
        sender="sender@example.com",
        recipient="recipient@example.com",
        smtp_server="smtp.example.com",
        smtp_port=port,
        smtp_user="smtp-user",
        smtp_password="smtp-password",
    )


@patch("module.mail.smtplib.SMTP")
def test_send_email_uses_starttls_for_port_587(smtp_mock: MagicMock) -> None:
    server = smtp_mock.return_value.__enter__.return_value

    _send(587)

    smtp_mock.assert_called_once_with("smtp.example.com", 587)
    server.ehlo.assert_called_once_with()
    server.starttls.assert_called_once_with()
    server.login.assert_called_once_with("smtp-user", "smtp-password")
    server.sendmail.assert_called_once()


@patch("module.mail.smtplib.SMTP_SSL")
@patch("module.mail.smtplib.SMTP")
def test_send_email_uses_ssl_for_port_465(
    smtp_mock: MagicMock, smtp_ssl_mock: MagicMock
) -> None:
    server = smtp_ssl_mock.return_value.__enter__.return_value

    _send(465)

    smtp_mock.assert_not_called()
    smtp_ssl_mock.assert_called_once_with("smtp.example.com", 465)
    server.login.assert_called_once_with("smtp-user", "smtp-password")
    server.sendmail.assert_called_once()
