# email_outbound/views_admin.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

import json
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from admin_tools.views import redirect_to_sign_in_page
from email_outbound.models import EmailTemplateFolder
from voter.models import voter_has_authority
import wevote_functions.admin
from wevote_functions.functions import positive_value_exists

logger = wevote_functions.admin.get_logger(__name__)


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

    email_template_name = request.POST.get('email_template_name', False)
    if positive_value_exists(email_template_name):
        email_template_name = email_template_name.strip()
    google_civic_election_id = request.POST.get('google_civic_election_id', 0)
    state_code = request.POST.get('state_code', False)

    # Since a pointer to performance_list was attached to performance_dict above, the performance_list
    # data gets passed along within performance_dict. We pass this performance_dict
    # with the name 'performance_process_dict' so it is clear this is from a "process" view.
    performance_process_dict_encoded = urlencode({
        'performance_process_dict': json.dumps(performance_dict)
    })

    messages.add_message(request, messages.INFO, 'EmailCampaign updated.')

    redirect_url = reverse(
        'email_outbound:email_campaign_list',
        args=()) + "?google_civic_election_id=" + str(google_civic_election_id) + \
        "&state_code=" + str(state_code) + "&" + performance_process_dict_encoded
    return HttpResponseRedirect(redirect_url)


@login_required
def email_campaign_edit_view(request):
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

    template_values = {
        # 'election':                                 election,
        # 'election_list':                            election_list,
        'google_civic_election_id':                 google_civic_election_id,
        'state_code':                               state_code,
        # 'state_list':                               sorted_state_list,
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

    email_template_name = request.POST.get('email_template_name', False)
    if positive_value_exists(email_template_name):
        email_template_name = email_template_name.strip()
    google_civic_election_id = request.POST.get('google_civic_election_id', 0)
    state_code = request.POST.get('state_code', False)

    # Since a pointer to performance_list was attached to performance_dict above, the performance_list
    # data gets passed along within performance_dict. We pass this performance_dict
    # with the name 'performance_process_dict' so it is clear this is from a "process" view.
    performance_process_dict_encoded = urlencode({
        'performance_process_dict': json.dumps(performance_dict)
    })

    messages.add_message(request, messages.INFO, 'EmailTemplate updated.')

    redirect_url = reverse(
        'email_outbound:email_template_list',
        args=()) + "?google_civic_election_id=" + str(google_civic_election_id) + \
        "&state_code=" + str(state_code) + "&" + performance_process_dict_encoded
    return HttpResponseRedirect(redirect_url)


@login_required
def email_template_folder_edit_process_view(request):
    """
    Process the new or edit template folder form
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

    email_template_name = request.POST.get('email_template_name', '')
    if positive_value_exists(email_template_name):
        email_template_name = email_template_name.strip()
    google_civic_election_id = request.POST.get('google_civic_election_id', 0)
    state_code = request.POST.get('state_code', False)

    # # Basic validations
    # if not email_template_name:
    #     err = 'Folder name is required.'
    #     messages.add_message(request, messages.ERROR, err)

    # Duplicate check, ignoring deleted folders
    exists = EmailTemplateFolder.objects.filter(
        deleted=False,
        email_template_name__iexact=email_template_name
    ).exists()
    if exists:
        err = f'A folder named "{email_template_name}" already exists.'
        messages.add_message(request, messages.ERROR, err)

    # Create
    folder = None
    if email_template_name and not exists:
        folder = EmailTemplateFolder.objects.create(
            email_template_name=email_template_name,
            archived=False,
            deleted=False,
        )

    # Since a pointer to performance_list was attached to performance_dict above, the performance_list
    # data gets passed along within performance_dict. We pass this performance_dict
    # with the name 'performance_process_dict' so it is clear this is from a "process" view.
    performance_process_dict_encoded = urlencode({
        'performance_process_dict': json.dumps(performance_dict)
    })
    if folder is not None:
        messages.add_message(request, messages.INFO, 'EmailTemplateFolder created.')

    # update folders:
    folder_list = EmailTemplateFolder.objects.filter(deleted=False)
    for folder in folder_list:
        # flag to check for changes
        folder_changed = False

        # check if row exists
        folder_archived_variable_exists_name = \
        "email_template_folder_archived_" + str(folder.id) + "_exists"
        folder_archived_variable_exists = \
            request.POST.get(folder_archived_variable_exists_name, None)

        # get variables
        folder_archived_variable_name = \
            "email_template_folder_archived_" + str(folder.id)
        folder_archived = \
            positive_value_exists(request.POST.get(folder_archived_variable_name, False))
        folder_deleted_variable_name = \
            "email_template_folder_deleted_" + str(folder.id)
        folder_deleted = \
            positive_value_exists(request.POST.get(folder_deleted_variable_name, False))

        # get edit folder name
        edit_email_template_folder_variable_name = 'edit_email_template_name_' + str(folder.id)
        edit_email_template_folder_name = request.POST.get(edit_email_template_folder_variable_name, '')
        if positive_value_exists(edit_email_template_folder_name):
            edit_email_template_folder_name = edit_email_template_folder_name.strip()

        # set variables only if row exists
        if folder_archived_variable_exists is not None:
            folder.archived = folder_archived
            folder.deleted = folder_deleted
            folder_changed = True

        # edit folder name is edit was called
        if edit_email_template_folder_name:
            folder.email_template_name = edit_email_template_folder_name
            folder_changed = True

        # save folder if changed
        if folder_changed:
            folder.save()


    redirect_url = reverse(
        'email_outbound:email_template_list',
        args=()) + "?google_civic_election_id=" + str(google_civic_election_id) + \
        "&state_code=" + str(state_code) + "&" + performance_process_dict_encoded
    return HttpResponseRedirect(redirect_url)


@login_required
def email_template_folder_edit_view(request):
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
    return render(request, 'email_outbound/email_template_folder_edit.html', template_values)


@login_required
def email_template_list_view(request):
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
        # Any data you want to show in the list, e.g. folders:
        'folders': EmailTemplateFolder.objects.filter(deleted=False).order_by('email_template_name'),
        # The process URL (used by the modal form)
        'process_url': reverse('email_outbound:email_template_folder_edit_process'),

    }
    return render(request, 'email_outbound/email_template_list.html', template_values)
