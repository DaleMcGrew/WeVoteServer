# wevote_functions/functions_email.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

import re
# from validate_email import validate_email  # Note that we use this in some places in our codebase


def extract_email_addresses_from_string(incoming_string):
    """
    Thanks to https://gist.github.com/dideler/5219706
    :param incoming_string:
    :return:
    """
    string_lower_case = incoming_string.lower()
    regex = re.compile((r"([a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`"
                        r"{|}~-]+)*(@|\sat\s)(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(\.|"
                        r"\sdot\s))+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)"))

    collection_of_emails = (email[0] for email in re.findall(regex, string_lower_case) if not email[0].startswith('//'))

    list_of_emails = []
    for email in collection_of_emails:
        list_of_emails.append(email)

    return list_of_emails
