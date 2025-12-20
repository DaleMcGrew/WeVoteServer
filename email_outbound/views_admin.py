# email_outbound/views_admin.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

import json
from datetime import datetime
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from admin_tools.views import redirect_to_sign_in_page
from email_outbound.models import EmailCampaign, EmailTemplate, EmailTemplateFolder, EmailCampaignRecipient, \
    EmailRecipientTemplateFolder, EmailRecipientTemplate
from voter.models import voter_has_authority
import wevote_functions.admin
from wevote_functions.functions import positive_value_exists
from wevote_functions.validate_email import validate_email

logger = wevote_functions.admin.get_logger(__name__)


def add_to_recipient_dict_if_accepted_we_vote_id_type(incoming_we_vote_id, recipient_dict, accepted_we_vote_id_types):
    save_recipient = False
    for we_vote_id_type in accepted_we_vote_id_types:
        if we_vote_id_type in incoming_we_vote_id:
            # It's a we_vote_id type we expect
            if we_vote_id_type == 'pol':
                recipient_dict.update({
                    'politician_we_vote_id': incoming_we_vote_id,
                })
                save_recipient = True
            elif we_vote_id_type == 'voter':
                recipient_dict.update({
                    'voter_we_vote_id': incoming_we_vote_id,
                })
                save_recipient = True
            break
    return recipient_dict, save_recipient


def email_associated_with_we_vote_id(email_address, incoming_we_vote_id):
    # TODO Check to make sure the email address is actually associated with the incoming_we_vote_id
    return True


