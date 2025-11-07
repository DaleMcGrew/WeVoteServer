# candidate/controllers_data_cleaning.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-
from datetime import datetime

from django.db.models import Q
from config.base import get_environment_variable
from django.db.models.functions import Length

from politician.models import PoliticianManager
import wevote_functions.admin
from wevote_functions.functions import convert_to_int, positive_value_exists
from wevote_functions.functions_date import convert_we_vote_date_string_to_date_as_integer, \
    generate_localized_datetime_from_obj, get_current_year_as_integer
from .models import CandidateCampaign, CandidateListManager

logger = wevote_functions.admin.get_logger(__name__)

WE_VOTE_SERVER_ROOT_URL = get_environment_variable("WE_VOTE_SERVER_ROOT_URL")


def augment_candidate_with_ultimate_election_date(candidate, elections_dict={}):
    """
    Update the values in the candidate object with new "candidate_ultimate_election_date" and "candidate_year"
    but don't save. (Saving happens outside of this function.)
    NOTE: Similar to generate_candidate_position_sorting_dates - perhaps refactor both?
    :param candidate:
    :param elections_dict:
    :return:
    """
    candidate_ultimate_election_date = None
    candidate_year = None
    status = ''
    success = True
    values_changed = False

    if not candidate or not hasattr(candidate, 'candidate_ultimate_election_date'):
        status += "CANDIDATE_MISSING "
        success = False
        return {
            'candidate':        candidate,
            'elections_dict':   elections_dict,
            # 'latest_office_we_vote_id': latest_office_we_vote_id,
            'success':          success,
            'status':           status,
            'values_changed':   values_changed,
        }
    candidate_list_manager = CandidateListManager()
    results = candidate_list_manager.retrieve_candidate_to_office_link_list(
        candidate_we_vote_id_list=[candidate.we_vote_id],
        read_only=True)
    candidate_to_office_link_list = results['candidate_to_office_link_list']
    latest_election_date = 0
    # latest_office_we_vote_id = ''
    for candidate_to_office_link in candidate_to_office_link_list:
        try:
            if candidate_to_office_link.google_civic_election_id in elections_dict:
                this_election = elections_dict[candidate_to_office_link.google_civic_election_id]
            else:
                this_election = candidate_to_office_link.election()
                try:
                    if positive_value_exists(this_election.google_civic_election_id) \
                            and this_election.google_civic_election_id not in elections_dict:
                        elections_dict[this_election.google_civic_election_id] = this_election
                except Exception as e:
                    status += "COULD_NOT_ADD_ELECTION_TO_DICT: " + str(e) + " "
            election_day_as_integer = convert_we_vote_date_string_to_date_as_integer(this_election.election_day_text)
            if election_day_as_integer > latest_election_date:
                candidate_ultimate_election_date = election_day_as_integer
                election_day_as_string = str(election_day_as_integer)
                year = election_day_as_string[:4]
                if year:
                    candidate_year = convert_to_int(year)
                latest_election_date = election_day_as_integer
                # latest_office_we_vote_id = candidate_to_office_link.contest_office_we_vote_id
        except Exception as e:
            status += "PROBLEM_GETTING_ELECTION_INFORMATION: " + str(e) + " "

    # Now that we have cycled through all the candidate_to_office_link_list, augment the candidate
    if positive_value_exists(candidate_ultimate_election_date) \
            and candidate_ultimate_election_date != candidate.candidate_ultimate_election_date:
        candidate.candidate_ultimate_election_date = candidate_ultimate_election_date
        values_changed = True
    if positive_value_exists(candidate_year) \
            and candidate_year != candidate.candidate_year:
        candidate.candidate_year = candidate_year
        values_changed = True
    return {
        'candidate':                candidate,
        'elections_dict':           elections_dict,
        # 'latest_office_we_vote_id': latest_office_we_vote_id,
        'success':                  success,
        'status':                   status,
        'values_changed':           values_changed,
    }


