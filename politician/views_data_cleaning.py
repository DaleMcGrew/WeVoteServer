# politician/views_data_cleaning.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.messages import get_messages
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from admin_tools.views import redirect_to_sign_in_page
from config.base import get_environment_variable
from voter.models import voter_has_authority
import wevote_functions.admin
from wevote_functions.functions import convert_to_int, positive_value_exists, STATE_CODE_MAP
from .models import Politician

POLITICIANS_SYNC_URL = get_environment_variable("POLITICIANS_SYNC_URL")  # politiciansSyncOut
TWITTER_API_ON = positive_value_exists(get_environment_variable("TWITTER_API_ON", no_exception=True))
WE_VOTE_SERVER_ROOT_URL = get_environment_variable("WE_VOTE_SERVER_ROOT_URL")
WEB_APP_ROOT_URL = get_environment_variable("WEB_APP_ROOT_URL")

logger = wevote_functions.admin.get_logger(__name__)


@login_required
def politicians_data_cleaning_view(request):
    # Pagination parameters
    page = int(request.GET.get('page', 0))  # Default to page 0
    # admin, analytics_admin, partner_organization, political_data_manager, political_data_viewer, verified_volunteer
    authority_required = {'partner_organization', 'political_data_viewer', 'verified_volunteer'}
    if not voter_has_authority(request, authority_required):
        return redirect_to_sign_in_page(request, authority_required)

    create_followers_on = positive_value_exists(request.GET.get('create_followers_on', False))
    politicians_to_create_followers_for = convert_to_int(request.GET.get('politicians_to_create_followers_for', 1000))
    google_civic_election_id = convert_to_int(request.GET.get('google_civic_election_id', 0))
    messages_on_stage = get_messages(request)
    politician_search = request.GET.get('politician_search', '')
    # run_scripts = positive_value_exists(request.GET.get('run_scripts', False))
    run_scripts = True
    state_code = request.GET.get('state_code', '')
    state_list = STATE_CODE_MAP
    sorted_state_list = sorted(state_list.items())

    # ################################################
    # Maintenance script section START
    # ################################################

    # When we were preparing to remove the field 'politician_email_address', we wanted to make sure
    # they had all be transferred. This verifies it.
    # # Are there any entries where politician_email doesn't match politician_email_address?
    # politician_query = Politician.objects.all()
    # politician_query = politician_query.exclude(
    #     Q(politician_email_address__isnull=True) |
    #     Q(politician_email_address="")
    # )
    # # Do not return entries where the values already match
    # politician_query = politician_query.exclude(politician_email__iexact=F('politician_email_address'))
    # list_found = list(politician_query[:10])  # Only find the first 10 entries
    # if len(list_found) > 0:
    #     we_vote_id_string = ''
    #     for one_politician in list_found:
    #         we_vote_id_string += str(one_politician.we_vote_id) + " "
    #     messages.add_message(request, messages.ERROR,
    #                          'politician_email mismatch with politician_email_address: ' + str(we_vote_id_string))

    # Make sure we have a version of the politician's name without a middle initial (for matching endorsements)
    generate_google_civic_name_alternates_on = True
    number_to_generate = 1000
    if generate_google_civic_name_alternates_on and run_scripts:
        from politician.controllers_data_cleaning import generate_google_civic_name_alternates
        results = generate_google_civic_name_alternates(number_to_generate=number_to_generate, state_code=state_code)
        if positive_value_exists(results['status']):
            messages.add_message(request, messages.INFO, results['status'])

    generate_politician_photo_backgrounds_on = True
    number_to_generate = 10
    if generate_politician_photo_backgrounds_on and run_scripts:
        from politician.controllers_data_cleaning import generate_politician_photo_backgrounds
        results = generate_politician_photo_backgrounds(number_to_generate=number_to_generate, state_code=state_code)
        if positive_value_exists(results['status']):
            messages.add_message(request, messages.INFO, results['status'])

    # Create seo_friendly_path for all politicians who currently don't have one
    generate_politician_seo_friendly_paths_on = True  # Set False on local machine for now
    number_to_create = 1000
    if generate_politician_seo_friendly_paths_on and run_scripts:
        from politician.controllers_data_cleaning import generate_politician_seo_friendly_paths
        results = generate_politician_seo_friendly_paths(number_to_create=number_to_create, state_code=state_code)
        if positive_value_exists(results['status']):
            messages.add_message(request, messages.INFO, results['status'])

    # Check all entries that have Politician.linked_campaignx_we_vote_id and
    #  make sure we have that corresponding CampaignX entry. If not, delete the Politician.linked_campaignx_we_vote_id
    #  value.
    delete_linked_campaignx_we_vote_id_if_campaignx_not_found_on = True
    number_to_verify = 5000
    if delete_linked_campaignx_we_vote_id_if_campaignx_not_found_on and run_scripts:
        from politician.controllers_data_cleaning import delete_linked_campaignx_we_vote_id_if_campaignx_not_found
        results = delete_linked_campaignx_we_vote_id_if_campaignx_not_found(
            number_to_verify=number_to_verify,
            state_code=state_code)
        if positive_value_exists(results['status']):
            messages.add_message(request, messages.INFO, results['status'])

    # Create default CampaignX for all politicians who currently don't have one
    generate_campaignx_for_every_politician_on = True
    number_to_create = 1000
    if generate_campaignx_for_every_politician_on and run_scripts:
        from politician.controllers_data_cleaning import generate_campaignx_for_every_politician
        results = generate_campaignx_for_every_politician(
            number_to_create=number_to_create,
            state_code=state_code)
        if positive_value_exists(results['status']):
            messages.add_message(request, messages.INFO, results['status'])

    # Find all politicians with linked_campaignx_we_vote_id and make sure Campaignx
    # entry includes linked_politician_we_vote_id. If it doesn't, or linked_politician_we_vote_id in CampaignX entry
    # doesn't match the Politician.we_vote_id, update it.
    update_campaignx_with_linked_politician_we_vote_id_on = True
    number_to_update = 1000
    if update_campaignx_with_linked_politician_we_vote_id_on and run_scripts:
        from politician.controllers_data_cleaning import update_campaignx_with_linked_politician_we_vote_id
        results = update_campaignx_with_linked_politician_we_vote_id(
            number_to_update=number_to_update,
            state_code=state_code)
        if positive_value_exists(results['status']):
            messages.add_message(request, messages.INFO, results['status'])

    if create_followers_on:
        # Find some Politicians we know have positions and Create FollowOrganization entries
        #  From PUBLIC positions and from FRIENDS_ONLY positions
        from follow.controllers import create_followers_from_politicians
        create_results = create_followers_from_politicians(
            number_to_create=politicians_to_create_followers_for, request=request, state_code=state_code)
        if positive_value_exists(create_results['info_message_to_print']):
            messages.add_message(request, messages.INFO, create_results['info_message_to_print'])
        if positive_value_exists(create_results['error_message_to_print']):
            messages.add_message(request, messages.ERROR, create_results['error_message_to_print'])

    # ################################################
    # Maintenance script section END
    # ################################################

    # ###############################
    # Count the number of Politicians who need an organization to be generated
    queryset = Politician.objects.using('readonly').all()
    queryset = queryset.filter(organization_analysis_needed=True)
    queryset = queryset.exclude(organization_manual_intervention_needed=True)
    if positive_value_exists(state_code):
        queryset = queryset.filter(state_code__iexact=state_code)
    organization_might_be_needed_count = queryset.count()

    # ###############################
    # Count the number of Politicians who need FollowOrganization entries to be generated
    queryset = Politician.objects.using('readonly').all()
    queryset = queryset.filter(follow_organization_analysis_complete=False)
    queryset = queryset.exclude(follow_organization_intervention_needed=True)
    if positive_value_exists(state_code):
        queryset = queryset.filter(state_code__iexact=state_code)
    politicians_need_followers_count = queryset.count()

    template_values = {
        'current_page_number':                  page,
        'google_civic_election_id':             google_civic_election_id,
        'messages_on_stage':                    messages_on_stage,
        'organization_might_be_needed_count':   organization_might_be_needed_count,
        'politician_search':                    politician_search,
        'politicians_need_followers_count':     politicians_need_followers_count,
        'state_code':                           state_code,
        'state_list':                           sorted_state_list,
    }
    return render(request, 'politician/politician_data_cleaning.html', template_values)


def update_is_claimed_profile_for_politicians(request):
    number_to_update = 5000
    state_code = request.GET.get('state_code', '')
    from politician.controllers_data_cleaning import update_is_claimed_profile_fields_in_bulk
    results = update_is_claimed_profile_fields_in_bulk(
        number_to_update=number_to_update,
        state_code=state_code,
    )
    if positive_value_exists(results['status']):
        if positive_value_exists(results['success']):
            messages.add_message(request, messages.INFO, results['status'])
        else:
            messages.add_message(request, messages.ERROR, results['status'])

    return HttpResponseRedirect(reverse('politician:politicians_data_cleaning', args=()))