@login_required
def email_campaign_edit_process_view(request):
    """
    Process the new or edit campaign form
    :param request:
    :return:
    """
    # The performance_dict variable contains list(s) of performance_snapshots.
    performance_dict = {}
    # Set up performance_list for this view. A pointer to the performance_list variable is established here.
    #  Throughout the rest of this view, we add snapshots to the performance_list. Since the performance_list
    #  is "attached" to the performance_dict with a pointer, when we pass performance_dict to the template,
    #  the performance_list data is included.
    performance_list = []
    performance_dict.update({
        'email_campaign_edit_process_view': performance_list,
    })

    # admin, analytics_admin, partner_organization, political_data_manager, political_data_viewer, verified_volunteer
    authority_required = {'verified_volunteer'}
    if not voter_has_authority(request, authority_required):
        return redirect_to_sign_in_page(request, authority_required)

    status = ""

    # Get form data
    campaign_title = request.POST.get('campaign_title', '').strip()
    email_template_id = request.POST.get('email_template_id', 0)
    recipient_ids = request.POST.get('recipient_ids', '')
    email_subject = request.POST.get('email_subject', '').strip()
    email_body = request.POST.get('email_body', '')
    email_campaign_id = request.POST.get('email_campaign_id', '')
    google_civic_election_id = request.POST.get('google_civic_election_id', 0)
    state_code = request.POST.get('state_code', '')
    send_button_clicked = request.POST.get('send_button_clicked', '')
    send_time_option = request.POST.get('send_time_option', 'now')
    scheduled_send_time_str = request.POST.get('scheduled_send_time', '')

    # Parse scheduled send time
    scheduled_send_time = None
    if send_time_option == 'scheduled' and scheduled_send_time_str:
        try:
            scheduled_send_time = datetime.fromisoformat(scheduled_send_time_str)
        except ValueError:
            pass

    # Create or update campaign
    if email_campaign_id:
        try:
            campaign = EmailCampaign.objects.get(id=email_campaign_id)
            campaign.email_campaign_name = campaign_title
            campaign.email_template_id = email_template_id
            campaign.email_subject_template_raw = email_subject
            campaign.email_body_template_raw = email_body
            campaign.scheduled_send_time = scheduled_send_time
            campaign.save()
            
            # Clear existing recipients for this campaign
            # TODO: We want to update this to only delete entries that have been removed from the form
            deleted_count, result_dict = EmailCampaignRecipient.objects.filter(email_campaign_id=campaign.id).delete()
            message = 'Email campaign updated.'
            if deleted_count > 0:
                message += f' Deleted {deleted_count} existing recipients.'
            messages.add_message(request, messages.SUCCESS, message)
        except EmailCampaign.DoesNotExist:
            campaign = EmailCampaign.objects.create(
                email_campaign_name=campaign_title,
                email_template_id=email_template_id,
                email_subject_template_raw=email_subject,
                email_body_template_raw=email_body,
                scheduled_send_time=scheduled_send_time,
            )
            email_campaign_id = campaign.id
            messages.add_message(request, messages.SUCCESS, 'Email campaign created.')
        except Exception as e:
            messages.add_message(request, messages.ERROR, f'Could not update email campaign. {e}')
    else:
        try:
            campaign = EmailCampaign.objects.create(
                email_campaign_name=campaign_title,
                email_template_id=email_template_id,
                email_subject_template_raw=email_subject,
                email_body_template_raw=email_body,
                scheduled_send_time=scheduled_send_time,
            )
            email_campaign_id = campaign.id
            messages.add_message(request, messages.SUCCESS, 'Email campaign created.')
        except Exception as e:
            messages.add_message(request, messages.ERROR, f'Could not create email campaign. {e}')

    if not positive_value_exists(email_campaign_id):
        messages.add_message(request, messages.ERROR, 'Email campaign not created or saved.')

    # Save recipients
    if positive_value_exists(recipient_ids) and positive_value_exists(email_campaign_id):
        accepted_we_vote_id_types = ['pol', 'voter']
        recipient_list = recipient_ids.split(',')
        for recipient_id in recipient_list:
            # Reset possible values
            email_address = ''
            incoming_we_vote_id = ''
            politician_we_vote_id = ''
            recipient_dict = {}
            voter_we_vote_id = ''
            recipient_id = recipient_id.strip()
            # recipient_id is structured like "WE_VOTE_ID-EMAIL_ADDRESS"
            # recipient_id = "wv01voter111-dalemcgrew@gmail.com"  # Test recipient_id
            # recipient_id = "dalemcgrew@gmail.com"  # Test recipient_id
            # recipient_id = "-dalemcgrew@gmail.com"  # Test recipient_id
            # recipient_id = "wv01pol111"  # Test recipient_id
            # recipient_id = "wv01voter111-"  # Test recipient_id
            if recipient_id:
                try:
                    part1, part2 = recipient_id.split('-')
                except Exception as e:
                    status += f'MINUS_SIGN_MISSING_FROM_RECIPIENT_ID: {e} '
                    part1 = recipient_id
                    part2 = ''

                save_recipient = False  # Reset to be safe
                recipient_dict.update({
                    'email_campaign_id': email_campaign_id,
                })

                if positive_value_exists(part2):
                    # Check to see if part1 contains any strings from accepted_we_vote_id_types
                    recipient_dict, recipient_dict_changed = \
                        add_to_recipient_dict_if_accepted_we_vote_id_type(
                            part1, recipient_dict, accepted_we_vote_id_types)
                    if positive_value_exists(recipient_dict_changed):
                        incoming_we_vote_id = part1
                        save_recipient = True
                    if validate_email(part2):
                        # It's an email address
                        email_address = part2
                        save_recipient = True
                else:
                    # If only one part is found, test it to see if it's an email address or a we_vote_id
                    if validate_email(part1):
                        # It's an email address
                        email_address = part1
                        save_recipient = True
                    else:
                        # Check to see if part1 contains any strings from accepted_we_vote_id_types
                        recipient_dict, recipient_dict_changed = \
                            add_to_recipient_dict_if_accepted_we_vote_id_type(
                                part1, recipient_dict, accepted_we_vote_id_types)
                        if positive_value_exists(recipient_dict_changed):
                            incoming_we_vote_id = part1
                            save_recipient = True
                        # if validate_email(part2):  # part2 would never exist give if/else block above
                        #     # It's an email address
                        #     email_address = part2

                save_email = False
                if positive_value_exists(email_address):
                    # Check to make sure the email address is associated with the we_vote_id
                    if not positive_value_exists(incoming_we_vote_id):
                        save_email = True
                    elif email_associated_with_we_vote_id(email_address, incoming_we_vote_id):
                        save_email = True

                if save_email:
                    recipient_dict.update({
                        'email_address': email_address,
                    })
                    save_recipient = True

                if save_recipient:
                    try:
                        # Check to see if an EmailCampaignRecipient value exists that matches the email_campaign_id and
                        #  any of these other values with a "Q" query parameter:
                        #  email_address, voter_we_vote_id, or politician_we_vote_id
                        queryset = EmailCampaignRecipient.objects.filter(email_campaign_id=email_campaign_id)
                        queryset = queryset.filter(
                            Q(email_address=email_address) |
                            Q(voter_we_vote_id=incoming_we_vote_id) |
                            Q(politician_we_vote_id=incoming_we_vote_id)
                        )
                        queryset = queryset.distinct()
                        if queryset.count() > 0:
                            # This recipient already exists for this campaign
                            recipient_list = list(queryset)
                            recipient_object = recipient_list[0]
                            # Update existing recipient with new values from recipient_dict
                            for field_key, field_value in recipient_dict.items():
                                if field_key != 'email_campaign_id':  # Don't update the primary lookup field
                                    if hasattr(recipient_object, field_key):
                                        setattr(recipient_object, field_key, field_value)
                            recipient_object.save()
                            status += f"EmailCampaignRecipient updated. "
                        else:
                            # Create a new EmailCampaignRecipient object
                            recipient_object = EmailCampaignRecipient(**recipient_dict)
                            recipient_object.save()
                            status += f"New EmailCampaignRecipient added. "
                    except Exception as e:
                        status += f"Error saving recipient: {str(e)}. "

    if positive_value_exists(send_button_clicked):
        # Send the email
        from email_outbound.controllers_email_campaign import email_campaign_send
        send_results = email_campaign_send(email_campaign_id=email_campaign_id)

        messages.add_message(request, messages.SUCCESS, 'Email sent!')

        redirect_url = reverse('email_outbound:email_campaign_edit') + \
            "?google_civic_election_id=" + str(google_civic_election_id) + \
            "&state_code=" + str(state_code)
    else:
        # Redirect back to edit page with the campaign ID
        redirect_url = reverse('email_outbound:email_campaign_edit') + \
            "?id=" + str(email_campaign_id) + \
            "&google_civic_election_id=" + str(google_civic_election_id) + \
            "&state_code=" + str(state_code)
    return HttpResponseRedirect(redirect_url)


