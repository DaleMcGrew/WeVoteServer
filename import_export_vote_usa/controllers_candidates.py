import json
import requests

from election.models import ElectionManager
from exception.models import handle_exception
from office.models import ContestOffice
from wevote_functions.functions import augment_vote_usa_office_id_with_suffix, extract_vote_usa_office_id, \
    extract_vote_usa_office_id_with_suffix, positive_value_exists
import wevote_functions.admin

from .models import VoteUSAApiCounterManager
from import_export_vote_usa.controllers import (
    VOTE_USA_API_KEY,
    VOTE_USA_CANDIDATE_QUERY_URL,
    HEADERS_FOR_VOTE_USA_API_CALL,
    VOTE_USA_CANDIDATE_QUERY_TYPE,
)


logger = wevote_functions.admin.get_logger(__name__)


def update_existing_candidates_from_candidates_api(google_civic_election_id=0, state_code=''):
    status = ""
    success = True

    election_manager = ElectionManager()
    results = election_manager.retrieve_election(google_civic_election_id)
    if not results['election_found']:
        success = False
        status += 'ELECTION_NOT_FOUND '
        results = {'success': success, 'status': status}
        return results
    
    election = results['election']
    election_day = election.election_day_text
    if not positive_value_exists(election_day):
        success = False
        status += 'ELECTION_DAY_MISSING '
        results = {'success': success, 'status': status}
        return results
    election_year_integer = int(election_day[:4])

    if not positive_value_exists(state_code):
        success = False
        status += 'STATE_CODE_MISSING '
        results = {'success': success, 'status': status}
        return results
    
    try:
        api_key = VOTE_USA_API_KEY
        response = requests.get(
            VOTE_USA_CANDIDATE_QUERY_URL,
            headers=HEADERS_FOR_VOTE_USA_API_CALL,
            params={
                "accessKey": api_key,
                "electionDay": election_day,
                "state": state_code,
            },
            timeout=30
        )
        
        try:
            structured_json = json.loads(response.text)
        except json.JSONDecodeError:
            success = False
            if 'maxJsonLength' in response.text:
                status += 'VOTE_USA_CANDIDATES_API_RESPONSE_TOO_LARGE_FOR_VOTE_USA_SERVER '
            else:
                status += 'VOTE_USA_CANDIDATES_API_INVALID_RESPONSE: ' + response.text
            logger.error(f"VoteUSA API unparsable response: {response.text}")
            results = {'success': success, 'status': status}
            return results

        candidates_structured_json = structured_json.get('candidates', [])
        if not positive_value_exists(candidates_structured_json):
            status += 'NO_CANDIDATES_FOUND_IN_API_RESPONSE '
            results = {'success': success, 'status': status}
            return results
    except Exception as e:
        success = False
        status += 'VOTE_USA_CANDIDATES_API_END_POINT_CRASH: ' + str(e) + ' '
        handle_exception(e, logger=logger, exception_message=status)
        results = {'success': success, 'status': status}
        return results
    
    if 'success' in structured_json and structured_json['success'] is False:
        success = False
        status += 'VOTE_USA_CANDIDATES_API_ERROR: ' + structured_json.get('status', '') + ' '
        results = {'success': success, 'status': status}
        return results
    
    try:
        # Use Vote USA API call counter to track the number of queries we are doing each day
        api_counter_manager = VoteUSAApiCounterManager()
        api_counter_manager.create_counter_entry(
            VOTE_USA_CANDIDATE_QUERY_TYPE,
            google_civic_election_id=google_civic_election_id)
        
        vote_usa_candidates_by_office = {}
        for candidate in candidates_structured_json:
            contests = candidate.get('contests', [])
            if not contests:
                continue
            raw_vote_usa_office_id = contests[0].get('id', '')
            if not raw_vote_usa_office_id:
                continue
            if raw_vote_usa_office_id not in vote_usa_candidates_by_office:
                vote_usa_candidates_by_office[raw_vote_usa_office_id] = []
            vote_usa_candidates_by_office[raw_vote_usa_office_id].append(candidate)
        
        # Raw VoteUSA office IDs include the election ID prefix (e.g. 'CA20221108GA|CAStateHouse51')
        # We extract the base ID and re-append the party suffix for primaries (e.g. 'CAStateHouse51|PD'),
        # or we use base ID as-is for general elections, special elections, and runoffs.
        vote_usa_to_wevote_office_id = {}
        for raw_vote_usa_office_id in vote_usa_candidates_by_office.keys():
            vote_usa_office_id = extract_vote_usa_office_id_with_suffix(raw_vote_usa_office_id)
            vote_usa_to_wevote_office_id[raw_vote_usa_office_id] = vote_usa_office_id
            
        contest_offices = ContestOffice.objects.filter(
            google_civic_election_id=google_civic_election_id,
            vote_usa_office_id__in=vote_usa_to_wevote_office_id.values()
        )
        
        contest_office_dict = {office.vote_usa_office_id: office for office in contest_offices}

        from import_export_google_civic.controllers import groom_and_store_google_civic_candidates_json_2021
        for raw_vote_usa_office_id, office_candidates in vote_usa_candidates_by_office.items():
            contest_office = contest_office_dict.get(vote_usa_to_wevote_office_id[raw_vote_usa_office_id])
            if not contest_office:
                status += 'CONTEST_OFFICE_NOT_FOUND_FOR_VOTE_USA_OFFICE_ID: ' + str(raw_vote_usa_office_id) + \
                    ' (' + str(len(office_candidates)) + ' candidates skipped) '
                continue
            # Create a different office for each political party primary race
            vote_usa_office_id = extract_vote_usa_office_id_with_suffix(raw_vote_usa_office_id)
            groom_results = groom_and_store_google_civic_candidates_json_2021(
                candidates_structured_json=office_candidates,
                google_civic_election_id=google_civic_election_id,
                state_code=state_code,
                contest_office_id=contest_office.id,
                contest_office_we_vote_id=contest_office.we_vote_id,
                contest_office_name=contest_office.office_name,
                election_year_integer=election_year_integer,
                update_or_create_rules={
                    'create_candidates': False,  # don't create new ones
                    'update_candidates': True,   # do full update on found ones
                },
                use_vote_usa=True,
                vote_usa_office_id=vote_usa_office_id,
            )
            if not groom_results['success']:
                success = False
                status += 'GROOM_CANDIDATES_FAILED_FOR_OFFICE: ' + str(vote_usa_office_id) + ' '
                status += groom_results['status']
    except Exception as e:
        success = False
        status += 'UPDATE_EXISTING_CANDIDATES_FROM_CANDIDATES_API_ERROR: ' + str(e) + ' '
        handle_exception(e, logger=logger, exception_message=status)
        results = {'success': success, 'status': status}
        return results

    return {
        'success': success,
        'status': status,
    }