def augment_candidate_with_contest_office_data(candidate, office):
    """
    Update the values in the candidate object with new "contest_office_name" and "district_name"
    but don't save. (Saving happens outside this function.)
    :param candidate:
    :param office:
    :return:
    """
    status = ''
    success = True
    values_changed = False

    error_results = {
        'candidate':        candidate,
        'success':          success,
        'status':           status,
        'values_changed':   values_changed,
    }

    if not candidate or not hasattr(candidate, 'contest_office_name'):
        status += "CANDIDATE_MISSING "
        error_results['status'] = status
        error_results['success'] = False
        return error_results

    if not office or not hasattr(office, 'google_civic_election_id'):
        status += "OFFICE_MISSING "
        error_results['status'] = status
        error_results['success'] = False
        return error_results

    if positive_value_exists(office.office_name) \
            and office.office_name != candidate.contest_office_name:
        candidate.contest_office_name = office.office_name
        values_changed = True
    if positive_value_exists(office.district_name) \
            and office.district_name != candidate.district_name:
        candidate.district_name = office.district_name
        values_changed = True
    if positive_value_exists(office.ballotpedia_race_office_level) \
            and office.ballotpedia_race_office_level != candidate.race_office_level:
        candidate.race_office_level = office.ballotpedia_race_office_level
        values_changed = True
    return {
        'candidate':                candidate,
        'status':                   status,
        'success':                  success,
        'values_changed':           values_changed,
    }


def campaignx_we_vote_id_updates(
        google_civic_election_id_list=None,
        number_to_update=1000,
        state_code=None,
):
    cleaning_candidate_list = []
    current_year = get_current_year_as_integer()
    starting_year = current_year - 1  # Start with prior year
    status = ''
    success = True
    total_to_convert_after = 0

    # After initial updates to all candidates, include in the search logic to find candidates with
    # linked_campaignx_we_vote_id_date_last_updated older than:
    # Politician.linked_campaignx_we_vote_id_date_last_updated

    # Find all candidates in this election
    candidates_to_update_we_vote_id_list = []
    if google_civic_election_id_list and len(google_civic_election_id_list) > 0:
        candidate_list_manager = CandidateListManager()
        results = candidate_list_manager.retrieve_candidate_to_office_link_list(
            google_civic_election_id_list=google_civic_election_id_list,
            read_only=True)
        candidate_to_office_link_list = results['candidate_to_office_link_list']
        candidates_to_update_we_vote_id_list = []
        for candidate_to_office_link in candidate_to_office_link_list:
            if candidate_to_office_link.candidate_we_vote_id not in candidates_to_update_we_vote_id_list:
                candidates_to_update_we_vote_id_list.append(candidate_to_office_link.candidate_we_vote_id)

    try:
        queryset = CandidateCampaign.objects.all()
        if candidates_to_update_we_vote_id_list and len(candidates_to_update_we_vote_id_list) > 0:
            queryset = queryset.filter(we_vote_id__in=candidates_to_update_we_vote_id_list)
        elif positive_value_exists(starting_year):
            queryset = queryset.filter(candidate_year__gte=starting_year)
        queryset = queryset.exclude(
            Q(politician_we_vote_id__isnull=True) |
            Q(politician_we_vote_id="")
        )
        queryset = queryset.filter(
            Q(linked_campaignx_we_vote_id__isnull=True) |
            Q(linked_campaignx_we_vote_id="")
        )
        if positive_value_exists(state_code):
            queryset = queryset.filter(state_code__iexact=state_code)
        total_to_convert = queryset.count()
        total_to_convert_after = total_to_convert - number_to_update if total_to_convert > number_to_update else 0
        queryset = queryset.order_by('-id')
        cleaning_candidate_list = list(queryset[:number_to_update])
    except Exception as e:
        status += "COULD_NOT_UPDATE_CANDIDATE_CAMPAIGNX_WE_VOTE_ID: " + str(e) + " "
        success = False

    politician_we_vote_id_list = []
    # Retrieve all relevant politicians in a single query
    for one_candidate in cleaning_candidate_list:
        politician_we_vote_id_list.append(one_candidate.politician_we_vote_id)
    politician_manager = PoliticianManager()
    politician_list = []
    if politician_we_vote_id_list and len(politician_we_vote_id_list) > 0:
        politician_results = politician_manager.retrieve_politician_list(
            politician_we_vote_id_list=politician_we_vote_id_list)
        politician_list = politician_results['politician_list']
    politician_dict_list = {}
    for one_politician in politician_list:
        politician_dict_list[one_politician.we_vote_id] = one_politician

    datetime_now = generate_localized_datetime_from_obj()[1]
    linked_campaignx_we_vote_id_missing = 0
    update_list = []
    updates_needed = False
    updates_made = 0
    candidate_without_linked_campaignx_we_vote_id_status = ""
    for one_candidate in cleaning_candidate_list:
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
        status += \
            "{linked_campaignx_we_vote_id_missing:,} " \
            "politicians attached to candidates missing linked_campaignx_we_vote_id. " \
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
            status += \
                "{updates_made:,} candidates updated with new linked_campaignx_we_vote_id. " \
                "{total_to_convert_after:,} remaining." \
                "".format(
                    total_to_convert_after=total_to_convert_after,
                    updates_made=updates_made)
        except Exception as e:
            status += \
                "{updates_made:,} candidates NOT updated with new linked_campaignx_we_vote_id. " \
                "{total_to_convert_after:,} remaining. ERROR: {error}" \
                "".format(
                    error=str(e),
                    total_to_convert_after=total_to_convert_after,
                    updates_made=updates_made)
    else:
        status += "NO_CAMPAIGNX_WE_VOTE_ID_UPDATES_NEEDED "
    if positive_value_exists(status):
        status = \
            "SCRIPT campaignx_we_vote_id_updates: " + status + " "

    return {
        'status':                   status,
        'success':                  success,
    }