@login_required
def email_campaign_edit_view(request):
    # Restrict access
    authority_required = {'political_data_manager', 'verified_volunteer'}
    if not voter_has_authority(request, authority_required):
        return redirect_to_sign_in_page(request, authority_required)

    google_civic_election_id = request.GET.get('google_civic_election_id', '')
    state_code = request.GET.get('state_code', '')
    campaign_id = request.GET.get('id', '')
    
    # Load existing campaign if editing
    email_campaign = None
    campaign_recipients = []
    if campaign_id:
        try:
            email_campaign = EmailCampaign.objects.get(id=campaign_id)
            
            # Load recipients for this campaign
            recipients = EmailCampaignRecipient.objects.filter(email_campaign_id=campaign_id)
            campaign_recipients = []
            for recipient in recipients:
                recipient_dict = {
                    'candidate_we_vote_id': recipient.candidate_we_vote_id
                    if positive_value_exists(recipient.candidate_we_vote_id) else '',
                    'email_address': recipient.email_address
                    if positive_value_exists(recipient.email_address) else '',
                    'email_campaign_id': recipient.email_campaign_id,
                    'organization_we_vote_id': recipient.organization_we_vote_id
                    if positive_value_exists(recipient.organization_we_vote_id) else '',
                    'politician_we_vote_id': recipient.politician_we_vote_id
                    if positive_value_exists(recipient.politician_we_vote_id) else '',
                    'recipient_name': recipient.recipient_name
                    if positive_value_exists(recipient.recipient_name) else '',
                    'voter_we_vote_id': recipient.voter_we_vote_id
                    if positive_value_exists(recipient.voter_we_vote_id) else '',
                }
                campaign_recipients.append(recipient_dict)

        except EmailCampaign.DoesNotExist:
            pass
    
    # Get list of saved campaigns
    saved_campaigns = EmailCampaign.objects.filter(deleted=False).order_by('-id')[:10]

    # Step 1: Get folders that are not deleted
    folder_queryset = EmailTemplateFolder.objects.filter(deleted=False, archived=False).order_by('email_template_name')

    # Get all valid folder IDs
    valid_folder_ids = list(folder_queryset.values_list('id', flat=True))

    # Step 2: Build a list of folders, each with its templates
    folder_list = []
    for folder in folder_queryset:
        templates_in_folder = EmailTemplate.objects.filter(
            email_template_folder_id=folder.id,
            deleted=False,
            archived=False
        ).order_by('email_template_name')

        folder_list.append({
            'id': folder.id,
            'folder_name': folder.email_template_name,  # For template display
            'templates': list(templates_in_folder.values('id', 'email_template_name')),
        })

    # Step 2b: Get templates without a folder (unfiled)
    # This includes templates with folder_id=0, NULL, or referencing non-existent folders
    unfiled_templates = EmailTemplate.objects.filter(
        deleted=False,
        archived=False
    ).filter(
        Q(email_template_folder_id__isnull=True) |
        Q(email_template_folder_id=0) |
        ~Q(email_template_folder_id__in=valid_folder_ids)
    ).order_by('email_template_name')

    # Always add unfiled section at the end (even if empty, so users know it exists)
    folder_list.append({
        'id': None,
        'folder_name': 'Unfiled',
        'templates': list(unfiled_templates.values('id', 'email_template_name')),
    })

    # Step 3: Pass data to template
    import json
    template_values = {
        'folder_list': folder_list,
        'folder_list_json': json.dumps(folder_list),
        'google_civic_election_id': google_civic_election_id,
        'state_code': state_code,
        'email_campaign': email_campaign,
        'saved_campaigns': saved_campaigns,
        'campaign_recipients': json.dumps(campaign_recipients),
    }

    return render(request, 'email_outbound/email_campaign_edit.html', template_values)


