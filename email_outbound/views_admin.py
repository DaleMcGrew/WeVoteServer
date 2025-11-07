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
from email_outbound.models import EmailTemplate, EmailTemplateFolder
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

    template_values = {
        # 'election':                                 election,
        # 'election_list':                            election_list,
        'email_template':                           email_template,
        'folder_list':                              EmailTemplateFolder.objects.filter(deleted=False).order_by('email_template_name'),
        'selected_folder_id':                        selected_folder_id,
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
