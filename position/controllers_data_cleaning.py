# position/controllers_data_cleaning.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

from django.db.models import Q

from config.base import get_environment_variable
from candidate.models import CandidateCampaign
from politician.models import Politician, PoliticianManager
import wevote_functions.admin
from wevote_functions.functions import positive_value_exists
from wevote_functions.functions_date import generate_localized_datetime_from_obj
from .models import PositionEntered, PositionForFriends

POLITICIANS_SYNC_URL = get_environment_variable("POLITICIANS_SYNC_URL")  # politiciansSyncOut
TWITTER_API_ON = positive_value_exists(get_environment_variable("TWITTER_API_ON", no_exception=True))
WE_VOTE_SERVER_ROOT_URL = get_environment_variable("WE_VOTE_SERVER_ROOT_URL")
WEB_APP_ROOT_URL = get_environment_variable("WEB_APP_ROOT_URL")

logger = wevote_functions.admin.get_logger(__name__)


def batch_process_maintenance_scripts_position():
    status = ':||: '
    success = True

    # ##################
    # Make sure we have a version of the politician's name without a middle initial (for matching endorsements)
    results = add_politician_we_vote_ids_to_candidate_positions(
        number_to_update=1000,  # Should be 1000
    )
    if positive_value_exists(results['status']):
        status += results['status'] + " :||: "

    results = {
        'status': status,
        'success': success,
    }
    return results


def add_politician_we_vote_ids_to_candidate_positions(
        number_to_update=1000,
        state_code=None,
):
    """
    Find positions about candidates that are not linked to politicians. Get the politician_we_vote_id from the
    candidate (if linked) and update the position with that politician_we_vote_id.
    """
    candidate_we_vote_id_list = []
    candidates_retrieved = 0
    candidates_missing_politician_we_vote_id = 0
    positions_cannot_update_from_missing_politician_we_vote_id = 0
    position_list_to_update = []
    status = ''
    success = True
    total_to_convert = 0
    total_to_convert_after = 0
    update_list = []
    updates_made = 0
    updates_needed = False

    try:
        queryset = PositionEntered.objects.all()
        queryset = queryset.filter(politician_we_vote_id_analyzed=False)
        queryset = queryset.exclude(
            Q(candidate_campaign_we_vote_id__isnull=True) | Q(candidate_campaign_we_vote_id=""))
        # For now, we ignore Positions incorrectly linked to politician_we_vote_ids that have been deleted/merged.
        # Only update entries without a politician_we_vote_id
        queryset = queryset.filter(
            Q(politician_we_vote_id__isnull=True) | Q(politician_we_vote_id=""))
        if positive_value_exists(state_code):
            queryset = queryset.filter(state_code__iexact=state_code)
        total_to_convert = queryset.count()
        total_to_convert_after = total_to_convert - number_to_update if total_to_convert > number_to_update else 0

        position_list_to_update = list(queryset[:number_to_update])

        # Assemble a list of candidate_campaign_we_vote_id values from these positions
        if position_list_to_update and len(position_list_to_update) > 0:
            for one_position in position_list_to_update:
                if one_position.candidate_campaign_we_vote_id and \
                        one_position.candidate_campaign_we_vote_id not in candidate_we_vote_id_list:
                    candidate_we_vote_id_list.append(one_position.candidate_campaign_we_vote_id)
    except Exception as e:
        status += "ERROR_POSITION_QUERY_add_politician_we_vote_ids_to_candidate_positions query: {e} " \
                  "".format(e=e)
        success = False

    try:
        # Retrieve all Candidates objects referred to by position_list_to_update so we can get the
        #  find the politician_we_vote_id, and attach it directly to the Position
        queryset = CandidateCampaign.objects.all()
        queryset = queryset.filter(we_vote_id__in=candidate_we_vote_id_list)
        candidate_list = list(queryset)

        candidates_missing_politician_we_vote_id = \
            sum(1 for candidate in candidate_list if not positive_value_exists(candidate.politician_we_vote_id))

        candidate_to_politician_map = {
            candidate.we_vote_id: candidate.politician_we_vote_id
            for candidate in candidate_list
            if positive_value_exists(candidate.politician_we_vote_id)
        }
        candidates_retrieved = len(candidate_to_politician_map)

        # Cycle through position_list_to_update and update with politician_we_vote_id
        for position in position_list_to_update:
            if position.candidate_campaign_we_vote_id in candidate_to_politician_map:
                position.politician_we_vote_id = candidate_to_politician_map[position.candidate_campaign_we_vote_id]
                position.politician_we_vote_id_analyzed = True
                update_list.append(position)
                updates_made += 1
                updates_needed = True
            else:
                position.politician_we_vote_id_analyzed = True
                update_list.append(position)
                updates_needed = True
                positions_cannot_update_from_missing_politician_we_vote_id += 1
    except Exception as e:
        status += "ERROR_CANDIDATE_QUERY_add_politician_we_vote_ids_to_candidate_positions query: {e} " \
                  "".format(e=e)
        success = False

    if updates_needed:
        try:
            PositionEntered.objects.bulk_update(
                update_list, [
                    'politician_we_vote_id', 'politician_we_vote_id_analyzed'])
            status += \
                "add_politician_we_vote_ids_to_candidate_positions: " \
                "{total_to_convert:,} positions found to update. " \
                "{updates_made:,} positions updated with politician_we_vote_id, " \
                "from {candidates_retrieved:,} candidates. " \
                "{candidates_missing_politician_we_vote_id:,} candidates missing politician_we_vote_id. " \
                "{positions_cannot_update_from_missing_politician_we_vote_id:,} " \
                "positions cannot update from missing politician_we_vote_id. " \
                "{total_to_convert_after:,} remaining. " \
                "".format(
                    candidates_missing_politician_we_vote_id=candidates_missing_politician_we_vote_id,
                    candidates_retrieved=candidates_retrieved,
                    positions_cannot_update_from_missing_politician_we_vote_id=
                    positions_cannot_update_from_missing_politician_we_vote_id,
                    total_to_convert=total_to_convert,
                    total_to_convert_after=total_to_convert_after,
                    updates_made=updates_made)
        except Exception as e:
            status += "ERROR_POSITION_BULK_UPDATE_add_politician_we_vote_ids_to_candidate_positions: {e} " \
                "".format(e=e)
            success = False
    else:
        status += \
            "add_politician_we_vote_ids_to_candidate_positions: " \
            "{total_to_convert_after:,} remaining. " \
            "".format(
                total_to_convert_after=total_to_convert_after)

    results = {
        'status': status,
        'success': success,
    }
    return results