@login_required
def email_campaign_list_view(request):
    # admin, analytics_admin, partner_organization, political_data_manager, political_data_viewer, verified_volunteer
    authority_required = {'political_data_manager', 'verified_volunteer'}
    if not voter_has_authority(request, authority_required):
        return redirect_to_sign_in_page(request, authority_required)

    google_civic_election_id = request.GET.get('google_civic_election_id', '')
    state_code = request.GET.get('state_code', '')

    template_values = {
        # 'election':                                 election,
        # 'election_list':                            election_list,
        'google_civic_election_id':                 google_civic_election_id,
        'state_code':                               state_code,
        # 'state_list':                               sorted_state_list,
    }
    return render(request, 'email_outbound/email_campaign_list.html', template_values)


@login_required
def email_template_edit_view(request):
    # admin, analytics_admin, partner_organization, political_data_manager, political_data_viewer, verified_volunteer
    authority_required = {'political_data_manager', 'verified_volunteer'}
    if not voter_has_authority(request, authority_required):
        return redirect_to_sign_in_page(request, authority_required)

    google_civic_election_id = request.GET.get('google_civic_election_id', '')
    state_code = request.GET.get('state_code', '')
    email_template_id = request.GET.get('email_template_id', 0)
    default_folder_id = request.GET.get('default_email_template_folder_id', None)

    # Load existing template if editing
    email_template = None
    if positive_value_exists(email_template_id):
        try:
            email_template = EmailTemplate.objects.get(id=email_template_id)
        except EmailTemplate.DoesNotExist:
            email_template = None

    selected_folder_id = None
    if email_template:
        selected_folder_id = email_template.email_template_folder_id
    elif default_folder_id:
        selected_folder_id = int(default_folder_id)

    # customization tokens
    TOKEN_LIST = [
        "[official email]",
        "[person first name]",
        "[person last name]",
        "[person full name]",
        "[personal email]",
        ]

    template_values = {
        # 'election':               election,
        # 'election_list':          election_list,
        'email_template':           email_template,
        'folder_list':              EmailTemplateFolder.objects.filter(deleted=False).order_by('email_template_name'),
        'selected_folder_id':       selected_folder_id,
        'google_civic_election_id': google_civic_election_id,
        'state_code':               state_code,
        'token_list':               TOKEN_LIST,
        # 'state_list':             sorted_state_list,
    }
    return render(request, 'email_outbound/email_template_edit.html', template_values)


@login_required
def email_template_edit_process_view(request):
    """
    Process the new or edit template form
    :param request:
    :return:
    """
    # The performance_dict variable contains list(s) of performance_snapshots.
    performance_dict = {}
    # Set up performance_list for this view. A pointer to the performance_list variable is established here.
    #  Throughout the rest of this view, we add snapshots to the performance_list. Since the performance_list
    #  is "attached" to the performance_dict with a pointer, when we pass performance_dict to the template,
    #  the performance_list data is included.
    performance_list = []
    performance_dict.update({
        'email_template_edit_process_view': performance_list,
    })

    # admin, analytics_admin, partner_organization, political_data_manager, political_data_viewer, verified_volunteer
    authority_required = {'verified_volunteer'}
    if not voter_has_authority(request, authority_required):
        return redirect_to_sign_in_page(request, authority_required)

    status = ""

    email_template_name = request.POST.get('email_template_name', '').strip()
    subject = request.POST.get('subject', '').strip()
    message = request.POST.get('message', '').strip()
    folder_id = request.POST.get('folder', 0)
    email_template_id = request.POST.get('email_template_id', None)

    # if positive_value_exists(email_template_name):
    #     email_template_name = email_template_name.strip()
    google_civic_election_id = request.POST.get('google_civic_election_id', 0)
    state_code = request.POST.get('state_code', '')

    if folder_id == "null":
        folder_id = None

    try:
        if email_template_id and EmailTemplate.objects.filter(
            id=email_template_id,
            deleted=False,
        ).exists():
            email_template = EmailTemplate.objects.filter(
                id=email_template_id,
                deleted=False,
            ).first()
            email_template.email_template_name = email_template_name
            email_template.subject = subject
            email_template.message = message
            email_template.email_template_folder_id = folder_id
            email_template.save()
            status += "Existing template updated. "
        else:
            email_template = EmailTemplate.objects.create(
                email_template_name=email_template_name,
                subject=subject,
                message=message,
                email_template_folder_id=folder_id,
                deleted=False,
                archived=False,
            )
            if email_template is not None:
                status += "New template created. "
    except Exception as e:
        status += f"Error saving template: {e}"

    messages.add_message(request, messages.INFO, status)

    # Since a pointer to performance_list was attached to performance_dict above, the performance_list
    # data gets passed along within performance_dict. We pass this performance_dict
    # with the name 'performance_process_dict' so it is clear this is from a "process" view.
    performance_process_dict_encoded = urlencode({
        'performance_process_dict': json.dumps(performance_dict)
    })

    redirect_url = reverse(
        'email_outbound:email_template_list',
        args=()) + "?google_civic_election_id=" + str(google_civic_election_id) + \
        "&state_code=" + str(state_code) + "&" + performance_process_dict_encoded
    return HttpResponseRedirect(redirect_url)


