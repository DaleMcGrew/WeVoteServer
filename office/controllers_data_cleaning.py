# office/controllers_data_cleaning.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-
from datetime import datetime

from django.db.models import Q
from config.environment_variable_functions import get_environment_variable
from django.db.models.functions import Length

from election.models import ElectionManager
import wevote_functions.admin
from wevote_functions.functions import convert_to_int, positive_value_exists
from wevote_functions.functions_date import convert_we_vote_date_string_to_date_as_integer, \
    generate_localized_datetime_from_obj, get_current_year_as_integer
from .models import ContestOffice

logger = wevote_functions.admin.get_logger(__name__)

WE_VOTE_SERVER_ROOT_URL = get_environment_variable("WE_VOTE_SERVER_ROOT_URL")


def batch_process_maintenance_scripts_office():
    status = ' :||: '
    success = True

    # ##################
    # Update the election_date_as_integer in all ContestOffice records
    results = add_election_date_as_integer_to_all_offices(
        number_to_update=1000,
    )
    if positive_value_exists(results['status']):
        status += results['status'] + ":||: "

    results = {
        'status': status,
        'success': success,
    }
    return results


def add_election_date_as_integer_to_all_offices(
        google_civic_election_id_list=None,
        number_to_update=1000,
        state_code=None,
):
    bulk_update_list = []
    election_day_text_by_election_id_dict = {}
    office_list = []
    offices_updated = 0
    offices_not_updated = 0
    status = ''
    success = True
    total_to_update = 0
    total_to_update_after = 0
    updates_needed = False

    election_manager = ElectionManager()
    if google_civic_election_id_list and len(google_civic_election_id_list) > 0:
        results = election_manager.retrieve_elections_by_google_civic_election_id_list(
            google_civic_election_id_list=google_civic_election_id_list)
        election_list = results['election_list']
    else:
        google_civic_election_id_list = []
        results = election_manager.retrieve_elections()
        election_list = results['election_list']
        for one_election in election_list:
            google_civic_election_id_list.append(one_election.google_civic_election_id)

    for one_election in election_list:
        if positive_value_exists(one_election.election_day_text) \
                and positive_value_exists(one_election.google_civic_election_id):
            election_day_text_by_election_id_dict[one_election.google_civic_election_id] = \
                convert_we_vote_date_string_to_date_as_integer(one_election.election_day_text)

    try:
        # Now get ContestOffice objects we want to update
        queryset = ContestOffice.objects.all()  # Cannot be readonly
        queryset = queryset.filter(
            Q(election_date_as_integer__isnull=True) |
            Q(election_date_as_integer=0)
        )
        if google_civic_election_id_list and len(google_civic_election_id_list) > 0:
            queryset = queryset.filter(google_civic_election_id__in=google_civic_election_id_list)
        if positive_value_exists(state_code):
            queryset = queryset.filter(state_code__iexact=state_code)
        queryset = queryset.exclude(google_civic_election_id='')
        total_to_update = queryset.count()
        total_to_update_after = total_to_update - number_to_update if total_to_update > number_to_update else 0
        office_list = queryset[:number_to_update]
    except Exception as e:
        status += "FAILED_RETRIEVING_OFFICES: " + str(e) + " "

    if positive_value_exists(total_to_update):
        status += \
            "ADD_ELECTION_DATE_SCRIPT: {total_to_update:,} entries to process " \
            "".format(total_to_update=total_to_update) + " "

    try:
        for one_office in office_list:
            if one_office.google_civic_election_id in election_day_text_by_election_id_dict:
                election_date_as_integer = election_day_text_by_election_id_dict[one_office.google_civic_election_id]
                if positive_value_exists(election_date_as_integer):
                    one_office.election_date_as_integer = election_date_as_integer
                    bulk_update_list.append(one_office)
                    offices_updated += 1
                    updates_needed = True
                else:
                    offices_not_updated += 1
            else:
                offices_not_updated += 1
    except Exception as e:
        status += "FAILED_ADDING_OFFICES_TO_BULK_UPDATE_LIST: " + str(e) + " "

    if updates_needed:
        try:
            ContestOffice.objects.bulk_update(bulk_update_list, ['election_date_as_integer'])
            status += \
                "{offices_updated:,} offices updated with new election_date_as_integer. " \
                "{offices_not_updated:,} offices NOT updated. " \
                "{total_to_update_after:,} remaining. " \
                "".format(
                    offices_not_updated=offices_not_updated,
                    offices_updated=offices_updated,
                    total_to_update_after=total_to_update_after)
        except Exception as e:
            status += "FAILED_BULK_UPDATE: " + str(e) + " "
    else:
        status += "NO_ELECTION_DATE_UPDATES_NEEDED: " \
            "{offices_not_updated:,} offices NOT updated. " \
            "{total_to_update_after:,} remaining. " \
            "".format(
                offices_not_updated=offices_not_updated,
                total_to_update_after=total_to_update_after)

    results = {
        'status': status,
        'success': success,
    }
    return results
