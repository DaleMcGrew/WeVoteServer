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
from django.db.models.functions import Length
from django.shortcuts import render
from django.utils.timezone import localtime, now

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

    ########## Basic functions for search feature

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

        # then use candidate_counts_qs to create a dict that maps state codes (case-insensitive) to their candidate counts
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
            #datetime_now = localtime(now()).date()  # We Vote uses Pacific Time for TIME_ZONE
            #current_year = datetime_now.year
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

    ########## End of basic functions for search feature

    # ################################################
    # Maintenance script section START
    # ################################################

    cleaning_candidate_list = []

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
        cleaning_candidate_query = CandidateCampaign.objects.all()
        cleaning_candidate_query = cleaning_candidate_query.filter(we_vote_id__in=candidates_to_update_we_vote_id_list)
        # For now, restrict to those who don't have candidate_ultimate_election_date. In the future, we could remove
        #  this to refresh the candidate_ultimate_election_date data for all candidates.
        cleaning_candidate_query = cleaning_candidate_query.filter(
            Q(candidate_ultimate_election_date=0) | Q(candidate_ultimate_election_date__isnull=True))
        if positive_value_exists(state_code):
            cleaning_candidate_query = cleaning_candidate_query.filter(state_code__iexact=state_code)
        candidate_ultimate_count = cleaning_candidate_query.count()
        if positive_value_exists(candidate_ultimate_count):
            populate_candidate_ultimate_election_date_status += \
                "SCRIPT: {entries_to_process:,} entries to process (populate_candidate_ultimate_election_date) " \
                "".format(entries_to_process=candidate_ultimate_count) + " "
        # Now process
        candidate_bulk_update_list = []
        cleaning_candidate_list = cleaning_candidate_query[:number_to_populate]
        candidates_updated = 0
        candidates_not_updated = 0
        elections_dict = {}
        from candidate.controllers import augment_candidate_with_ultimate_election_date
        for one_candidate in cleaning_candidate_list:
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
                "candidates_not_updated: " + str(candidates_not_updated) + " "
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
        cleaning_candidate_query = CandidateCampaign.objects.all()
        # Restrict to candidates who are in the future
        year_list = [2023, 2024]
        try:
            datetime_now = datetime.now()
            date_string = datetime_now.strftime('%Y%m%d')
            date_int = int(date_string)
        except Exception as e:
            date_int = 20240101
        cleaning_candidate_query = cleaning_candidate_query.filter(
            Q(candidate_ultimate_election_date__gt=date_int) |
            Q(candidate_year__in=year_list)
        )
        if positive_value_exists(state_code):
            cleaning_candidate_query = cleaning_candidate_query.filter(state_code__iexact=state_code)
        # Restrict to entries with BOTH contest_office_name and district_name empty
        #  OR race_office_level null or empty
        cleaning_candidate_query = cleaning_candidate_query.filter(
            ((Q(contest_office_name__isnull=True) | Q(contest_office_name='')) &
             (Q(district_name__isnull=True) | Q(district_name=''))) |
            (Q(race_office_level__isnull=True) | Q(race_office_level=''))
        )
        candidate_ultimate_count = cleaning_candidate_query.count()
        if positive_value_exists(candidate_ultimate_count):
            populate_contest_office_data_status += \
                "SCRIPT: {entries_to_process:,} entries to process (populate_contest_office_data). " \
                "".format(entries_to_process=candidate_ultimate_count) + " "

        # Filter candidates based on whether they have an email address
        if positive_value_exists(show_candidates_with_email):
            cleaning_candidate_query = cleaning_candidate_query.annotate(candidate_email_length=Length('candidate_email'))
            cleaning_candidate_query = cleaning_candidate_query.filter(
                Q(candidate_email_length__gt=2)
            )

        # Now process
        candidate_bulk_update_list = []
        cleaning_candidate_list = cleaning_candidate_query[:number_to_populate]
        candidates_updated = 0
        candidates_not_updated = 0
        candidate_to_office_link_list = []
        cleaning_candidate_we_vote_id_list = []
        contest_office_by_we_vote_id_dict = {}
        contest_office_list = []
        contest_office_we_vote_id_list = []
        office_by_candidate_we_vote_id_dict = {}
        from candidate.controllers import augment_candidate_with_contest_office_data
        for candidate in cleaning_candidate_list:
            # Collect candidate_we_vote_id_list, so we can retrieve linked offices first
            if candidate.we_vote_id not in cleaning_candidate_we_vote_id_list:
                cleaning_candidate_we_vote_id_list.append(candidate.we_vote_id)

        # Retrieve all CandidateToOfficeLink objects for these candidates
        if len(cleaning_candidate_we_vote_id_list) > 0:
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

        why_candidates_did_not_update = ""
        for candidate in cleaning_candidate_list:
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
        cleaning_candidate_list = list(seo_update_query[:number_to_update])
        politician_we_vote_id_list = []
        # Retrieve all relevant politicians in a single query
        for one_candidate in cleaning_candidate_list:
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
        cleaning_candidate_list = list(update_query[:number_to_update])
        politician_we_vote_id_list = []
        # Retrieve all relevant politicians in a single query
        for one_candidate in cleaning_candidate_list:
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