@login_required
def email_template_list_process_view(request):
    """
    Process the email template list form (archive/delete operations)
    :param request:
    :return:
    """

    if request.method != "POST":
        return HttpResponseRedirect(reverse('email_outbound:email_template_list'))

    google_civic_election_id = request.POST.get('google_civic_election_id', 0)
    state_code = request.POST.get('state_code', '')

    def back():
        return HttpResponseRedirect(
            f"{reverse('email_outbound:email_template_list')}?google_civic_election_id={google_civic_election_id}&state_code={state_code}")

    action = request.POST.get("action", "").strip()

    try:
        if action == "create_folder":
            name = (request.POST.get("email_template_name") or "").strip()
            if not name:
                messages.error(request, "Folder name is required.")
                return back()
            exists = EmailTemplateFolder.objects.filter(
                deleted=False,
                email_template_name__iexact=name
            ).exists()
            if exists:
                err = f'A folder named "{name}" already exists.'
                messages.error(request, err)
                return back()
            EmailTemplateFolder.objects.create(email_template_name=name)
            messages.success(request, f"Folder “{name}” created.")
            return back()

        if action == "rename_folder":
            folder_id = request.POST.get("folder_id")
            new_name = (request.POST.get("edit_email_template_name") or "").strip()
            folder = EmailTemplateFolder.objects.get(id=folder_id, deleted=False)
            old = folder.email_template_name
            folder.email_template_name = new_name
            folder.save(update_fields=["email_template_name"])
            messages.success(request, f"Folder renamed from “{old}” to “{new_name}”.")
            return back()

        if action == "delete_folder":
            folder_id = request.POST.get("folder_id")
            folder = EmailTemplateFolder.objects.get(id=folder_id, deleted=False)
            # Move templates to Unfiled (NULL)
            EmailTemplate.objects.filter(email_template_folder_id=folder.id).update(email_template_folder_id=None)
            folder.deleted = True
            folder.archived = False
            folder.save(update_fields=["deleted", "archived"])
            messages.success(request, "Folder deleted. Templates moved to Unfiled.")
            return back()

        if action == "archive_folder":
            folder_id = request.POST.get("folder_id")
            folder = EmailTemplateFolder.objects.get(id=folder_id, deleted=False)
            folder.archived = True
            folder.save(update_fields=["archived"])
            messages.success(request, f"Folder “{folder.email_template_name}” archived.")
            return back()

        if action == "unarchive_folder":
            folder_id = request.POST.get("folder_id")
            folder = EmailTemplateFolder.objects.get(id=folder_id, deleted=False)
            folder.archived = False
            folder.save(update_fields=["archived"])
            messages.success(request, f"Folder “{folder.email_template_name}” unarchived.")
            return back()

        if action == "create_template":
            # Optionally pick a default folder for the new template (can be blank/unfiled)
            folder_id = request.POST.get("folder_id")
            # Redirect to template edit page (creation flow)
            edit_url = reverse("email_outbound:email_template_edit")
            qs = f"?google_civic_election_id={google_civic_election_id}&state_code={state_code}"
            if folder_id and folder_id != "null":
                qs += f"&default_email_template_folder_id={folder_id}"
            return HttpResponseRedirect(edit_url + qs)

        if action == "change_template_folder":
            template_id = request.POST.get("template_id")
            new_folder_id = request.POST.get("new_folder_id")  # can be "null"
            tmpl = EmailTemplate.objects.get(id=template_id, deleted=False)
            if new_folder_id == "null" or new_folder_id == "":
                tmpl.email_template_folder_id = None
            else:
                folder = EmailTemplateFolder.objects.get(id=new_folder_id, deleted=False)
                tmpl.email_template_folder_id = folder.id
            tmpl.save(update_fields=["email_template_folder_id"])
            messages.success(request, "Template moved.")
            return back()

        if action == "archive_template":
            template_id = request.POST.get("template_id")
            tmpl = EmailTemplate.objects.get(id=template_id, deleted=False)
            tmpl.archived = True
            tmpl.save(update_fields=["archived"])
            messages.success(request, f"Template “{tmpl.email_template_name}” archived.")
            return back()

        if action == "unarchive_template":
            template_id = request.POST.get("template_id")
            tmpl = EmailTemplate.objects.get(id=template_id, deleted=False)
            tmpl.archived = False
            tmpl.save(update_fields=["archived"])
            messages.success(request, f"Template “{tmpl.email_template_name}” unarchived.")
            return back()

        if action == "delete_template":
            template_id = request.POST.get("template_id")
            tmpl = EmailTemplate.objects.get(id=template_id, deleted=False)
            tmpl.deleted = True
            tmpl.email_template_folder_id = None
            tmpl.save(update_fields=["deleted", "email_template_folder_id"])
            messages.success(request, "Template deleted.")
            return back()

        messages.error(request, "Unknown action.")
        return back()

    except EmailTemplateFolder.DoesNotExist:
        messages.error(request, "Folder not found.")
        return back()
    except EmailTemplate.DoesNotExist:
        messages.error(request, "Template not found.")
        return back()
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return back()


