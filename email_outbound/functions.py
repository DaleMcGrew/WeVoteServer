# email_outbound/functions.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

from .models import CAMPAIGNX_FRIEND_HAS_SUPPORTED_TEMPLATE, CAMPAIGNX_NEWS_ITEM_TEMPLATE, \
    CAMPAIGNX_SUPER_SHARE_ITEM_TEMPLATE, CAMPAIGNX_SUPPORTER_INITIAL_RESPONSE_TEMPLATE, \
    FRIEND_ACCEPTED_INVITATION_TEMPLATE, FRIEND_INVITATION_TEMPLATE, LINK_TO_SIGN_IN_TEMPLATE, \
    MESSAGE_TO_FRIEND_TEMPLATE, NOTICE_FRIEND_ENDORSEMENTS_TEMPLATE, NOTICE_VOTER_DAILY_SUMMARY_TEMPLATE, \
    REMIND_CONTACT, SEND_BALLOT_TO_SELF, SEND_BALLOT_TO_FRIENDS, SIGN_IN_CODE_EMAIL_TEMPLATE, \
    VERIFY_EMAIL_ADDRESS_TEMPLATE
from django.template.loader import get_template
from django.template import Context
from html.parser import HTMLParser
import re
import json


def get_template_filename(kind_of_email_template, text_or_html):
    if kind_of_email_template == VERIFY_EMAIL_ADDRESS_TEMPLATE:
        if text_or_html == "HTML":
            return "verify_email_address.html"
        else:
            return "verify_email_address.txt"
    elif kind_of_email_template == CAMPAIGNX_FRIEND_HAS_SUPPORTED_TEMPLATE:
        if text_or_html == "HTML":
            return "campaignx_friend_has_supported.html"
        else:
            return "campaignx_friend_has_supported.txt"
    elif kind_of_email_template == CAMPAIGNX_NEWS_ITEM_TEMPLATE:
        if text_or_html == "HTML":
            return "campaignx_news_item.html"
        else:
            return "campaignx_news_item.txt"
    elif kind_of_email_template == CAMPAIGNX_SUPER_SHARE_ITEM_TEMPLATE:
        if text_or_html == "HTML":
            return "campaignx_super_share_item.html"
        else:
            return "campaignx_super_share_item.txt"
    elif kind_of_email_template == CAMPAIGNX_SUPPORTER_INITIAL_RESPONSE_TEMPLATE:
        if text_or_html == "HTML":
            return "campaignx_supporter_initial_response.html"
        else:
            return "campaignx_supporter_initial_response.txt"
    elif kind_of_email_template == FRIEND_INVITATION_TEMPLATE:
        if text_or_html == "HTML":
            return "friend_invitation.html"
        else:
            return "friend_invitation.txt"
    elif kind_of_email_template == FRIEND_ACCEPTED_INVITATION_TEMPLATE:
        if text_or_html == "HTML":
            return "friend_accepted_invitation.html"
        else:
            return "friend_accepted_invitation.txt"
    elif kind_of_email_template == LINK_TO_SIGN_IN_TEMPLATE:
        if text_or_html == "HTML":
            return "link_to_sign_in.html"
        else:
            return "link_to_sign_in.txt"
    elif kind_of_email_template == MESSAGE_TO_FRIEND_TEMPLATE:
        if text_or_html == "HTML":
            return "message_to_friend.html"
        else:
            return "message_to_friend.txt"
    elif kind_of_email_template == NOTICE_FRIEND_ENDORSEMENTS_TEMPLATE:
        if text_or_html == "HTML":
            return "notice_friend_endorsements.html"
        else:
            return "notice_friend_endorsements.txt"
    elif kind_of_email_template == NOTICE_VOTER_DAILY_SUMMARY_TEMPLATE:
        if text_or_html == "HTML":
            return "notice_voter_daily_summary.html"
        else:
            return "notice_voter_daily_summary.txt"
    elif kind_of_email_template == REMIND_CONTACT:
        if text_or_html == "HTML":
            return "remind_contact.html"
        else:
            return "remind_contact.txt"
    elif kind_of_email_template == SEND_BALLOT_TO_SELF:
        if text_or_html == "HTML":
            return "send_ballot_to_self.html"
        else:
            return "send_ballot_to_self.txt"
    elif kind_of_email_template == SEND_BALLOT_TO_FRIENDS:
        if text_or_html == "HTML":
            return "send_ballot_to_friends.html"
        else:
            return "send_ballot_to_friends.txt"
    elif kind_of_email_template == SIGN_IN_CODE_EMAIL_TEMPLATE:
        if text_or_html == "HTML":
            return "sign_in_code_email.html"
        else:
            return "sign_in_code_email.txt"
    # If the template wasn't recognized, return GENERIC_EMAIL_TEMPLATE
    if text_or_html == "HTML":
        return "generic_email.html"
    else:
        return "generic_email.txt"