def populate_candidates_ultimate_election_date(
        google_civic_election_id_list=None,
        number_to_populate=1000,
        state_code=None,
):
    candidate_bulk_update_list = []
    candidates_updated = 0
    candidates_not_updated = 0
    cleaning_candidate_list = []
    current_year = get_current_year_as_integer()
    starting_year = current_year - 1  # Start with prior year
    elections_dict = {}
    status = ''
    success = True

    # Find all candidates in this election
    candidates_to_update_we_vote_id_list = []
    if google_civic_election_id_list and len(google_civic_election_id_list) > 0:
        candidate_list_manager = CandidateListManager()
        results = candidate_list_manager.retrieve_candidate_to_office_link_list(
            google_civic_election_id_list=google_civic_election_id_list,
            read_only=True)
        candidate_to_office_link_list = results['candidate_to_office_link_list']
        candidates_to_update_we_vote_id_list = []
        for candidate_to_office_link in candidate_to_office_link_list:
            if candidate_to_office_link.candidate_we_vote_id not in candidates_to_update_we_vote_id_list:
                candidates_to_update_we_vote_id_list.append(candidate_to_office_link.candidate_we_vote_id)

    # Now get all candidates we want to update, with a single query
    try:
        queryset = CandidateCampaign.objects.all()
        if candidates_to_update_we_vote_id_list and len(candidates_to_update_we_vote_id_list) > 0:
            queryset = queryset.filter(we_vote_id__in=candidates_to_update_we_vote_id_list)
        elif positive_value_exists(starting_year):
            queryset = queryset.filter(candidate_year__gte=starting_year)
        queryset = queryset.filter(candidate_ultimate_election_date_calculated=False)
        # For now, restrict to those who don't have candidate_ultimate_election_date. In the future, we could remove
        #  this to refresh the candidate_ultimate_election_date data for all candidates.
        queryset = queryset.filter(
            Q(candidate_ultimate_election_date=0) | Q(candidate_ultimate_election_date__isnull=True))
        if positive_value_exists(state_code):
            queryset = queryset.filter(state_code__iexact=state_code)

        candidate_ultimate_count = queryset.count()
        if positive_value_exists(candidate_ultimate_count):
            status += \
                "SCRIPT: {entries_to_process:,} entries to process (populate_candidates_ultimate_election_date) " \
                "".format(entries_to_process=candidate_ultimate_count) + " "
        # Now process
        cleaning_candidate_list = queryset[:number_to_populate]
    except Exception as e:
        status += "FAILED_RETRIEVING_CANDIDATES: " + str(e) + " "

    for one_candidate in cleaning_candidate_list:
        results = augment_candidate_with_ultimate_election_date(
            candidate=one_candidate,
            elections_dict=elections_dict)
        if results['success']:
            elections_dict = results['elections_dict']
        if results['values_changed']:
            candidate_to_update = results['candidate']
            candidate_to_update.candidate_ultimate_election_date_calculated = True
            candidate_bulk_update_list.append(candidate_to_update)
            candidates_updated += 1
        else:
            one_candidate.candidate_ultimate_election_date_calculated = True
            candidate_bulk_update_list.append(one_candidate)
            candidates_not_updated += 1
    if candidate_bulk_update_list and len(candidate_bulk_update_list) > 0:
        try:
            CandidateCampaign.objects.bulk_update(
                candidate_bulk_update_list,
                ['candidate_ultimate_election_date',
                 'candidate_ultimate_election_date_calculated',
                 'candidate_year'])
        except Exception as e:
            status += "FAILED_BULK_UPDATE: " + str(e) + " "
    else:
        status += "NO_CANDIDATE_ULTIMATE_ELECTION_DATE_UPDATES_NEEDED "

    if positive_value_exists(candidates_updated):
        status += \
            "candidates_updated: " + str(candidates_updated) + " "
    if positive_value_exists(candidates_not_updated):
        status += \
            "candidates_not_updated: " + str(candidates_not_updated) + " "

    results = {
        'status': status,
        'success': success,
    }
    return results