@login_required
def email_template_list_view(request):
    # admin, analytics_admin, partner_organization, political_data_manager, political_data_viewer, verified_volunteer
    authority_required = {'political_data_manager', 'verified_volunteer'}
    if not voter_has_authority(request, authority_required):
        return redirect_to_sign_in_page(request, authority_required)

    google_civic_election_id = request.GET.get('google_civic_election_id',
                                               request.POST.get('google_civic_election_id', 0))
    state_code = request.GET.get('state_code', request.POST.get('state_code', ''))

    # Folders
    folder_qs = EmailTemplateFolder.objects.filter(deleted=False)
    folders_active = folder_qs.filter(archived=False).order_by('email_template_name')
    folders_archived = folder_qs.filter(archived=True).order_by('email_template_name')

    # Templates
    template_qs = EmailTemplate.objects.filter(deleted=False)
    templates_active = template_qs.filter(archived=False).order_by('email_template_name')
    templates_archived = template_qs.filter(archived=True).order_by('email_template_name')

    # Map active templates by folder id
    templates_by_folder = {}
    for t in templates_active:
        fid = t.email_template_folder_id  # None means "Unfiled"
        templates_by_folder.setdefault(fid, []).append(t)

    unfiled_templates = templates_by_folder.get(None, [])

    # Map folder id to folder name
    all_folders_by_id = {}
    for folder in folder_qs:
        all_folders_by_id[folder.id] = folder.email_template_name

    context = {
        "google_civic_election_id": google_civic_election_id,
        "state_code": state_code,

        # Groupings for UI
        "all_folders_by_id": all_folders_by_id,
        "folders_active": folders_active,
        "folders_archived": folders_archived,
        "templates_by_folder": templates_by_folder,  # keyed by folder id (None for Unfiled)
        "unfiled_templates": unfiled_templates,
        "archived_templates": templates_archived,

        # URLs
        "process_url": reverse('email_outbound:email_template_list_process'),
        "template_edit_url": reverse('email_outbound:email_template_edit'),
    }
    # messages.add_message(request, messages.INFO, '')
    return render(request, "email_outbound/email_template_list.html", context)