def merge_message_content_with_template(kind_of_email_template, template_variables_in_json):
    success = True
    status = "KIND_OF_EMAIL_TEMPLATE: " + str(kind_of_email_template) + " "
    message_text = ""
    message_html = ""

    # Transfer JSON template variables back into a dict
    template_variables_dict = json.loads(template_variables_in_json)
    # template_variables_object = Context(template_variables_dict)  # Used previously with Django 1.8

    # Set up the templates
    text_template_path = "email_outbound/email_templates/" + get_template_filename(kind_of_email_template, "TEXT")
    html_template_path = "email_outbound/email_templates/" + get_template_filename(kind_of_email_template, "HTML")

    # We need to combine the template_variables_in_json with the kind_of_email_template
    text_template = get_template(text_template_path)
    html_template = get_template(html_template_path)

    if "subject" in template_variables_dict:
        subject = template_variables_dict['subject']
    else:
        subject = "From We Vote"

    try:
        message_text = text_template.render(template_variables_dict)
        status += "RENDERED_TEXT_TEMPLATE "
        message_html = html_template.render(template_variables_dict)
        status += "RENDERED_HTML_TEMPLATE "
    except Exception as e:
        status += "FAILED_RENDERING_TEMPLATE, error: " + str(e) + " "
        success = False

    results = {
        'success':      success,
        'status':       status,
        'subject':      subject,
        'message_text': message_text,
        'message_html': message_html,
    }
    return results


class HTMLToPlainText(HTMLParser):
    """Convert HTML to plain text, preserving structure and readability."""

    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.current_line = []
        self.in_script = False
        self.in_style = False

    def handle_starttag(self, tag, attrs):
        # Add line breaks for block elements
        if tag in ['p', 'div', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'tr']:
            if self.current_line:
                self.text_parts.append(''.join(self.current_line).strip())
                self.current_line = []

        # Add extra line break for headers
        if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            self.text_parts.append('')

        # Track script and style tags to ignore their content
        if tag == 'script':
            self.in_script = True
        elif tag == 'style':
            self.in_style = True

    def handle_endtag(self, tag):
        if tag in ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table']:
            if self.current_line:
                self.text_parts.append(''.join(self.current_line).strip())
                self.current_line = []
            self.text_parts.append('')  # Add blank line after these elements

        if tag == 'script':
            self.in_script = False
        elif tag == 'style':
            self.in_style = False

    def handle_data(self, data):
        # Ignore content in script and style tags
        if self.in_script or self.in_style:
            return

        # Clean up whitespace but preserve single spaces
        cleaned_data = ' '.join(data.split())
        if cleaned_data:
            self.current_line.append(cleaned_data)

    def get_text(self):
        # Add any remaining text
        if self.current_line:
            self.text_parts.append(''.join(self.current_line).strip())

        # Join all parts and clean up excessive blank lines
        text = '\n'.join(self.text_parts)
        # Replace 3+ newlines with just 2 newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()


def convert_html_to_plain_text(html_content):
    """
    Convert HTML email content to plain text.

    Args:
        html_content: String containing HTML

    Returns:
        Plain text version of the HTML content
    """
    if not html_content:
        return ''

    try:
        parser = HTMLToPlainText()
        parser.feed(html_content)
        plain_text = parser.get_text()
        return plain_text
    except Exception as e:
        # Fallback: strip all HTML tags if parser fails
        plain_text = re.sub(r'<[^>]+>', '', html_content)
        # Clean up whitespace
        plain_text = re.sub(r'\s+', ' ', plain_text)
        return plain_text.strip()
