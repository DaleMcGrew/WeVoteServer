# campaign/functions.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

from wevote_functions.functions import positive_value_exists


def obfuscate_email(email):
    if not email or not isinstance(email, str) or '@' not in email:
        return email  # Return the original input if it's not a valid email

    local_part, domain = email.split('@')

    if len(local_part) <= 3:
        # For super short local parts, keep the first character and obfuscate the rest
        obfuscated_local_part = local_part[0] + '*' * (len(local_part) - 1)
    elif len(local_part) <= 4:
        # For short local parts, keep the first two characters and obfuscate the rest
        obfuscated_local_part = local_part[:2] + '*' * (len(local_part) - 2)
    else:
        # For longer local parts, keep the first three characters and obfuscate the rest
        middle_length = len(local_part) - 4
        obfuscated_local_part = local_part[:3] + '*' * (len(local_part) - 2)

    domain_parts = domain.split('.')
    domain_name = domain_parts[0]
    top_level_domain = '.'.join(domain_parts[1:])  # Handle multi-part TLDs

    if len(domain_name) <= 3:
        # For short domain names, keep the first character and obfuscate the rest
        obfuscated_domain_name = domain_name[0] + '*' * (len(domain_name) - 1)
    else:
        # For longer domain names, keep the first and last character
        obfuscated_domain_name = domain_name[0] + '*' * (len(domain_name) - 2) + domain_name[-1]

    return f"{obfuscated_local_part}@{obfuscated_domain_name}.{top_level_domain}"


def protect_emails_in_list(incoming_email_list):
    protected_list = []
    if incoming_email_list:
        for email_dict in incoming_email_list:
            for email_we_vote_id, unprotected_email in email_dict.items():
                protected_email = obfuscate_email(unprotected_email)
                protected_list.append({email_we_vote_id: protected_email})
    return protected_list


def get_verification_emails(campaignx_owner=None, viewer_is_owner=False):
    try:
        voter_we_vote_id = campaignx_owner.voter_we_vote_id
    except Exception as e:
        voter_we_vote_id = ''
    verified_email_addresses = []
    if positive_value_exists(voter_we_vote_id):
        from email_outbound.models import EmailManager
        email_manager = EmailManager()
        results = email_manager.retrieve_voter_email_address_list(voter_we_vote_id)
        if results['email_address_list_found']:
            email_address_list = results['email_address_list']
            verified_email_addresses = [
                {email_object.we_vote_id: email_object.normalized_email_address}
                for email_object in email_address_list
                if email_object.email_ownership_is_verified and not email_object.deleted
            ]
    if viewer_is_owner:
        return verified_email_addresses
    else:
        # Obscure the email addresses for privacy reasons
        return protect_emails_in_list(verified_email_addresses)