@login_required
def recipient_template_list_process_view(request):
    """
    Process the recipient template list form (archive/delete operations)
    :param request:
    :return:
    """

    if request.method != "POST":
        return HttpResponseRedirect(reverse('email_outbound:recipient_template_list'))

    google_civic_election_id = request.POST.get('google_civic_election_id', 0)
    state_code = request.POST.get('state_code', '')

    def back():
        return HttpResponseRedirect(
            f"{reverse('email_outbound:recipient_template_list')}?google_civic_election_id={google_civic_election_id}&state_code={state_code}")

    action = request.POST.get("action", "").strip()

    try:
        if action == "create_folder":
            name = (request.POST.get("recipient_template_name") or "").strip()
            if not name:
                messages.error(request, "Folder name is required.")
                return back()
            exists = EmailRecipientTemplateFolder.objects.filter(
                deleted=False,
                recipient_template_name__iexact=name
            ).exists()
            if exists:
                err = f'A folder named "{name}" already exists.'
                messages.error(request, err)
                return back()
            EmailRecipientTemplateFolder.objects.create(recipient_template_name=name)
            messages.success(request, f"Folder “{name}” created.")
            return back()

        if action == "rename_folder":
            folder_id = request.POST.get("folder_id")
            new_name = (request.POST.get("edit_recipient_template_name") or "").strip()
            folder = EmailRecipientTemplateFolder.objects.get(id=folder_id, deleted=False)
            old = folder.recipient_template_name
            folder.recipient_template_name = new_name
            folder.save(update_fields=["recipient_template_name"])
            messages.success(request, f"Folder renamed from “{old}” to “{new_name}”.")
            return back()

        if action == "delete_folder":
            folder_id = request.POST.get("folder_id")
            folder = EmailRecipientTemplateFolder.objects.get(id=folder_id, deleted=False)
            # Move templates to Unfiled (NULL)
            EmailRecipientTemplate.objects.filter(recipient_template_folder_id=folder.id).update(recipient_template_folder_id=None)
            folder.deleted = True
            folder.archived = False
            folder.save(update_fields=["deleted", "archived"])
            messages.success(request, "Folder deleted. Templates moved to Unfiled.")
            return back()

        if action == "archive_folder":
            folder_id = request.POST.get("folder_id")
            folder = EmailRecipientTemplateFolder.objects.get(id=folder_id, deleted=False)
            folder.archived = True
            folder.save(update_fields=["archived"])
            messages.success(request, f"Folder “{folder.recipient_template_name}” archived.")
            return back()

        if action == "unarchive_folder":
            folder_id = request.POST.get("folder_id")
            folder = EmailRecipientTemplateFolder.objects.get(id=folder_id, deleted=False)
            folder.archived = False
            folder.save(update_fields=["archived"])
            messages.success(request, f"Folder “{folder.recipient_template_name}” unarchived.")
            return back()

        if action == "create_template":
            # Optionally pick a default folder for the new template (can be blank/unfiled)
            folder_id = request.POST.get("folder_id")
            # Redirect to template edit page (creation flow)
            edit_url = reverse("email_outbound:recipient_template_list")
            # if modal is used for recipient template edit then ignore this link
            # else link to appropriate view
            qs = f"?google_civic_election_id={google_civic_election_id}&state_code={state_code}"
            if folder_id and folder_id != "null":
                qs += f"&default_recipient_template_folder_id={folder_id}"
            return HttpResponseRedirect(edit_url + qs)

        if action == "change_template_folder":
            template_id = request.POST.get("template_id")
            new_folder_id = request.POST.get("new_folder_id")  # can be "null"
            tmpl = EmailRecipientTemplate.objects.get(id=template_id, deleted=False)
            if new_folder_id == "null" or new_folder_id == "":
                tmpl.recipient_template_folder_id = None
            else:
                folder = EmailRecipientTemplateFolder.objects.get(id=new_folder_id, deleted=False)
                tmpl.recipient_template_folder_id = folder.id
            tmpl.save(update_fields=["recipient_template_folder_id"])
            messages.success(request, "Template moved.")
            return back()

        if action == "archive_template":
            template_id = request.POST.get("template_id")
            tmpl = EmailRecipientTemplate.objects.get(id=template_id, deleted=False)
            tmpl.archived = True
            tmpl.save(update_fields=["archived"])
            messages.success(request, f"Template “{tmpl.recipient_template_name}” archived.")
            return back()

        if action == "unarchive_template":
            template_id = request.POST.get("template_id")
            tmpl = EmailRecipientTemplate.objects.get(id=template_id, deleted=False)
            tmpl.archived = False
            tmpl.save(update_fields=["archived"])
            messages.success(request, f"Template “{tmpl.recipient_template_name}” unarchived.")
            return back()

        if action == "delete_template":
            template_id = request.POST.get("template_id")
            tmpl = EmailRecipientTemplate.objects.get(id=template_id, deleted=False)
            tmpl.deleted = True
            tmpl.recipient_template_folder_id = None
            tmpl.save(update_fields=["deleted", "recipient_template_folder_id"])
            messages.success(request, "Template deleted.")
            return back()

        messages.error(request, "Unknown action.")
        return back()

    except EmailRecipientTemplateFolder.DoesNotExist:
        messages.error(request, "Folder not found.")
        return back()
    except EmailRecipientTemplate.DoesNotExist:
        messages.error(request, "Template not found.")
        return back()
    except Exception as e:
        messages.error(request, f"Error: {e}")
        return back()

