"""Activity 1: Deterministic email header extraction (no LLM)."""

import email
import email.utils
from email.policy import default as default_policy

from temporalio import activity

from models import EmailHeaders, EmailInput


def _parse_address_list(raw: str | None) -> list[str]:
    """Parse a comma-separated header into a list of email addresses."""
    if not raw:
        return []
    addresses = email.utils.getaddresses([raw])
    return [addr for _, addr in addresses if addr]


@activity.defn
def extract_headers(email_input: EmailInput) -> EmailHeaders:
    """Parse RFC-2822 headers from a raw email message string."""
    msg = email.message_from_string(email_input.raw_message, policy=default_policy)

    message_id = msg.get("Message-ID", "")
    date = msg.get("Date", "")
    from_address = email.utils.parseaddr(msg.get("From", ""))[1]
    to_addresses = _parse_address_list(msg.get("To"))
    # Enron dataset uses X-cc / X-bcc instead of standard Cc / Bcc
    cc_addresses = _parse_address_list(msg.get("Cc") or msg.get("X-cc"))
    bcc_addresses = _parse_address_list(msg.get("Bcc") or msg.get("X-bcc"))
    subject = msg.get("Subject", "")

    activity.logger.info(
        "Extracted headers for message %s (from=%s, to=%d recipients)",
        message_id,
        from_address,
        len(to_addresses),
    )

    return EmailHeaders(
        message_id=message_id,
        date=date,
        from_address=from_address,
        to_addresses=to_addresses,
        cc_addresses=cc_addresses,
        bcc_addresses=bcc_addresses,
        subject=subject,
    )
