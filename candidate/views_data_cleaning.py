# candidate/views_data_cleaning.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-
import json
from datetime import datetime
from time import time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.messages import get_messages
from django.db.models import Q, Count
from django.shortcuts import render

import wevote_functions.admin
from admin_tools.views import redirect_to_sign_in_page
from ballot.models import BallotReturnedListManager
from config.base import get_environment_variable
from election.controllers import retrieve_election_id_list_by_year_list, retrieve_upcoming_election_id_list
from election.models import ElectionManager
from import_export_batches.models import BatchManager
from measure.models import ContestMeasure
from office.models import ContestOffice
from politician.models import PoliticianManager
from position.models import PositionEntered
from voter.models import voter_has_authority
from voter_guide.models import VoterGuide
from wevote_functions.functions import convert_to_int, positive_value_exists, STATE_CODE_MAP
from wevote_functions.functions_date import generate_localized_datetime_from_obj, \
    DATE_FORMAT_YMD, DATE_FORMAT_DAY_TWO_DIGIT
from wevote_settings.constants import ELECTION_YEARS_AVAILABLE
from .controllers import fetch_ballotpedia_urls_to_retrieve_for_links_count, \
    fetch_ballotpedia_urls_to_retrieve_for_photos_count
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
    page = convert_to_int(request.GET.get('page', 0))
    page = page if positive_value_exists(page) else 0  # Prevent negative pages
    # run_scripts = positive_value_exists(request.GET.get('run_scripts', False))
    run_scripts = True
    show_all_elections = positive_value_exists(request.GET.get('show_all_elections', False))
    show_election_statistics = positive_value_exists(request.GET.get('show_election_statistics', False))
    show_this_year_of_candidates = convert_to_int(request.GET.get('show_this_year_of_candidates', 0))
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
                status += f"Error parsing performance_process_dict: {e}"
        except json.JSONDecodeError:
            status += "Error decoding performance_process_dict: {error}.format(error=e)"

    performance_list = []
    performance_dict.update({
        'candidates_data_cleaning_view': performance_list,
    })

    state_code = request.GET.get('state_code', '')
    state_list = STATE_CODE_MAP
    state_list_modified = {}
    candidate_list_manager = CandidateListManager()

    # ######### Basic functions for search feature

    candidate_we_vote_id_list = []
    t0 = time()
    if positive_value_exists(google_civic_election_id):
        candidate_list_manager = CandidateListManager()
        results = candidate_list_manager.retrieve_candidate_we_vote_id_list_from_election_list(
            google_civic_election_id_list=[google_civic_election_id])
        candidate_we_vote_id_list = results['candidate_we_vote_id_list']
    t1 = time()
    performance_snapshot = {
        'name': 'CandidateWeVoteIdListBasic',
        'description': 'Retrieve candidate_we_vote_id_list (basic retrieval)',
        'time_difference': t1 - t0,
    }
    performance_list.append(performance_snapshot)

    t0 = time()
    google_civic_election_id_list_generated = False
    show_this_year_of_candidates_restriction = False
    if positive_value_exists(google_civic_election_id):
        google_civic_election_id_list = [convert_to_int(google_civic_election_id)]
        google_civic_election_id_list_generated = True
    elif positive_value_exists(show_this_year_of_candidates):
        google_civic_election_id_list = retrieve_election_id_list_by_year_list([show_this_year_of_candidates])
        show_this_year_of_candidates_restriction = True
    elif positive_value_exists(show_all_elections):
        google_civic_election_id_list = []
    else:
        # Limit to just upcoming elections
        google_civic_election_id_list_generated = True
        google_civic_election_id_list = retrieve_upcoming_election_id_list()
    t1 = time()
    performance_snapshot = {
        'name': 'GenerateGoogleCivicElectionIdList',
        'description': 'Determine which election_id_list to use (param vs year vs all vs upcoming)',
        'time_difference': t1 - t0,
    }
    performance_list.append(performance_snapshot)

    t0 = time()
    candidate_we_vote_id_list = []
    if show_this_year_of_candidates_restriction:
        results = candidate_list_manager.retrieve_candidate_we_vote_id_list_from_year_list(
            year_list=[show_this_year_of_candidates],
            limit_to_this_state_code=state_code)
        candidate_we_vote_id_list = results['candidate_we_vote_id_list']
    elif google_civic_election_id_list_generated:
        if positive_value_exists(state_code) and state_code.lower() == 'na':
            results = candidate_list_manager.retrieve_candidate_we_vote_id_list_from_election_list(
                google_civic_election_id_list=google_civic_election_id_list)
        else:
            results = candidate_list_manager.retrieve_candidate_we_vote_id_list_from_election_list(
                google_civic_election_id_list=google_civic_election_id_list,
                limit_to_this_state_code=state_code)
        candidate_we_vote_id_list = results['candidate_we_vote_id_list']
    t1 = time()
    performance_snapshot = {
        'name': 'CandidateWeVoteIdListUpdated',
        'description': 'Retrieve candidate_we_vote_id_list for either year/state or election/state',
        'time_difference': t1 - t0,
    }
    performance_list.append(performance_snapshot)

    t0 = time()
    if not positive_value_exists(candidate_we_vote_id_list):
        state_list_modified = {code: name for code, name in state_list.items()}
    else:
        # make 1 query to get all states' candidate counts in one swoop (using django.db.models Count)
        candidate_counts_qs = CandidateCampaign.objects.using('readonly').filter(
            we_vote_id__in=candidate_we_vote_id_list).values('state_code').annotate(candidate_count=Count('id'))

        # then use candidate_counts_qs to create dict that maps state codes (case-insensitive) to their candidate counts
        candidate_counts_by_state = {}
        for x in candidate_counts_qs:
            code = (x.get('state_code') or '').lower()
            candidate_counts_by_state[code] = candidate_counts_by_state.get(code, 0) + x['candidate_count']

        for one_state_code, one_state_name in state_list.items():
            count_result = candidate_list_manager.retrieve_candidate_count_for_election_and_state(
                google_civic_election_id_list, one_state_code, candidate_counts_by_state)
            state_name_modified = one_state_name
            if positive_value_exists(count_result['candidate_count']):
                state_name_modified += " - " + str(count_result['candidate_count'])
            elif str(one_state_code.lower()) == str(state_code.lower()):
                state_name_modified += " - 0"
            # At one point we did not include state in drop-down if there weren't any candidates in that state.
            #  Now we do.
            state_list_modified[one_state_code] = state_name_modified

    sorted_state_list = sorted(state_list_modified.items())
    # if positive_value_exists(google_civic_election_id):
    #     pass
    # else:
    #     sorted_state_list = sorted(state_list.items())
    t1 = time()
    performance_snapshot = {
        'name': 'ModifyStateNamesWithCandidateCounts',
        'description': 'Sort state list based on modified state names with appended candidate counts',
        'time_difference': t1 - t0,
    }
    performance_list.append(performance_snapshot)

    cleaning_candidate_list = []
    candidate_list_exists = False
    candidate_list_count = 0
    candidate_count_start = 0

    t0 = time()
    election_manager = ElectionManager()
    if positive_value_exists(show_all_elections):
        results = election_manager.retrieve_elections()
        election_list = results['election_list']
    else:
        results = election_manager.retrieve_upcoming_elections()
        election_list = results['election_list']
    t1 = time()
    performance_snapshot = {
        'name': 'ElectionList',
        'description': 'Retrieve election_list, either all or upcoming',
        'time_difference': t1 - t0,
    }
    performance_list.append(performance_snapshot)

    # Figure out the subset of candidate_we_vote_ids to look up
    t0 = time()
    filtered_candidate_we_vote_id_list = candidate_we_vote_id_list
    t1 = time()
    performance_snapshot = {
        'name': 'FilteredCandidateWeVoteIdList',
        'description': 'Retrieve filtered_candidate_we_vote_id_list (by election, year)',
        'time_difference': t1 - t0,
    }
    performance_list.append(performance_snapshot)

    # Now retrieve the candidate_list from the filtered_candidate_we_vote_id_list
    t0 = time()
    try:
        candidate_query = CandidateCampaign.objects.all()
        if positive_value_exists(google_civic_election_id_list_generated) \
                or positive_value_exists(show_this_year_of_candidates_restriction):
            # datetime_now = localtime(now()).date()  # We Vote uses Pacific Time for TIME_ZONE
            # current_year = datetime_now.year
            # # We could include all candidates in this year
            # candidate_query = candidate_query.filter(
            #     Q(we_vote_id__in=filtered_candidate_we_vote_id_list) |
            #     Q(candidate_year=current_year)
            # )
            # We currently only add the year when searching
            candidate_query = candidate_query.filter(we_vote_id__in=filtered_candidate_we_vote_id_list)
        if positive_value_exists(state_code):
            candidate_query = candidate_query.filter(state_code__iexact=state_code)

        candidate_list_count = candidate_query.count()

        candidate_list_exists = candidate_list_count > 0
        cleaning_candidate_list = list(candidate_query)
    except CandidateCampaign.DoesNotExist:
        pass

    t1 = time()
    performance_snapshot = {
        'name': 'RetrieveCandidateListFromFilteredCandidateWeVoteIdList',
        'description': 'Retrieve candidate_list from the filtered_candidate_we_vote_id_list',
        'time_difference': t1 - t0,
    }
    performance_list.append(performance_snapshot)

    t0 = time()
    if positive_value_exists(google_civic_election_id):
        results = candidate_list_manager.retrieve_candidate_we_vote_id_list_from_election_list(
            google_civic_election_id_list=[google_civic_election_id])
        candidate_we_vote_id_list = results['candidate_we_vote_id_list']
    else:
        # Only look at candidates for this year
        current_year = datetime.now().year
        results = candidate_list_manager.retrieve_candidate_we_vote_id_list_from_year_list(
            year_list=[current_year])
        candidate_we_vote_id_list = results['candidate_we_vote_id_list']
    t1 = time()
    performance_snapshot = {
        'name': 'RetrieveCandidateWeVoteIdListFromElectionOrYearList',
        'description': 'Get candidates in the elections or the year we care about',
        'time_difference': t1 - t0,
    }
    performance_list.append(performance_snapshot)

    # How many candidates with ballotpedia_candidate_url's don't have ballotpedia_photo_url?
    t0 = time()
    ballotpedia_urls_without_picture_urls = fetch_ballotpedia_urls_to_retrieve_for_photos_count(
        candidate_we_vote_id_list=candidate_we_vote_id_list,
        state_code=state_code,
        default_year_if_empty=False,
    )
    t1 = time()
    performance_snapshot = {
        'name': 'FetchBallotpediaUrlsToRetrieveForPhotosCount',
        'description': 'How many candidates with ballotpedia_candidate_url\'s don\'t have ballotpedia_photo_url?',
        'time_difference': t1 - t0,
    }
    performance_list.append(performance_snapshot)

    t0 = time()
    ballotpedia_urls_to_retrieve_for_links = fetch_ballotpedia_urls_to_retrieve_for_links_count(
        candidate_we_vote_id_list=candidate_we_vote_id_list,
        state_code=state_code,
        default_year_if_empty=False
    )
    t1 = time()
    performance_snapshot = {
        'name': 'FetchBallotpediaUrlsToRetrieveForLinksCount',
        'description': 'Determine how many ballotpedia_urls need to be retrieved for links',
        'time_difference': t1 - t0,
    }
    performance_list.append(performance_snapshot)

    # How many facebook_url's don't have facebook_profile_image_url_https
    # SELECT * FROM public.candidate_candidatecampaign where google_civic_election_id = '1000052' and facebook_url
    #     is not null and facebook_profile_image_url_https is null
    facebook_urls_retrieve_on = False
    facebook_urls_without_picture_urls = 0
    if facebook_urls_retrieve_on:
        t0 = time()
        try:
            count_queryset = CandidateCampaign.objects.using('readonly').all()
            count_queryset = count_queryset.filter(we_vote_id__in=candidate_we_vote_id_list)
            count_queryset = count_queryset.exclude(facebook_photo_url_is_broken=True)
            count_queryset = count_queryset.exclude(facebook_photo_url_is_placeholder=True)
            count_queryset = count_queryset.exclude(facebook_url_is_broken=True)
            if positive_value_exists(state_code):
                count_queryset = count_queryset.filter(state_code__iexact=state_code)

            # Exclude candidates without facebook_url
            count_queryset = count_queryset.exclude(
                Q(facebook_url__isnull=True) | Q(facebook_url__iexact=''))

            # Find candidates that don't have a photo (i.e. that are null or '')
            count_queryset = count_queryset. \
                filter(Q(facebook_profile_image_url_https__isnull=True) | Q(facebook_profile_image_url_https__exact=''))

            # candidates_to_review = list(count_queryset)
            facebook_urls_without_picture_urls = count_queryset.count()
        except Exception as e:
            logger.error("Find facebook URLs without facebook pictures in candidate: ", e)

        t1 = time()
        performance_snapshot = {
            'name': 'DetermineFacebookUrlWithoutPhoto',
            'description': 'Determine how many facebook_url do not have facebook_profile_image_url',
            'time_difference': t1 - t0,
        }
        performance_list.append(performance_snapshot)

    # How many candidates with wikipedia_candidate_url's don't have wikipedia_photo_url?
    t0 = time()
    wikipedia_urls_without_picture_urls = 0
    try:
        count_queryset = CandidateCampaign.objects.using('readonly').all()
        count_queryset = count_queryset.filter(we_vote_id__in=candidate_we_vote_id_list)
        count_queryset = count_queryset.exclude(wikipedia_photo_does_not_exist=True)
        if positive_value_exists(state_code):
            count_queryset = count_queryset.filter(state_code__iexact=state_code)

        # Exclude candidates without wikipedia_candidate_url
        count_queryset = count_queryset. \
            exclude(Q(wikipedia_url__isnull=True) | Q(wikipedia_url__exact=''))

        # Find candidates that don't have a photo (i.e. that are null or '')
        count_queryset = count_queryset.filter(
            Q(wikipedia_photo_url__isnull=True) | Q(wikipedia_photo_url__iexact=''))

        wikipedia_urls_without_picture_urls = count_queryset.count()

    except Exception as e:
        logger.error("ERROR Finding Wikipedia Photo URLs: ", e)

    t1 = time()
    performance_snapshot = {
        'name': 'DetermineWikipediaUrlWithoutPhoto',
        'description': 'Determine how many wikipedia_url do not have wikipedia_photo_url',
        'time_difference': t1 - t0,
    }
    performance_list.append(performance_snapshot)

    status_print_list = ""
    status_print_list += "{candidate_list_count:,} candidates found." \
                         "".format(candidate_list_count=candidate_list_count)

    messages.add_message(request, messages.INFO, status_print_list)

    messages_on_stage = get_messages(request)

    # Provide this election to the template, so we can show election statistics
    election = None
    if positive_value_exists(google_civic_election_id):
        t0 = time()
        results = election_manager.retrieve_election(google_civic_election_id)
        t1 = time()
        performance_snapshot = {
            'name': 'RetrieveElection',
            'description': 'Retrieve election from election_manager',
            'time_difference': t1 - t0,
        }
        performance_list.append(performance_snapshot)

        if results['election_found']:
            election = results['election']
            ballot_returned_list_manager = BallotReturnedListManager()
            batch_manager = BatchManager()
            # timezone = pytz.timezone("America/Los_Angeles")
            # datetime_now = timezone.localize(datetime.now())
            timezone, datetime_now = generate_localized_datetime_from_obj()
            if positive_value_exists(election.election_day_text):
                try:
                    date_of_election = \
                        timezone.localize(datetime.strptime(election.election_day_text, DATE_FORMAT_YMD))  # "%Y-%m-%d"
                    if date_of_election > datetime_now:
                        time_until_election = date_of_election - datetime_now
                        election.days_until_election = \
                            convert_to_int(DATE_FORMAT_DAY_TWO_DIGIT % time_until_election.days)  # "%d"
                except Exception as e:
                    pass

            # How many offices?
            t0 = time()
            office_list_query = ContestOffice.objects.using('readonly').all()
            office_list_query = office_list_query.filter(google_civic_election_id=election.google_civic_election_id)
            election.office_count = office_list_query.count()
            t1 = time()
            performance_snapshot = {
                'name': 'RetrieveOfficeCount',
                'description': 'Retrieve office_count from querying ContestOffice',
                'time_difference': t1 - t0,
            }
            performance_list.append(performance_snapshot)

            if positive_value_exists(show_election_statistics):
                t0 = time()
                office_list = list(office_list_query)

                election.ballot_returned_count = \
                    ballot_returned_list_manager.fetch_ballot_returned_list_count_for_election(
                        election.google_civic_election_id, election.state_code)
                election.ballot_location_display_option_on_count = \
                    ballot_returned_list_manager.fetch_ballot_location_display_option_on_count_for_election(
                        election.google_civic_election_id, election.state_code)
                if election.ballot_returned_count < 500:
                    batch_set_source = "IMPORT_BALLOTPEDIA_BALLOT_ITEMS"
                    results = batch_manager.retrieve_unprocessed_batch_set_info_by_election_and_set_source(
                        election.google_civic_election_id, batch_set_source)
                    if positive_value_exists(results['batches_not_processed']):
                        election.batches_not_processed = results['batches_not_processed']
                        election.batches_not_processed_batch_set_id = results['batch_set_id']
                t1 = time()
                performance_snapshot = {
                    'name': 'RetrieveBallotAndBatchInfo',
                    'description': 'Retrieve ballot_returned_count and batches_not_processed',
                    'time_difference': t1 - t0,
                }
                performance_list.append(performance_snapshot)

                # How many offices with zero candidates?
                offices_with_candidates_count = 0
                offices_without_candidates_count = 0
                t0 = time()
                for one_office in office_list:
                    candidate_list_query = CandidateCampaign.objects.using('readonly').all()
                    candidate_list_query = candidate_list_query.filter(contest_office_id=one_office.id)
                    candidate_count = candidate_list_query.count()
                    if positive_value_exists(candidate_count):
                        offices_with_candidates_count += 1
                    else:
                        offices_without_candidates_count += 1
                election.offices_with_candidates_count = offices_with_candidates_count
                election.offices_without_candidates_count = offices_without_candidates_count
                t1 = time()
                performance_snapshot = {
                    'name': 'CountOfficesWithAndWithoutCandidates',
                    'description': 'Retrieve offices_with_candidates_count and offices_without_candidates_count',
                    'time_difference': t1 - t0,
                }
                performance_list.append(performance_snapshot)

                # if positive_value_exists(google_civic_election_id_list_generated) \
                #         or positive_value_exists(show_marquee_or_battleground):
                #     candidate_query = candidate_query.filter(we_vote_id__in=filtered_candidate_we_vote_id_list)
                # How many candidates?
                t0 = time()
                candidate_list_query = CandidateCampaign.objects.using('readonly').all()
                candidate_list_query = candidate_list_query.filter(we_vote_id__in=candidate_we_vote_id_list)
                election.candidate_count = candidate_list_query.count()
                t1 = time()
                performance_snapshot = {
                    'name': 'CountCandidates',
                    'description': 'Retrieve candidate_count',
                    'time_difference': t1 - t0,
                }
                performance_list.append(performance_snapshot)

                # How many without photos?
                t0 = time()
                # candidate_list_query = CandidateCampaign.objects.using('readonly').all()
                # candidate_list_query = candidate_list_query.filter(we_vote_id__in=candidate_we_vote_id_list)
                candidate_list_query = candidate_list_query.filter(
                    Q(we_vote_hosted_profile_image_url_tiny__isnull=True) | Q(we_vote_hosted_profile_image_url_tiny='')
                )
                election.candidates_without_photo_count = candidate_list_query.count()
                if positive_value_exists(election.candidate_count):
                    election.candidates_without_photo_percentage = \
                        100 * (election.candidates_without_photo_count / election.candidate_count)
                t1 = time()
                performance_snapshot = {
                    'name': 'CountCandidatesWithoutPhoto',
                    'description': 'Retrieve candidates_without_photo and percentage from total candidate count',
                    'time_difference': t1 - t0,
                }
                performance_list.append(performance_snapshot)

                # How many measures?
                t0 = time()
                measure_list_query = ContestMeasure.objects.using('readonly').all()
                measure_list_query = measure_list_query.filter(
                    google_civic_election_id=election.google_civic_election_id)
                election.measure_count = measure_list_query.count()
                t1 = time()
                performance_snapshot = {
                    'name': 'CountMeasures',
                    'description': 'Retrieve measure_count',
                    'time_difference': t1 - t0,
                }
                performance_list.append(performance_snapshot)

                # Number of Voter Guides
                t0 = time()
                voter_guide_query = VoterGuide.objects.using('readonly').filter(
                    google_civic_election_id=election.google_civic_election_id)
                voter_guide_query = voter_guide_query.exclude(vote_smart_ratings_only=True)
                election.voter_guides_count = voter_guide_query.count()
                t1 = time()
                performance_snapshot = {
                    'name': 'CountVoterGuides',
                    'description': 'Retrieve voter_guides_count',
                    'time_difference': t1 - t0,
                }
                performance_list.append(performance_snapshot)

                # Number of Public Positions
                t0 = time()
                position_query = PositionEntered.objects.using('readonly').all()
                # Catch both candidates and measures (which have google_civic_election_id in the Positions table)
                position_query = position_query.filter(
                    Q(google_civic_election_id=election.google_civic_election_id) |
                    Q(candidate_campaign_we_vote_id__in=candidate_we_vote_id_list))
                # As of Aug 2018 we are no longer using PERCENT_RATING
                position_query = position_query.exclude(stance__iexact='PERCENT_RATING')
                election.public_positions_count = position_query.count()
                t1 = time()
                performance_snapshot = {
                    'name': 'CountPublicPositions',
                    'description': 'Retrieve public_positions_count',
                    'time_difference': t1 - t0,
                }
                performance_list.append(performance_snapshot)

    # Make sure we always include the current election in the election_list, even if it is older
    if positive_value_exists(google_civic_election_id):
        t0 = time()
        this_election_found = False
        for one_election in election_list:
            if convert_to_int(one_election.google_civic_election_id) == convert_to_int(google_civic_election_id):
                this_election_found = True
                break
        if not this_election_found:
            results = election_manager.retrieve_election(google_civic_election_id)
            if results['election_found']:
                one_election = results['election']
                election_list.append(one_election)
        t1 = time()
        performance_snapshot = {
            'name': 'EnsureCurrentElectionIncluded',
            'description': 'Loop through election_list until current election found; if not, append to election_list',
            'time_difference': t1 - t0,
        }
        performance_list.append(performance_snapshot)

    # ######### End of basic functions for search feature

    # ################################################
    # Maintenance script section START
    # ################################################

    # If we are looking at one specific election, find all the candidates under that election and make sure each
    #  candidate entry has a value for candidate_ultimate_election_date. Note this won't update candidates
    #  who have the general election as their ultimate_election_date, if they lost in the primary. That will require
    #  an update to this script.
    populate_candidates_ultimate_election_date_on = True
    t0 = time()
    number_to_populate = 1000  # Normally we can process 10000 at a time
    if populate_candidates_ultimate_election_date_on and run_scripts:
        google_civic_election_id_list = []
        if positive_value_exists(google_civic_election_id):
            google_civic_election_id_list = [google_civic_election_id]
        from candidate.controllers_data_cleaning import populate_candidates_ultimate_election_date
        results = populate_candidates_ultimate_election_date(
            google_civic_election_id_list=google_civic_election_id_list,
            number_to_populate=number_to_populate,
            state_code=state_code,
        )
        if positive_value_exists(results['status']):
            messages.add_message(request, messages.INFO, results['status'])
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
    populate_contest_office_data_on = True
    number_to_populate = 1000  # Normally we can process 1000 at a time
    if populate_contest_office_data_on and run_scripts:
        google_civic_election_id_list = []
        if positive_value_exists(google_civic_election_id):
            google_civic_election_id_list = [google_civic_election_id]
        from candidate.controllers_data_cleaning import populate_contest_office_data
        results = populate_contest_office_data(
            google_civic_election_id_list=google_civic_election_id_list,
            number_to_populate=number_to_populate,
            show_candidates_with_email=show_candidates_with_email,
            state_code=state_code,
        )
        if positive_value_exists(results['status']):
            messages.add_message(request, messages.INFO, results['status'])

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
    seo_friendly_path_updates_on = True
    if seo_friendly_path_updates_on and run_scripts:
        google_civic_election_id_list = None
        if positive_value_exists(google_civic_election_id):
            google_civic_election_id_list = [google_civic_election_id]
        from candidate.controllers_data_cleaning import seo_friendly_path_updates
        results = seo_friendly_path_updates(
            google_civic_election_id_list=google_civic_election_id_list,
            number_to_update=number_to_update,
            state_code=state_code,
        )
        if positive_value_exists(results['status']):
            messages.add_message(request, messages.INFO, results['status'])

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
    campaignx_we_vote_id_updates_on = True
    if campaignx_we_vote_id_updates_on and run_scripts:
        google_civic_election_id_list = None
        if positive_value_exists(google_civic_election_id):
            google_civic_election_id_list = [google_civic_election_id]
        from candidate.controllers_data_cleaning import campaignx_we_vote_id_updates
        results = campaignx_we_vote_id_updates(
            google_civic_election_id_list=google_civic_election_id_list,
            number_to_update=number_to_update,
            state_code=state_code,
        )
        if positive_value_exists(results['status']):
            messages.add_message(request, messages.INFO, results['status'])

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
        'ballotpedia_urls_to_retrieve_for_links':   ballotpedia_urls_to_retrieve_for_links,
        'ballotpedia_urls_without_picture_urls':    ballotpedia_urls_without_picture_urls,
        'candidate_count_start':                    candidate_count_start,
        'candidate_list_exists':                    candidate_list_exists,
        'cleaning_candidate_list':                  cleaning_candidate_list,
        'current_page_number':                      page,
        'election':                                 election,
        'election_list':                            election_list,
        'election_years_available':                 ELECTION_YEARS_AVAILABLE,
        'google_civic_election_id':                 google_civic_election_id,
        'messages_on_stage':                        messages_on_stage,
        'performance_dict':                         performance_dict,
        'show_all_elections':                       show_all_elections,
        'show_candidates_with_email':               show_candidates_with_email,
        'show_election_statistics':                 show_election_statistics,
        'show_this_year_of_candidates':             show_this_year_of_candidates,
        'state_code':                               state_code,
        'state_list':                               sorted_state_list,
        'wikipedia_urls_without_picture_urls':      wikipedia_urls_without_picture_urls,
    }
    return render(request, 'candidate/candidate_data_cleaning.html', template_values)