@login_required
def recipient_template_list_view(request):
    # admin, analytics_admin, partner_organization, political_data_manager, political_data_viewer, verified_volunteer
    authority_required = {'political_data_manager', 'verified_volunteer'}
    if not voter_has_authority(request, authority_required):
        return redirect_to_sign_in_page(request, authority_required)

    google_civic_election_id = request.GET.get('google_civic_election_id',
                                               request.POST.get('google_civic_election_id', 0))
    state_code = request.GET.get('state_code', request.POST.get('state_code', ''))

    # Folders
    folder_qs = EmailRecipientTemplateFolder.objects.filter(deleted=False)
    folders_active = folder_qs.filter(archived=False).order_by('recipient_template_name')
    folders_archived = folder_qs.filter(archived=True).order_by('recipient_template_name')

    # Templates
    template_qs = EmailRecipientTemplate.objects.filter(deleted=False)
    templates_active = template_qs.filter(archived=False).order_by('recipient_template_name')
    templates_archived = template_qs.filter(archived=True).order_by('recipient_template_name')

    # Map active templates by folder id
    templates_by_folder = {}
    for t in templates_active:
        fid = t.recipient_template_folder_id  # None means "Unfiled"
        templates_by_folder.setdefault(fid, []).append(t)

    unfiled_templates = templates_by_folder.get(None, [])

    # Map folder id to folder name
    all_folders_by_id = {}
    for folder in folder_qs:
        all_folders_by_id[folder.id] = folder.recipient_template_name

    context = {
        "google_civic_election_id": google_civic_election_id,
        "state_code": state_code,

        # Groupings for UI
        "all_folders_by_id": all_folders_by_id,
        "folders_active": folders_active,
        "folders_archived": folders_archived,
        "templates_by_folder": templates_by_folder,  # keyed by folder id (None for Unfiled)
        "unfiled_templates": unfiled_templates,
        "archived_templates": templates_archived,

        # URLs
        "process_url": reverse('email_outbound:recipient_template_list_process'),
        "template_edit_url": reverse('email_outbound:recipient_template_list'),
        # use template_edit_url variable with relevant link
        # if new view is used for recipient template edit and not modal
    }
    # messages.add_message(request, messages.INFO, '')
    return render(request, "email_outbound/recipient_template_list.html", context)


# @login_required
# def recipient_template_edit_view(request):
#     # admin, analytics_admin, partner_organization, political_data_manager, political_data_viewer, verified_volunteer
#     authority_required = {'political_data_manager', 'verified_volunteer'}
#     if not voter_has_authority(request, authority_required):
#         return redirect_to_sign_in_page(request, authority_required)
#
#     google_civic_election_id = request.GET.get('google_civic_election_id', '')
#     state_code = request.GET.get('state_code', '')
#     recipient_template_id = request.GET.get('recipient_template_id', 0)
#     default_folder_id = request.GET.get('default_recipient_template_folder_id', None)
#
#     # Load existing template if editing
#     recipient_template = None
#     if positive_value_exists(recipient_template_id):
#         try:
#             recipient_template = EmailTemplate.objects.get(id=recipient_template_id)
#         except EmailTemplate.DoesNotExist:
#             recipient_template = None
#
#     selected_folder_id = None
#     if recipient_template:
#         selected_folder_id = recipient_template.recipient_template_folder_id
#     elif default_folder_id:
#         selected_folder_id = int(default_folder_id)
#
#     # customization tokens
#     TOKEN_LIST = [
#         "[official email]",
#         "[person first name]",
#         "[person last name]",
#         "[person full name]",
#         "[personal email]",
#         ]
#
#     template_values = {
#         # 'election':               election,
#         # 'election_list':          election_list,
#         'recipient_template':           recipient_template,
#         'folder_list':              EmailTemplateFolder.objects.filter(deleted=False).order_by('recipient_template_name'),
#         'selected_folder_id':       selected_folder_id,
#         'google_civic_election_id': google_civic_election_id,
#         'state_code':               state_code,
#         'token_list':               TOKEN_LIST,
#         # 'state_list':             sorted_state_list,
#     }
#     return render(request, 'email_outbound/recipient_template_edit.html', template_values)

@login_required
def email_template_content_view(request):
    """
    API endpoint to fetch template content
    """
    template_id = request.GET.get('template_id', '')
    
    try:
        template = EmailTemplate.objects.get(id=template_id)
        return JsonResponse({
            'success': True,
            'subject': template.subject or '',
            'message': template.message or '',
        })
    except EmailTemplate.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Template not found'
        }, status=404)
