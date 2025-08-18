# politician/views_data_cleaning.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.messages import get_messages
from django.db.models import Q
from django.shortcuts import render
import wevote_functions.admin
from admin_tools.views import redirect_to_sign_in_page
from config.base import get_environment_variable
from voter.models import voter_has_authority
from wevote_functions.functions import convert_to_int, positive_value_exists, STATE_CODE_MAP
from wevote_functions.functions_date import generate_localized_datetime_from_obj
from .controllers import add_alternate_names_to_next_spot, generate_campaignx_for_politician
from .models import Politician, PoliticianManager
from politician.controllers_generate_color import generate_background
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
    generate_google_civic_name_alternates = True
    number_to_generate = 1000
    if generate_google_civic_name_alternates and positive_value_exists(state_code) and run_scripts:
        politician_query = Politician.objects.all()
        politician_query = politician_query.filter(google_civic_name_alternates_generated=False)
        politician_query = politician_query.filter(state_code__iexact=state_code)
        total_to_convert = politician_query.count()
        total_to_convert_after = total_to_convert - number_to_generate if total_to_convert > number_to_generate else 0
        politician_list_to_convert = list(politician_query[:number_to_generate])
        update_list = []
        updates_needed = False
        updates_made = 0
        for one_politician in politician_list_to_convert:
            results = add_alternate_names_to_next_spot(
                politician=one_politician,
            )
            if results['values_changed']:
                politician = results['politician']
                politician.google_civic_name_alternates_generated = True
                update_list.append(politician)
                updates_needed = True
                updates_made += 1
            elif results['success']:
                one_politician.google_civic_name_alternates_generated = True
                update_list.append(one_politician)
                updates_needed = True
        if updates_needed:
            try:
                Politician.objects.bulk_update(update_list, [
                    'google_civic_name_alternates_generated',
                    'google_civic_candidate_name',
                    'google_civic_candidate_name2',
                    'google_civic_candidate_name3',
                ])
                messages.add_message(request, messages.INFO,
                                     "{updates_made:,} google_civic_name_alternates_generated. "
                                     "{total_to_convert_after:,} remaining."
                                     "".format(total_to_convert_after=total_to_convert_after,
                                               updates_made=updates_made))
            except Exception as e:
                messages.add_message(request, messages.ERROR,
                                     "ERROR with google_civic_name_alternates_generated: {e} "
                                     "".format(e=e))

    generate_backgrounds = True
    number_to_generate = 10
    if generate_backgrounds and positive_value_exists(state_code) and run_scripts:
        politician_query = Politician.objects.all()
        politician_query = politician_query.filter(state_code__iexact=state_code)
        politician_query = politician_query.exclude(profile_image_background_color_needed=False)
        total_to_convert = politician_query.count()
        total_to_convert_after = total_to_convert - number_to_generate if total_to_convert > number_to_generate else 0
        politician_list_to_convert = list(politician_query[:number_to_generate])
        update_list = []
        politicians_updated = 0
        politicians_not_updated = 0

        for politician in politician_list_to_convert:
            politician.profile_image_background_color_needed = False
            if positive_value_exists(politician.we_vote_hosted_profile_image_url_large):
                politician.profile_image_background_color = generate_background(politician)
                politicians_updated += 1
                update_list.append(politician)
            else:
                politicians_not_updated += 1

        if len(update_list) > 0:
            try:
                Politician.objects.bulk_update(update_list, ['profile_image_background_color',
                                                             'profile_image_background_color_needed'])
                message = \
                    "Politicians updated: {politicians_updated:,}. " \
                    "Politicians without picture URL:  {politicians_not_updated:,}. " \
                    "".format(politicians_updated=politicians_updated, politicians_not_updated=politicians_not_updated)
                messages.add_message(request, messages.INFO, message)
            except Exception as e:
                messages.add_message(request, messages.ERROR,
                                     "ERROR with update_profile_image_background_color_view: {e}"
                                     "".format(e=e))

    # Create seo_friendly_path for all politicians who currently don't have one
    generate_seo_friendly_path_updates = True  # Set False on local machine for now
    number_to_create = 1000
    if generate_seo_friendly_path_updates and run_scripts:
        politician_query = Politician.objects.all()
        politician_query = politician_query.filter(
            Q(seo_friendly_path__isnull=True) |
            Q(seo_friendly_path="")
        )
        if positive_value_exists(state_code):
            politician_query = politician_query.filter(state_code__iexact=state_code)
        total_to_convert = politician_query.count()
        total_to_convert_after = total_to_convert - number_to_create if total_to_convert > number_to_create else 0
        politician_list_to_convert = list(politician_query[:number_to_create])
        politician_manager = PoliticianManager()
        update_list = []
        updates_needed = False
        updates_made = 0
        # timezone = pytz.timezone("America/Los_Angeles")
        # datetime_now = timezone.localize(datetime.now())
        datetime_now = generate_localized_datetime_from_obj()[1]
        for one_politician in politician_list_to_convert:
            results = politician_manager.generate_seo_friendly_path(
                politician_name=one_politician.politician_name,
                politician_we_vote_id=one_politician.we_vote_id,
                state_code=one_politician.state_code,
            )
            if results['seo_friendly_path_found']:
                one_politician.seo_friendly_path = results['seo_friendly_path']
                one_politician.seo_friendly_path_date_last_updated = datetime_now
                update_list.append(one_politician)
                updates_needed = True
                updates_made += 1
        if updates_needed:
            try:
                Politician.objects.bulk_update(update_list,
                                               ['seo_friendly_path', 'seo_friendly_path_date_last_updated'])
                messages.add_message(request, messages.INFO,
                                     "{updates_made:,} politicians updated with new seo_friendly_path. "
                                     "{total_to_convert_after:,} remaining."
                                     "".format(total_to_convert_after=total_to_convert_after,
                                               updates_made=updates_made))
            except Exception as e:
                messages.add_message(request, messages.ERROR,
                                     "ERROR with generate_seo_friendly_path_updates: {e} "
                                     "".format(e=e))

    # Check all entries that have Politician.linked_campaignx_we_vote_id and
    #  make sure we have that corresponding CampaignX entry. If not, delete the Politician.linked_campaignx_we_vote_id
    #  value.
    delete_linked_campaignx_we_vote_id_if_campaignx_not_found = True
    number_to_create = 1000
    if delete_linked_campaignx_we_vote_id_if_campaignx_not_found and run_scripts:
        politician_query = Politician.objects.all()
        politician_query = politician_query.exclude(
            Q(linked_campaignx_we_vote_id__isnull=True) |
            Q(linked_campaignx_we_vote_id="")
        )
        politician_query = politician_query.filter(linked_campaignx_we_vote_id_verified=False)
        if positive_value_exists(state_code):
            politician_query = politician_query.filter(state_code__iexact=state_code)
        linked_campaignx_we_vote_id_list = \
            politician_query.values_list('linked_campaignx_we_vote_id', flat=True).distinct()
        linked_campaignx_we_vote_id_list = list(linked_campaignx_we_vote_id_list[:number_to_create])

        # Find existing CampaignX entries expected from the Politician.linked_campaignx_we_vote_id values
        from campaign.models import CampaignX
        existing_campaignx_we_vote_ids = set(CampaignX.objects.filter(
            we_vote_id__in=linked_campaignx_we_vote_id_list
        ).values_list('we_vote_id', flat=True))

        # Create a list of linked_campaignx_we_vote_ids that don't exist in CampaignX
        non_existent_campaignx_we_vote_ids = [
            we_vote_id for we_vote_id in linked_campaignx_we_vote_id_list
            if we_vote_id not in existing_campaignx_we_vote_ids
        ]

        records_cleared = 0
        total_to_convert = politician_query.count()
        total_to_convert_after = total_to_convert - number_to_create if total_to_convert > number_to_create else 0
        # politician_list_to_convert = list(politician_query[:number_to_create])
        update_list = []
        updates_needed = False
        updates_made = 0
        # timezone = pytz.timezone("America/Los_Angeles")
        # datetime_now = timezone.localize(datetime.now())
        datetime_now = generate_localized_datetime_from_obj()[1]
        if existing_campaignx_we_vote_ids:
            politician_unchanged_query = Politician.objects.filter(
                linked_campaignx_we_vote_id__in=existing_campaignx_we_vote_ids
            )
            politician_unchanged_list = list(politician_unchanged_query)
            for politician in politician_unchanged_list:
                politician.linked_campaignx_we_vote_id_date_last_updated = datetime_now
                politician.linked_campaignx_we_vote_id_verified = True
                update_list.append(politician)
                updates_needed = True
                updates_made += 1
        if non_existent_campaignx_we_vote_ids:
            politician_clear_query = Politician.objects.filter(
                linked_campaignx_we_vote_id__in=non_existent_campaignx_we_vote_ids
            )
            politician_list_to_clear = list(politician_clear_query)
            for politician in politician_list_to_clear:
                politician.linked_campaignx_we_vote_id = None
                politician.linked_campaignx_we_vote_id_date_last_updated = datetime_now
                politician.linked_campaignx_we_vote_id_verified = True
                update_list.append(politician)
                updates_needed = True
                updates_made += 1
                records_cleared += 1

        if updates_needed:
            try:
                Politician.objects.bulk_update(
                    update_list, [
                        'linked_campaignx_we_vote_id',
                        'linked_campaignx_we_vote_id_date_last_updated',
                        'linked_campaignx_we_vote_id_verified'])
                messages.add_message(
                    request, messages.INFO,
                    "{updates_made:,} politicians scanned for a current linked_campaignx_we_vote_id. "
                    "{records_cleared:,} records had Politician.linked_campaignx_we_vote_id cleared out. "
                    "{total_to_convert_after:,} remaining."
                    "".format(
                        records_cleared=records_cleared,
                        total_to_convert_after=total_to_convert_after,
                        updates_made=updates_made))
            except Exception as e:
                messages.add_message(request, messages.ERROR,
                                     "ERROR with delete_linked_campaignx_we_vote_id_if_campaignx_not_found: {e} "
                                     "".format(e=e))

    # Create default CampaignX for all politicians who currently don't have one
    generate_campaignx_for_every_politician = True
    number_to_create = 1000
    if generate_campaignx_for_every_politician and run_scripts:
        politician_query = Politician.objects.all()
        politician_query = politician_query.filter(
            Q(linked_campaignx_we_vote_id__isnull=True) |
            Q(linked_campaignx_we_vote_id="")
        )
        politician_query = politician_query.exclude(
            Q(seo_friendly_path__isnull=True) |
            Q(seo_friendly_path="")
        )
        if positive_value_exists(state_code):
            politician_query = politician_query.filter(state_code__iexact=state_code)
        total_to_convert = politician_query.count()
        total_to_convert_after = total_to_convert - number_to_create if total_to_convert > number_to_create else 0
        politician_list_to_convert = list(politician_query[:number_to_create])
        update_list = []
        updates_needed = False
        updates_made = 0
        # timezone = pytz.timezone("America/Los_Angeles")
        # datetime_now = timezone.localize(datetime.now())
        datetime_now = generate_localized_datetime_from_obj()[1]
        for one_politician in politician_list_to_convert:
            results = generate_campaignx_for_politician(
                datetime_now=datetime_now,
                politician=one_politician,
                save_individual_politician=False,
            )
            if results['success'] and results['campaignx_created']:
                one_politician = results['politician']
                update_list.append(one_politician)
                updates_needed = True
                updates_made += 1

        if updates_needed:
            try:
                Politician.objects.bulk_update(
                    update_list, ['linked_campaignx_we_vote_id', 'linked_campaignx_we_vote_id_date_last_updated'])
                messages.add_message(request, messages.INFO,
                                     "Generated CampaignX for {updates_made:,} politicians. "
                                     "{total_to_convert_after:,} remaining."
                                     "".format(total_to_convert_after=total_to_convert_after,
                                               updates_made=updates_made))
            except Exception as e:
                messages.add_message(request, messages.ERROR,
                                     "ERROR with generate_campaignx_for_every_politician: {e} "
                                     "".format(e=e))

    # Find all politicians with linked_campaignx_we_vote_id and make sure Campaignx
    # entry includes linked_politician_we_vote_id. If it doesn't, or linked_politician_we_vote_id in CampaignX entry
    # doesn't match the Politician.we_vote_id, update it.
    # We don't want to always leave this on
    update_campaignx_with_linked_politician_we_vote_id = True
    number_to_update = 7000  # We have to run this routine on the entire state
    if update_campaignx_with_linked_politician_we_vote_id and positive_value_exists(state_code) and run_scripts:
        update_campaignx_with_linked_politician_we_vote_id_status = ""
        politician_query = Politician.objects.all()
        politician_query = politician_query.exclude(
            Q(linked_campaignx_we_vote_id__isnull=True) |
            Q(linked_campaignx_we_vote_id="")
        )
        politician_query = politician_query.filter(state_code__iexact=state_code)
        total_to_convert = politician_query.count()
        total_to_convert_after = total_to_convert - number_to_update if total_to_convert > number_to_update else 0
        politician_list_to_convert = list(politician_query[:number_to_update])
        campaignx_we_vote_id_list = []
        politician_dict_by_campaign_we_vote_id = {}
        politicians_with_linked_campaignx_we_vote_id_count = 0
        for one_politician in politician_list_to_convert:
            if positive_value_exists(one_politician.linked_campaignx_we_vote_id):
                politicians_with_linked_campaignx_we_vote_id_count += 1
                if one_politician.linked_campaignx_we_vote_id not in campaignx_we_vote_id_list:
                    campaignx_we_vote_id_list.append(one_politician.linked_campaignx_we_vote_id)
                    politician_dict_by_campaign_we_vote_id[one_politician.linked_campaignx_we_vote_id] = one_politician

        update_list = []
        updates_needed = False
        updates_made = 0

        from campaign.models import CampaignX
        campaignx_query = CampaignX.objects.all()
        campaignx_query = campaignx_query.filter(we_vote_id__in=campaignx_we_vote_id_list)
        campaignx_list = list(campaignx_query)
        campaignx_with_linked_politician_we_vote_id_count = 0
        for one_campaignx in campaignx_list:
            if one_campaignx.we_vote_id in politician_dict_by_campaign_we_vote_id:
                one_politician = politician_dict_by_campaign_we_vote_id[one_campaignx.we_vote_id]
                if hasattr(one_politician, 'we_vote_id') and positive_value_exists(one_politician.we_vote_id):
                    if one_campaignx.linked_politician_we_vote_id != one_politician.we_vote_id:
                        one_campaignx.linked_politician_we_vote_id = one_politician.we_vote_id
                        update_list.append(one_campaignx)
                        updates_made += 1
                        if not updates_needed:
                            updates_needed = True

            if positive_value_exists(one_campaignx.linked_politician_we_vote_id):
                campaignx_with_linked_politician_we_vote_id_count += 1

        updates_error = False
        if updates_needed:
            try:
                CampaignX.objects.bulk_update(
                    update_list, ['linked_politician_we_vote_id'])
                update_campaignx_with_linked_politician_we_vote_id_status += \
                    "UPDATES MADE: {updates_made:,} politicians updated with new linked_campaignx_we_vote_id. " \
                    "{total_to_convert_after:,} remaining." \
                    "".format(
                        total_to_convert_after=total_to_convert_after,
                        updates_made=updates_made)
            except Exception as e:
                updates_error = True
                update_campaignx_with_linked_politician_we_vote_id_status += \
                    "ERROR with update_campaignx_with_linked_politician_we_vote_id: {e} " \
                    "".format(e=e)
        elif positive_value_exists(campaignx_with_linked_politician_we_vote_id_count):
            pass
            # update_campaignx_with_linked_politician_we_vote_id_status += \
            #     "NO UPDATES: {campaignx_with_linked_politician_we_vote_id_count} CampaignX entries " \
            #     "already have linked_politician_we_vote_id. " \
            #     "".format(
            #         campaignx_with_linked_politician_we_vote_id_count=campaignx_with_linked_politician_we_vote_id_count)
        if positive_value_exists(update_campaignx_with_linked_politician_we_vote_id_status):
            update_campaignx_with_linked_politician_we_vote_id_status = \
                update_campaignx_with_linked_politician_we_vote_id_status + \
                " (SCRIPT update_campaignx_with_linked_politician_we_vote_id) "

            message_type = messages.ERROR if updates_error else messages.INFO
            messages.add_message(request, message_type, update_campaignx_with_linked_politician_we_vote_id_status)

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
