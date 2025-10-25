# politician/controllers_managed_politician.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

import base64
import copy
from io import BytesIO
from PIL import Image, ImageOps
import re
from datetime import datetime
from django.db.models import Q
from django.http import HttpResponse
from exception.models import handle_exception
import json

from campaign.models import CampaignXManager, FINAL_ELECTION_DATE_COOL_DOWN, CampaignXOwner
from candidate.controllers import add_name_to_next_spot, copy_field_value_from_object1_to_object2, \
    generate_candidate_dict_list_from_candidate_object_list, move_candidates_to_another_politician
from candidate.models import CandidateListManager, CandidateManager, PROFILE_IMAGE_TYPE_FACEBOOK, \
    PROFILE_IMAGE_TYPE_UNKNOWN, \
    PROFILE_IMAGE_TYPE_UPLOADED, PROFILE_IMAGE_TYPE_TWITTER, PROFILE_IMAGE_TYPE_VOTE_USA
from email_outbound.models import EmailAddress
from image.controllers import cache_image_object_to_aws, create_resized_images
from office.models import ContestOfficeManager, ContestOfficeListManager
from office_held.controllers import generate_office_held_dict_list_from_office_held_we_vote_id_list
from organization.models import Organization, OrganizationManager
from politician.controllers_generate_seo_friendly_path import generate_campaign_title_from_politician
from politician.models import Politician, PoliticianManager, PoliticianSEOFriendlyPath, \
    POLITICIAN_UNIQUE_ATTRIBUTES_TO_BE_CLEARED, POLITICIAN_UNIQUE_IDENTIFIERS, UNKNOWN
from position.controllers import move_positions_to_another_politician
import pytz
from representative.controllers import generate_representative_dict_list_from_representative_object_list, \
    move_representatives_to_another_politician
from representative.models import RepresentativeManager
from voter.models import Voter, VoterManager
from config.base import get_environment_variable
import wevote_functions.admin
from wevote_functions.functions import candidate_party_display, convert_to_int, \
    convert_to_political_party_constant, extract_instagram_handle_from_text_string, \
    generate_random_string, positive_value_exists, \
    process_request_from_master, remove_middle_initial_from_name
from wevote_functions.functions_date import convert_we_vote_date_string_to_date_as_integer, generate_date_as_integer, \
    generate_localized_datetime_from_obj, DATE_FORMAT_YMD_HMS

logger = wevote_functions.admin.get_logger(__name__)


def politician_managed_retrieve_for_api(  # politicianManagedRetrieve
        request=None,
        voter_device_id='',
):
    status = ''
    success = True

    results = {}
    results.update({
        # 'candidate_list':                   politician_candidate_dict_list,
        'status':                           status,
        'success':                          success,
    })
    return results


def politician_managed_save_for_api(  # politicianManagedSave
        request=None,
        voter_device_id='',
):
    status = ''
    success = True

    return politician_managed_retrieve_for_api(request, voter_device_id)


def politicians_managed_retrieve_for_api(  # politiciansManagedRetrieve
        request=None,
        voter_device_id='',
):
    politician_we_vote_id_list = []
    politicians_managed_list = []
    status = ''
    success = True
    voter_is_signed_in = False
    voter_we_vote_id = ''

    error_results = {
        'politicians_managed_list': politicians_managed_list,
        'status': status,
        'success': success,
    }

    voter_manager = VoterManager()
    voter_results = voter_manager.retrieve_voter_from_voter_device_id(voter_device_id, read_only=True)
    if voter_results['voter_found']:
        voter = voter_results['voter']
        voter_is_signed_in = voter.is_signed_in()
        voter_we_vote_id = voter.we_vote_id

    if not voter_is_signed_in:
        error_results['status'] += "NOT_SIGNED_IN "
        error_results['success'] = True
        return error_results

    # Find all verified emails associated with the voter

    # Search to find all politicians this voter can manage
    campaignx_manager = CampaignXManager()
    voter_owned_campaignx_we_vote_ids = campaignx_manager.retrieve_voter_owned_campaignx_we_vote_ids(
        voter_we_vote_id=voter_we_vote_id)

    if len(voter_owned_campaignx_we_vote_ids) > 0:
        politician_manager = PoliticianManager()
        results = politician_manager.retrieve_politician_list(
            campaignx_we_vote_id_list=voter_owned_campaignx_we_vote_ids)
        if not results['success']:
            status += "FAILED_RETRIEVING_POLITICIANS_FOR_VOTER_OWNED_CAMPAIGNS: "
            status += results['status'] + ' '
            success = False
        politician_list = results['politician_list']

        for politician in politician_list:
            politicians_managed_list.append(
                {
                    'politician_we_vote_id': politician.we_vote_id,
                    'politician_name': politician.politician_name,
                    'we_vote_hosted_profile_image_url_large': politician.we_vote_hosted_profile_image_url_large,
                    'we_vote_hosted_profile_image_url_medium': politician.we_vote_hosted_profile_image_url_medium,
                    'we_vote_hosted_profile_image_url_tiny': politician.we_vote_hosted_profile_image_url_tiny,
                }
            )

    results = {}
    results.update({
        'politicians_managed_list':         politicians_managed_list,
        'status':                           status,
        'success':                          success,
    })
    return results