def populate_contest_office_data(
        google_civic_election_id_list=None,
        number_to_populate=1000,
        show_candidates_with_email=False,
        state_code=None,
):
    candidate_bulk_update_list = []
    cleaning_candidate_list = []
    current_year = get_current_year_as_integer()
    starting_year = current_year - 1  # Start with prior year
    status = ''
    success = True

    # Find all candidates in this election
    candidates_to_update_we_vote_id_list = []
    if google_civic_election_id_list and len(google_civic_election_id_list) > 0:
        candidate_list_manager = CandidateListManager()
        results = candidate_list_manager.retrieve_candidate_to_office_link_list(
            google_civic_election_id_list=google_civic_election_id_list,
            read_only=True)
        candidate_to_office_link_list = results['candidate_to_office_link_list']
        candidates_to_update_we_vote_id_list = []
        for candidate_to_office_link in candidate_to_office_link_list:
            if candidate_to_office_link.candidate_we_vote_id not in candidates_to_update_we_vote_id_list:
                candidates_to_update_we_vote_id_list.append(candidate_to_office_link.candidate_we_vote_id)

    try:
        datetime_now = datetime.now()
        date_string = datetime_now.strftime('%Y%m%d')
        date_int = int(date_string)
    except Exception as e:
        date_int = 20240101

    try:
        queryset = CandidateCampaign.objects.all()
        if candidates_to_update_we_vote_id_list and len(candidates_to_update_we_vote_id_list) > 0:
            queryset = queryset.filter(we_vote_id__in=candidates_to_update_we_vote_id_list)
        else:
            queryset = queryset.filter(
                Q(candidate_ultimate_election_date__gt=date_int) |
                Q(candidate_year__gte=starting_year)
            )
        queryset = queryset.filter(contest_office_name_calculated=False)
        if positive_value_exists(state_code):
            queryset = queryset.filter(state_code__iexact=state_code)
        # Restrict to entries with BOTH contest_office_name and district_name empty
        #  OR race_office_level null or empty
        queryset = queryset.filter(
            ((Q(contest_office_name__isnull=True) | Q(contest_office_name='')) &
             (Q(district_name__isnull=True) | Q(district_name=''))) |
            (Q(race_office_level__isnull=True) | Q(race_office_level=''))
        )
        candidate_ultimate_count = queryset.count()
        if positive_value_exists(candidate_ultimate_count):
            status += \
                "SCRIPT: {entries_to_process:,} entries to process (populate_contest_office_data). " \
                "".format(entries_to_process=candidate_ultimate_count) + " "

        # Filter candidates based on whether they have an email address
        if positive_value_exists(show_candidates_with_email):
            queryset = queryset.annotate(candidate_email_length=Length('candidate_email'))
            queryset = queryset.filter(
                Q(candidate_email_length__gt=2)
            )

        # Now process
        cleaning_candidate_list = queryset[:number_to_populate]
    except Exception as e:
        status += "FAILED_RETRIEVING_CANDIDATES_POPULATE_CONTEST_OFFICE: " + str(e) + " "

    candidates_updated = 0
    candidates_not_matched = 0
    candidates_not_updated = 0
    candidate_to_office_link_list = []
    cleaning_candidate_we_vote_id_list = []
    contest_office_by_we_vote_id_dict = {}
    contest_office_list = []
    contest_office_we_vote_id_list = []
    office_by_candidate_we_vote_id_dict = {}
    for candidate in cleaning_candidate_list:
        # Collect candidate_we_vote_id_list, so we can retrieve linked offices first
        if candidate.we_vote_id not in cleaning_candidate_we_vote_id_list:
            cleaning_candidate_we_vote_id_list.append(candidate.we_vote_id)

    # Retrieve all CandidateToOfficeLink objects for these candidates
    if cleaning_candidate_we_vote_id_list and len(cleaning_candidate_we_vote_id_list) > 0:
        candidate_list_manager = CandidateListManager()
        results = candidate_list_manager.retrieve_candidate_to_office_link_list(
            candidate_we_vote_id_list=cleaning_candidate_we_vote_id_list,
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
    if contest_office_we_vote_id_list and len(contest_office_we_vote_id_list) > 0:
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
        for candidate in cleaning_candidate_list:
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

    why_candidates_did_not_update = "WHY_CANDIDATES_DID_NOT_UPDATE_EXAMPLES: [["
    for candidate in cleaning_candidate_list:
        if positive_value_exists(candidate.we_vote_id) and \
                candidate.we_vote_id in office_by_candidate_we_vote_id_dict:
            contest_office = office_by_candidate_we_vote_id_dict[candidate.we_vote_id]
            if hasattr(contest_office, 'district_name'):  # Make sure legit office object
                results = augment_candidate_with_contest_office_data(
                    candidate=candidate,
                    office=contest_office)
                if results['values_changed']:
                    candidate_augmented = results['candidate']
                    candidate_augmented.contest_office_name_calculated = True
                    candidate_bulk_update_list.append(candidate_augmented)
                    candidates_updated += 1
                else:
                    candidate.contest_office_name_calculated = True
                    candidate_bulk_update_list.append(candidate)
                    candidates_not_updated += 1
                    if candidates_not_updated < 5:
                        why_candidates_did_not_update += "[" + contest_office.office_name + " (" + \
                                                         contest_office.we_vote_id + ") "
                        why_candidates_did_not_update += "/ " + candidate.candidate_name + " (" + \
                                                         candidate.we_vote_id + ")] "
        else:
            candidate.contest_office_name_calculated = True
            candidate_bulk_update_list.append(candidate)
            candidates_not_matched += 1
            if candidates_not_matched < 5:
                why_candidates_did_not_update += "[ " + candidate.candidate_name + " (" + \
                                                 candidate.we_vote_id + ")] "
    why_candidates_did_not_update += "]] "
    if candidate_bulk_update_list and len(candidate_bulk_update_list) > 0:
        try:
            CandidateCampaign.objects.bulk_update(
                candidate_bulk_update_list, [
                    'contest_office_name', 'contest_office_name_calculated', 'district_name', 'race_office_level',
                ])
        except Exception as e:
            success = False
            status += "FAILED_BULK_UPDATE_POPULATE_CONTEST_OFFICE: " + str(e) + " "
    else:
        status += "POPULATE_CONTEST_OFFICE_DATA_NO_CANDIDATES_UPDATED "

    # If there are some leftover entries which we can't update, we don't want to show a message like this forever:
    #  SCRIPT: 7 entries to process (populate_contest_office_data).
    candidates_updated_or_not_updated = False
    if positive_value_exists(candidates_updated):
        status += "candidates_updated: " + str(candidates_updated) + " "
        candidates_updated_or_not_updated = True
    if positive_value_exists(candidates_not_updated) or positive_value_exists(candidates_not_matched):
        status += \
            "candidates_not_updated: " + str(candidates_not_updated) + " " + \
            "candidates_not_matched: " + str(candidates_not_matched) + " " + \
            why_candidates_did_not_update + " "
        candidates_updated_or_not_updated = True

    results = {
        'candidates_updated_or_not_updated': candidates_updated_or_not_updated,
        'status': status,
        'success': success,
    }
    return results


def batch_process_maintenance_scripts_candidate():
    status = ' :||: '
    success = True

    # ##################
    # Update the Candidate's ultimate election date
    results = populate_candidates_ultimate_election_date(
        number_to_populate=1000,
    )
    if positive_value_exists(results['status']):
        status += results['status'] + ":||: "

    # ##################
    # We use contest_office_name and/or district_name some places. Update candidates missing this data.
    results = populate_contest_office_data(
        number_to_populate=1000,
    )
    if positive_value_exists(results['status']):
        status += results['status'] + " :||: "

    # ##################
    # Update candidates who currently don't have seo_friendly_path, if there is seo_friendly_path
    #  in linked politician
    results = seo_friendly_path_updates(
        number_to_update=1000,
    )
    if positive_value_exists(results['status']):
        status += results['status'] + " :||: "

    # ##################
    # Update candidates who currently don't have linked_campaignx_we_vote_id, with value from linked politician
    results = campaignx_we_vote_id_updates(
        number_to_update=1000,
    )
    if positive_value_exists(results['status']):
        status += results['status'] + " :||: "

    results = {
        'status': status,
        'success': success,
    }
    return results


def seo_friendly_path_updates(
        google_civic_election_id_list=None,
        number_to_update=1000,
        state_code=None,
):
    cleaning_candidate_list = []
    current_year = get_current_year_as_integer()
    starting_year = current_year - 1  # Start with prior year
    status = ''
    success = True
    total_to_convert_after = 0

    # Find all candidates in this election
    candidates_to_update_we_vote_id_list = []
    if google_civic_election_id_list and len(google_civic_election_id_list) > 0:
        candidate_list_manager = CandidateListManager()
        results = candidate_list_manager.retrieve_candidate_to_office_link_list(
            google_civic_election_id_list=google_civic_election_id_list,
            read_only=True)
        candidate_to_office_link_list = results['candidate_to_office_link_list']
        candidates_to_update_we_vote_id_list = []
        for candidate_to_office_link in candidate_to_office_link_list:
            if candidate_to_office_link.candidate_we_vote_id not in candidates_to_update_we_vote_id_list:
                candidates_to_update_we_vote_id_list.append(candidate_to_office_link.candidate_we_vote_id)

    # Now get all candidates we want to update, with a single query
    try:
        queryset = CandidateCampaign.objects.all()
        if candidates_to_update_we_vote_id_list and len(candidates_to_update_we_vote_id_list) > 0:
            queryset = queryset.filter(we_vote_id__in=candidates_to_update_we_vote_id_list)
        elif positive_value_exists(starting_year):
            queryset = queryset.filter(candidate_year__gte=starting_year)

        queryset = queryset.exclude(
            Q(politician_we_vote_id__isnull=True) |
            Q(politician_we_vote_id="")
        )
        queryset = queryset.filter(
            Q(seo_friendly_path__isnull=True) |
            Q(seo_friendly_path="")
        )

        # After initial updates to all candidates, include in the search logic to find candidates with
        # seo_friendly_path_date_last_updated older than Politician.seo_friendly_path_date_last_updated
        if positive_value_exists(state_code):
            queryset = queryset.filter(state_code__iexact=state_code)
        total_to_convert = queryset.count()
        total_to_convert_after = total_to_convert - number_to_update if total_to_convert > number_to_update else 0
        queryset = queryset.order_by('-id')
        cleaning_candidate_list = list(queryset[:number_to_update])
    except Exception as e:
        status += "FAILED_RETRIEVING_CANDIDATES_FOR_SEO_FRIENDLY_PATH: " + str(e) + " "

    politician_we_vote_id_list = []
    # Retrieve all relevant politicians in a single query
    for one_candidate in cleaning_candidate_list:
        politician_we_vote_id_list.append(one_candidate.politician_we_vote_id)
    politician_manager = PoliticianManager()
    politician_list = []
    if politician_we_vote_id_list and len(politician_we_vote_id_list) > 0:
        politician_results = politician_manager.retrieve_politician_list(
            politician_we_vote_id_list=politician_we_vote_id_list)
        politician_list = politician_results['politician_list']
    politician_dict_list = {}
    for one_politician in politician_list:
        politician_dict_list[one_politician.we_vote_id] = one_politician

    datetime_now = generate_localized_datetime_from_obj()[1]
    seo_friendly_path_missing = 0
    update_list = []
    updates_needed = False
    updates_made = 0
    for one_candidate in cleaning_candidate_list:
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
        status += \
            "{seo_friendly_path_missing:,} missing seo_friendly_path (not found in Politician). " \
            "".format(seo_friendly_path_missing=seo_friendly_path_missing)

    if updates_needed:
        try:
            CandidateCampaign.objects.bulk_update(
                update_list, ['seo_friendly_path', 'seo_friendly_path_date_last_updated'])
            status += \
                "{updates_made:,} candidates updated with new seo_friendly_path. " \
                "{total_to_convert_after:,} remaining." \
                "".format(total_to_convert_after=total_to_convert_after, updates_made=updates_made)
        except Exception as e:
            status += "FAILED_MAKING_CANDIDATES_SEO_FRIENDLY_PATH_UPDATES: " + str(e) + " "
            success = False
    else:
        status += "NO_SEO_FRIENDLY_PATH_UPDATES_NEEDED "

    if positive_value_exists(status):
        status += "(SEO_UPDATE_SCRIPT) "

    results = {
        'status': status,
        'success': success,
    }
    return results
