# candidate/views_data_cleaning.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-
import json
from datetime import datetime
from time import time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.messages import get_messages
from django.db.models import Q
from django.db.models.functions import Length
from django.shortcuts import render

import wevote_functions.admin
from admin_tools.views import redirect_to_sign_in_page
from config.base import get_environment_variable
from politician.models import PoliticianManager
from voter.models import voter_has_authority
from wevote_functions.functions import convert_to_int, positive_value_exists, STATE_CODE_MAP
from wevote_functions.functions_date import generate_localized_datetime_from_obj
from .models import CandidateCampaign, CandidateListManager

CANDIDATES_SYNC_URL = get_environment_variable("CANDIDATES_SYNC_URL")  # candidatesSyncOut
TWITTER_API_ON = positive_value_exists(get_environment_variable("TWITTER_API_ON", no_exception=True))
WE_VOTE_SERVER_ROOT_URL = get_environment_variable("WE_VOTE_SERVER_ROOT_URL")
WEB_APP_ROOT_URL = get_environment_variable("WEB_APP_ROOT_URL")

logger = wevote_functions.admin.get_logger(__name__)


@login_required
def candidates_data_cleaning_view(request):
    # admin, analytics_admin, partner_organization, political_data_manager, political_data_viewer, verified_volunteer
    authority_required = {'partner_organization', 'political_data_viewer', 'verified_volunteer'}
    if not voter_has_authority(request, authority_required):
        return redirect_to_sign_in_page(request, authority_required)

    google_civic_election_id = convert_to_int(request.GET.get('google_civic_election_id', 0))
    messages_on_stage = get_messages(request)
    # run_scripts = positive_value_exists(request.GET.get('run_scripts', False))
    run_scripts = True
    state_code = request.GET.get('state_code', '')
    state_list = STATE_CODE_MAP
    sorted_state_list = sorted(state_list.items())

    page = convert_to_int(request.GET.get('page', 0))
    page = page if positive_value_exists(page) else 0  # Prevent negative pages
    show_candidates_with_email = positive_value_exists(request.GET.get('show_candidates_with_email', False))
    performance_process_dict = (request.GET.get('performance_process_dict', {}))
    status = ""

    performance_dict = {}

    if isinstance(performance_process_dict, str):
        try:
            performance_process_dict = json.loads(performance_process_dict)
            try:
                performance_dict.update(performance_process_dict)
            except Exception as e:
                status += "Error parsing performance_process_dict: {error}.format(error=e)"
        except json.JSONDecodeError:
            status += "Error decoding performance_process_dict: {error}.format(error=e)"

    performance_list = []
    performance_dict.update({
        'candidates_data_cleaning_view': performance_list,
    })

    candidate_list_manager = CandidateListManager()
    candidate_list = []
    candidate_we_vote_id_list = []

    # ################################################
    # Maintenance script section START
    # ################################################

    # If we are looking at one specific election, find all the candidates under that election and make sure each
    #  candidate entry has a value for candidate_ultimate_election_date. Note this won't update candidates
    #  who have the general election as their ultimate_election_date, if they lost in the primary. That will require
    #  an update to this script.
    populate_candidate_ultimate_election_date = True
    t0 = time()
    number_to_populate = 1000  # Normally we can process 10000 at a time
    if populate_candidate_ultimate_election_date and positive_value_exists(google_civic_election_id) and run_scripts:
        # We require google_civic_election_id just so we can limit the scope of this update
        populate_candidate_ultimate_election_date_status = ''
        # Find all candidates in this election
        results = candidate_list_manager.retrieve_candidate_to_office_link_list(
            google_civic_election_id_list=[google_civic_election_id],
            read_only=True)
        candidate_to_office_link_list = results['candidate_to_office_link_list']
        candidates_to_update_we_vote_id_list = []
        for candidate_to_office_link in candidate_to_office_link_list:
            if candidate_to_office_link.candidate_we_vote_id not in candidates_to_update_we_vote_id_list:
                candidates_to_update_we_vote_id_list.append(candidate_to_office_link.candidate_we_vote_id)

        # Now get all candidates we want to update, with a single query
        candidate_query = CandidateCampaign.objects.all()
        candidate_query = candidate_query.filter(we_vote_id__in=candidates_to_update_we_vote_id_list)
        # For now, restrict to those who don't have candidate_ultimate_election_date. In the future, we could remove
        #  this to refresh the candidate_ultimate_election_date data for all candidates.
        candidate_query = candidate_query.filter(
            Q(candidate_ultimate_election_date=0) | Q(candidate_ultimate_election_date__isnull=True))
        if positive_value_exists(state_code):
            candidate_query = candidate_query.filter(state_code__iexact=state_code)
        candidate_ultimate_count = candidate_query.count()
        if positive_value_exists(candidate_ultimate_count):
            populate_candidate_ultimate_election_date_status += \
                "SCRIPT: {entries_to_process:,} entries to process (populate_candidate_ultimate_election_date) " \
                "".format(entries_to_process=candidate_ultimate_count) + " "
        # Now process
        candidate_bulk_update_list = []
        candidate_list = candidate_query[:number_to_populate]
        candidates_updated = 0
        candidates_not_updated = 0
        elections_dict = {}
        from candidate.controllers import augment_candidate_with_ultimate_election_date
        for one_candidate in candidate_list:
            results = augment_candidate_with_ultimate_election_date(
                candidate=one_candidate,
                elections_dict=elections_dict)
            if results['success']:
                elections_dict = results['elections_dict']
            if results['values_changed']:
                candidate_bulk_update_list.append(results['candidate'])
                candidates_updated += 1
            else:
                candidates_not_updated += 1
        if len(candidate_bulk_update_list) > 0:
            try:
                CandidateCampaign.objects.bulk_update(
                    candidate_bulk_update_list,
                    ['candidate_ultimate_election_date',
                     'candidate_year'])
            except Exception as e:
                messages.add_message(request, messages.ERROR, "FAILED_BULK_UPDATE: " + str(e))

        if positive_value_exists(candidates_updated):
            populate_candidate_ultimate_election_date_status += \
                "candidates_updated: " + str(candidates_updated) + " "
        if positive_value_exists(candidates_not_updated):
            populate_candidate_ultimate_election_date_status += \
                "candidates_not_updated: " + str(candidates_updated) + " "
        if positive_value_exists(populate_candidate_ultimate_election_date_status):
            messages.add_message(request, messages.INFO, populate_candidate_ultimate_election_date_status)
    t1 = time()
    performance_snapshot = {
        'name': 'CandidateUltimateElectionDateRetrieve',
        'description': 'Looking at one election, find all the candidates under that election and make sure each '
                       'candidate entry has a value for candidate_ultimate_election_date.',
        'time_difference': t1 - t0,
    }
    performance_list.append(performance_snapshot)

    # We use the contest_office_name and/or district_name some places on WebApp. Update candidates missing this data.
    t0 = time()
    populate_contest_office_data = True
    number_to_populate = 500  # Normally we can process 1000 at a time
    if populate_contest_office_data and run_scripts:
        populate_contest_office_data_status = ''
        candidate_query = CandidateCampaign.objects.all()
        # Restrict to candidates who are in the future
        year_list = [2023, 2024]
        try:
            datetime_now = datetime.now()
            date_string = datetime_now.strftime('%Y%m%d')
            date_int = int(date_string)
        except Exception as e:
            date_int = 20240101
        candidate_query = candidate_query.filter(
            Q(candidate_ultimate_election_date__gt=date_int) |
            Q(candidate_year__in=year_list)
        )
        if positive_value_exists(state_code):
            candidate_query = candidate_query.filter(state_code__iexact=state_code)
        # Restrict to entries with BOTH contest_office_name and district_name empty
        #  OR race_office_level null or empty
        candidate_query = candidate_query.filter(
            ((Q(contest_office_name__isnull=True) | Q(contest_office_name='')) &
             (Q(district_name__isnull=True) | Q(district_name=''))) |
            (Q(race_office_level__isnull=True) | Q(race_office_level=''))
        )
        candidate_ultimate_count = candidate_query.count()
        if positive_value_exists(candidate_ultimate_count):
            populate_contest_office_data_status += \
                "SCRIPT: {entries_to_process:,} entries to process (populate_contest_office_data). " \
                "".format(entries_to_process=candidate_ultimate_count) + " "

        # Filter candidates based on whether they have an email address
        if positive_value_exists(show_candidates_with_email):
            candidate_query = candidate_query.annotate(candidate_email_length=Length('candidate_email'))
            candidate_query = candidate_query.filter(
                Q(candidate_email_length__gt=2)
            )

        # Now process
        candidate_bulk_update_list = []
        candidate_list = candidate_query[:number_to_populate]
        candidates_updated = 0
        candidates_not_updated = 0
        candidate_to_office_link_list = []
        candidate_we_vote_id_list = []
        contest_office_by_we_vote_id_dict = {}
        contest_office_list = []
        contest_office_we_vote_id_list = []
        office_by_candidate_we_vote_id_dict = {}
        from candidate.controllers import augment_candidate_with_contest_office_data
        for candidate in candidate_list:
            # Collect candidate_we_vote_id_list, so we can retrieve linked offices first
            if candidate.we_vote_id not in candidate_we_vote_id_list:
                candidate_we_vote_id_list.append(candidate.we_vote_id)

        # Retrieve all CandidateToOfficeLink objects for these candidates
        if len(candidate_we_vote_id_list) > 0:
            results = candidate_list_manager.retrieve_candidate_to_office_link_list(
                candidate_we_vote_id_list=candidate_we_vote_id_list,
                read_only=True
            )
            if results['candidate_to_office_link_list_found']:
                candidate_to_office_link_list = results['candidate_to_office_link_list']

        for one_link in candidate_to_office_link_list:
            if positive_value_exists(one_link.contest_office_we_vote_id) \
                    and one_link.contest_office_we_vote_id not in contest_office_we_vote_id_list:
                contest_office_we_vote_id_list.append(one_link.contest_office_we_vote_id)

        # Retrieve all the offices for these candidates
        from office.models import ContestOfficeListManager
        contest_office_list_manager = ContestOfficeListManager()
        if len(contest_office_we_vote_id_list) > 0:
            results = contest_office_list_manager.retrieve_offices(
                retrieve_from_this_office_we_vote_id_list=contest_office_we_vote_id_list,
                return_list_of_objects=True,
                read_only=True)
            if results['office_list_found']:
                contest_office_list = results['office_list_objects']
                for one_office in contest_office_list:
                    if hasattr(one_office, 'district_name'):  # Make sure legit office object
                        contest_office_by_we_vote_id_dict[one_office.we_vote_id] = one_office

        # Take CandidateToOfficeLink entries for each candidate, and figure out the contest_office object
        #  furthest in the future. We will use this to find the district_name and contest_office_name
        for office in contest_office_list:
            for candidate in candidate_list:
                for one_link in candidate_to_office_link_list:
                    # If the candidate and office match this candidate_to_office_link, proceed
                    if candidate.we_vote_id == one_link.candidate_we_vote_id \
                            and office.we_vote_id == one_link.contest_office_we_vote_id:
                        if candidate.we_vote_id in office_by_candidate_we_vote_id_dict:
                            # If this office is further in the future, replace the earlier version
                            try:
                                office_election_date_as_integer = convert_to_int(office.election_date_as_integer)
                            except Exception as e:
                                office_election_date_as_integer = 0
                            try:
                                office_by_candidate_we_vote_id = \
                                    office_by_candidate_we_vote_id_dict[candidate.we_vote_id]
                                if hasattr(office_by_candidate_we_vote_id, 'office_name'):
                                    office_election_date_from_dict_as_integer = \
                                        office_by_candidate_we_vote_id.election_date_as_integer
                                    office_election_date_from_dict_as_integer = \
                                        convert_to_int(office_election_date_from_dict_as_integer)
                                else:
                                    office_election_date_from_dict_as_integer = 0
                            except Exception as e:
                                office_election_date_from_dict_as_integer = 0
                            try:
                                if office_election_date_as_integer > office_election_date_from_dict_as_integer:
                                    office_by_candidate_we_vote_id_dict[candidate.we_vote_id] = office
                            except Exception as e:
                                pass
                        else:
                            office_by_candidate_we_vote_id_dict[candidate.we_vote_id] = office

        why_candidates_did_not_update = ""
        for candidate in candidate_list:
            if positive_value_exists(candidate.we_vote_id) and \
                    candidate.we_vote_id in office_by_candidate_we_vote_id_dict:
                contest_office = office_by_candidate_we_vote_id_dict[candidate.we_vote_id]
                if hasattr(contest_office, 'district_name'):  # Make sure legit office object
                    results = augment_candidate_with_contest_office_data(
                        candidate=candidate,
                        office=contest_office)
                    if results['values_changed']:
                        candidate_bulk_update_list.append(results['candidate'])
                        candidates_updated += 1
                    else:
                        candidates_not_updated += 1
                        if candidates_not_updated < 10:
                            why_candidates_did_not_update += "[" + contest_office.office_name + " (" + \
                                                             contest_office.we_vote_id + ") "
                            why_candidates_did_not_update += ":: " + candidate.candidate_name + " (" + \
                                                             candidate.we_vote_id + ")] "
        if len(candidate_bulk_update_list) > 0:
            try:
                CandidateCampaign.objects.bulk_update(
                    candidate_bulk_update_list, ['contest_office_name', 'district_name', 'race_office_level'])
            except Exception as e:
                messages.add_message(request, messages.ERROR, "FAILED_BULK_UPDATE: " + str(e))

        # If there are some leftover entries which we can't update, we don't want to show a message like this forever:
        #  SCRIPT: 7 entries to process (populate_contest_office_data).
        candidates_updated_or_not_updated = False
        if positive_value_exists(candidates_updated):
            populate_contest_office_data_status += "candidates_updated: " + str(candidates_updated) + " "
            candidates_updated_or_not_updated = True
        if positive_value_exists(candidates_not_updated):
            populate_contest_office_data_status += \
                "candidates_not_updated: " + str(candidates_not_updated) + " " + \
                why_candidates_did_not_update + " "
            candidates_updated_or_not_updated = True
        if candidates_updated_or_not_updated and positive_value_exists(populate_contest_office_data_status):
            messages.add_message(request, messages.INFO, populate_contest_office_data_status)

    t1 = time()
    performance_snapshot = {
        'name': 'UpdateMissingContestOfficeOrDistrictName',
        'description': 'Update candidates missing contest_office_name and/or district_name',
        'time_difference': t1 - t0,
    }
    performance_list.append(performance_snapshot)

    # Update candidates who currently don't have seo_friendly_path, if there is seo_friendly_path
    #  in linked politician
    number_to_update = 1000
    t0 = time()
    seo_friendly_path_updates = True
    if seo_friendly_path_updates and run_scripts:
        seo_friendly_path_updates_status = ""
        seo_update_query = CandidateCampaign.objects.all()
        seo_update_query = seo_update_query.exclude(
            Q(politician_we_vote_id__isnull=True) |
            Q(politician_we_vote_id="")
        )
        seo_update_query = seo_update_query.filter(
            Q(seo_friendly_path__isnull=True) |
            Q(seo_friendly_path="")
        )
        if positive_value_exists(google_civic_election_id):
            seo_update_query = seo_update_query.filter(we_vote_id__in=candidate_we_vote_id_list)
        # After initial updates to all candidates, include in the search logic to find candidates with
        # seo_friendly_path_date_last_updated older than Politician.seo_friendly_path_date_last_updated
        if positive_value_exists(state_code):
            seo_update_query = seo_update_query.filter(state_code__iexact=state_code)
        total_to_convert = seo_update_query.count()
        total_to_convert_after = total_to_convert - number_to_update if total_to_convert > number_to_update else 0
        seo_update_query = seo_update_query.order_by('-id')
        candidate_list = list(seo_update_query[:number_to_update])
        politician_we_vote_id_list = []
        # Retrieve all relevant politicians in a single query
        for one_candidate in candidate_list:
            politician_we_vote_id_list.append(one_candidate.politician_we_vote_id)
        politician_manager = PoliticianManager()
        politician_list = []
        if len(politician_we_vote_id_list) > 0:
            politician_results = politician_manager.retrieve_politician_list(
                politician_we_vote_id_list=politician_we_vote_id_list)
            politician_list = politician_results['politician_list']
        politician_dict_list = {}
        for one_politician in politician_list:
            politician_dict_list[one_politician.we_vote_id] = one_politician
        # timezone = pytz.timezone("America/Los_Angeles")
        # datetime_now = timezone.localize(datetime.now())
        datetime_now = generate_localized_datetime_from_obj()[1]
        seo_friendly_path_missing = 0
        update_list = []
        updates_needed = False
        updates_made = 0
        for one_candidate in candidate_list:
            one_politician = politician_dict_list.get(one_candidate.politician_we_vote_id)
            if hasattr(one_politician, 'seo_friendly_path') and positive_value_exists(one_politician.seo_friendly_path):
                one_candidate.seo_friendly_path = one_politician.seo_friendly_path
                one_candidate.seo_friendly_path_date_last_updated = datetime_now
                update_list.append(one_candidate)
                updates_needed = True
                updates_made += 1
            else:
                seo_friendly_path_missing += 1
        if positive_value_exists(seo_friendly_path_missing):
            seo_friendly_path_updates_status += \
                "{seo_friendly_path_missing:,} missing seo_friendly_path (not found in Politician). " \
                "".format(seo_friendly_path_missing=seo_friendly_path_missing)
        if updates_needed:
            CandidateCampaign.objects.bulk_update(
                update_list, ['seo_friendly_path', 'seo_friendly_path_date_last_updated'])
            seo_friendly_path_updates_status += \
                "{updates_made:,} candidates updated with new seo_friendly_path. " \
                "{total_to_convert_after:,} remaining." \
                "".format(total_to_convert_after=total_to_convert_after, updates_made=updates_made)
        if positive_value_exists(seo_friendly_path_updates_status):
            seo_friendly_path_updates_status += "(UPDATE_SCRIPT) "
            messages.add_message(request, messages.INFO, seo_friendly_path_updates_status)
    t1 = time()
    performance_snapshot = {
        'name': 'UpdateNoSEOPath',
        'description': 'Update candidates who do not have SEO friendly path',
        'time_difference': t1 - t0,
    }
    performance_list.append(performance_snapshot)

    # Update candidates who currently don't have linked_campaignx_we_vote_id, with value from linked politician
    t0 = time()
    number_to_update = 1000
    campaignx_we_vote_id_updates = True
    if campaignx_we_vote_id_updates and run_scripts:
        campaignx_we_vote_id_updates_status = ""
        # After initial updates to all candidates, include in the search logic to find candidates with
        # linked_campaignx_we_vote_id_date_last_updated older than:
        # Politician.linked_campaignx_we_vote_id_date_last_updated
        update_query = CandidateCampaign.objects.all()
        update_query = update_query.exclude(
            Q(politician_we_vote_id__isnull=True) |
            Q(politician_we_vote_id="")
        )
        update_query = update_query.filter(
            Q(linked_campaignx_we_vote_id__isnull=True) |
            Q(linked_campaignx_we_vote_id="")
        )
        # After initial updates to all candidates, include in the search logic to find candidates with
        # linked_campaignx_we_vote_id_date_last_updated older than
        # Politician.linked_campaignx_we_vote_id_date_last_updated
        if positive_value_exists(google_civic_election_id):
            update_query = update_query.filter(we_vote_id__in=candidate_we_vote_id_list)
        if positive_value_exists(state_code):
            update_query = update_query.filter(state_code__iexact=state_code)
        total_to_convert = update_query.count()
        total_to_convert_after = total_to_convert - number_to_update if total_to_convert > number_to_update else 0
        update_query = update_query.order_by('-id')
        candidate_list = list(update_query[:number_to_update])
        politician_we_vote_id_list = []
        # Retrieve all relevant politicians in a single query
        for one_candidate in candidate_list:
            politician_we_vote_id_list.append(one_candidate.politician_we_vote_id)
        politician_manager = PoliticianManager()
        politician_list = []
        if len(politician_we_vote_id_list) > 0:
            politician_results = politician_manager.retrieve_politician_list(
                politician_we_vote_id_list=politician_we_vote_id_list)
            politician_list = politician_results['politician_list']
        politician_dict_list = {}
        for one_politician in politician_list:
            politician_dict_list[one_politician.we_vote_id] = one_politician
        # timezone = pytz.timezone("America/Los_Angeles")
        # datetime_now = timezone.localize(datetime.now())
        datetime_now = generate_localized_datetime_from_obj()[1]
        linked_campaignx_we_vote_id_missing = 0
        update_list = []
        updates_needed = False
        updates_made = 0
        candidate_without_linked_campaignx_we_vote_id_status = ""
        for one_candidate in candidate_list:
            one_politician = politician_dict_list.get(one_candidate.politician_we_vote_id)
            if one_politician and hasattr(one_politician, 'linked_campaignx_we_vote_id') \
                    and positive_value_exists(one_politician.linked_campaignx_we_vote_id):
                one_candidate.linked_campaignx_we_vote_id = one_politician.linked_campaignx_we_vote_id
                one_candidate.linked_campaignx_we_vote_id_date_last_updated = datetime_now
                update_list.append(one_candidate)
                updates_needed = True
                updates_made += 1
            else:
                linked_campaignx_we_vote_id_missing += 1
                if linked_campaignx_we_vote_id_missing < 10:
                    candidate_without_linked_campaignx_we_vote_id_status += \
                        one_candidate.display_candidate_name() + \
                        " (" + one_candidate.we_vote_id + "/" + one_candidate.politician_we_vote_id + ") "
        if positive_value_exists(linked_campaignx_we_vote_id_missing):
            campaignx_we_vote_id_updates_status += \
                "{linked_campaignx_we_vote_id_missing:,} politicians missing linked_campaignx_we_vote_id. " \
                "(Add campaigns by visiting Campaigns list.) " \
                "EXAMPLES: {candidate_without_linked_campaignx_we_vote_id_status}" \
                "".format(
                    candidate_without_linked_campaignx_we_vote_id_status=
                    candidate_without_linked_campaignx_we_vote_id_status,
                    linked_campaignx_we_vote_id_missing=linked_campaignx_we_vote_id_missing)
        if updates_needed:
            try:
                CandidateCampaign.objects.bulk_update(
                    update_list, ['linked_campaignx_we_vote_id', 'linked_campaignx_we_vote_id_date_last_updated'])
                campaignx_we_vote_id_updates_status += \
                    "{updates_made:,} candidates updated with new linked_campaignx_we_vote_id. " \
                    "{total_to_convert_after:,} remaining." \
                    "".format(
                        total_to_convert_after=total_to_convert_after,
                        updates_made=updates_made)
            except Exception as e:
                campaignx_we_vote_id_updates_status += \
                    "{updates_made:,} candidates NOT updated with new linked_campaignx_we_vote_id. " \
                    "{total_to_convert_after:,} remaining. ERROR: {error}" \
                    "".format(
                        error=str(e),
                        total_to_convert_after=total_to_convert_after,
                        updates_made=updates_made)
        if positive_value_exists(campaignx_we_vote_id_updates_status):
            campaignx_we_vote_id_updates_status = \
                "SCRIPT campaignx_we_vote_id_updates: " + campaignx_we_vote_id_updates_status + " "
            messages.add_message(request, messages.INFO, campaignx_we_vote_id_updates_status)

    t1 = time()
    performance_snapshot = {
        'name': 'UpdateNoLinkedInCampaignXWeVoteId',
        'description': 'Update candidates who currently do not have linked_campaignx_we_vote_id',
        'time_difference': t1 - t0,
    }
    performance_list.append(performance_snapshot)

    # ################################################
    # Maintenance script section END
    # ################################################

    template_values = {
        'candidate_list':               candidate_list,
        'current_page_number':          page,
        'google_civic_election_id':     google_civic_election_id,
        'messages_on_stage':            messages_on_stage,
        'performance_dict':             performance_dict,
        'show_candidates_with_email':   show_candidates_with_email,
        'state_code':                   state_code,
        'state_list':                   sorted_state_list,
    }
    return render(request, 'candidate/candidate_data_cleaning.html', template_values)