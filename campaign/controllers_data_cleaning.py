# campaign/controllers_data_cleaning.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

from django.db.models import Q
from django.utils.timezone import localtime, now

from config.base import get_environment_variable
from organization.models import Organization
from politician.models import Politician
import wevote_functions.admin
from wevote_functions.functions import positive_value_exists
from .models import CampaignX

POLITICIANS_SYNC_URL = get_environment_variable("POLITICIANS_SYNC_URL")  # politiciansSyncOut
TWITTER_API_ON = positive_value_exists(get_environment_variable("TWITTER_API_ON", no_exception=True))
WE_VOTE_SERVER_ROOT_URL = get_environment_variable("WE_VOTE_SERVER_ROOT_URL")
WEB_APP_ROOT_URL = get_environment_variable("WEB_APP_ROOT_URL")

logger = wevote_functions.admin.get_logger(__name__)


def batch_process_maintenance_scripts_campaignx():
    status = ' :||: '
    success = True

    # ##################
    # Check all entries that have Politician.linked_campaignx_we_vote_id and
    # make sure we have that corresponding CampaignX entry. If not, delete the Politician.linked_campaignx_we_vote_id
    # value.
    results = clean_campaigns_with_dead_politician_we_vote_id(
        number_to_update=1000,
    )
    if positive_value_exists(results['status']):
        status += results['status'] + ":||: "

    # ##################
    # If a CampaignX entry has a linked_politician_we_vote_id, but no organization_we_vote_id,
    #  then add organization_we_vote_id to the entry
    results = add_organization_we_vote_id_from_politician_to_campaignx(
        number_to_update=1000,
    )
    if positive_value_exists(results['status']):
        status += results['status'] + ":||: "

    results = {
        'status': status,
        'success': success,
    }
    return results


def clean_campaigns_with_dead_politician_we_vote_id(
        number_to_update=1000,
        state_code=None,
):
    """
    Check all entries that have Politician.linked_campaignx_we_vote_id and
    make sure we have that corresponding CampaignX entry. If not, delete the Politician.linked_campaignx_we_vote_id
    value.
    """
    campaignx_list_to_update = []
    records_cleared = 0
    status = ''
    success = True
    total_to_update_after = 0
    update_list = []
    updates_made = 0
    updates_needed = False
    politician_we_vote_id_list = []
    politician_we_vote_ids_not_found_list = []

    try:
        queryset = CampaignX.objects.using('readonly').all()
        queryset = queryset.exclude(
            Q(linked_politician_we_vote_id__isnull=True) | Q(linked_politician_we_vote_id=''))
        queryset = queryset.exclude(linked_politician_we_vote_id_verified=True)
        if positive_value_exists(state_code):
            queryset = queryset.filter(state_code__iexact=state_code)
        total_to_update = queryset.count()
        total_to_update_after = total_to_update - number_to_update if total_to_update > number_to_update else 0
        campaignx_list_to_update = list(queryset[:number_to_update])
        for one_campaignx in campaignx_list_to_update:
            if positive_value_exists(one_campaignx.linked_politician_we_vote_id):
                if one_campaignx.linked_politician_we_vote_id not in politician_we_vote_id_list:
                    politician_we_vote_id_list.append(one_campaignx.linked_politician_we_vote_id)
    except Exception as e:
        status += "CAMPAIGNX_CLEAN_QUERY_FAILED: " + str(e) + " "

    if campaignx_list_to_update and len(campaignx_list_to_update) == 0:
        status += "clean_campaigns_with_dead_politician_we_vote_id_NO_CAMPAIGNX_RECORDS_FOUND_TO_UPDATE "
        return {
           'status': status,
           'success': success,
        }

    try:
        if politician_we_vote_id_list and len(politician_we_vote_id_list) > 0:
            queryset = Politician.objects.using('readonly').all()
            queryset = queryset.filter(we_vote_id__in=politician_we_vote_id_list)
            queryset = queryset.values_list('we_vote_id', flat=True).distinct()
            politician_we_vote_ids_found_list = list(queryset)
            politician_we_vote_ids_not_found_list = politician_we_vote_id_list.copy()
            for one_politician_we_vote_id in politician_we_vote_ids_found_list:
                politician_we_vote_ids_not_found_list.remove(one_politician_we_vote_id)

        for one_campaignx in campaignx_list_to_update:
            one_campaignx.linked_politician_we_vote_id_verified = True
            if one_campaignx.linked_politician_we_vote_id in politician_we_vote_ids_not_found_list:
                one_campaignx.date_last_updated_from_politician = localtime(now()).date()
                one_campaignx.linked_politician_we_vote_id = None
                one_campaignx.seo_friendly_path = None
            update_list.append(one_campaignx)
            updates_needed = True
            records_cleared += 1
    except Exception as e:
        status += "ERROR_POLITICIAN_QUERY_clean_campaigns_with_dead_politician_we_vote_id query: {e} " \
                  "".format(e=e)
        success = False

    if updates_needed:
        try:
            CampaignX.objects.bulk_update(
                update_list,
                ['date_last_updated_from_politician',
                 'linked_politician_we_vote_id',
                 'linked_politician_we_vote_id_verified',
                 'seo_friendly_path'])
            status += \
                "clean_campaigns_with_dead_politician_we_vote_id: " \
                "{updates_made:,} campaignx entries cleaned from missing politicians. " \
                "{records_cleared:,} records had Politician.linked_campaignx_we_vote_id cleared out. " \
                "{total_to_update_after:,} remaining. " \
                "".format(
                    records_cleared=records_cleared,
                    total_to_update_after=total_to_update_after,
                    updates_made=updates_made)
        except Exception as e:
            status += "ERROR_CAMPAIGNX_BULK_UPDATE_clean_campaigns_with_dead_politician_we_vote_id: {e} " \
                      "politician_we_vote_ids_not_found_list: {politician_we_vote_ids_not_found_list}" \
                      "".format(
                          e=e,
                          politician_we_vote_ids_not_found_list=politician_we_vote_ids_not_found_list)
            success = False
    else:
        status += \
            "clean_campaigns_with_dead_politician_we_vote_id: " \
            "{total_to_update_after:,} remaining. " \
            "".format(
                total_to_update_after=total_to_update_after)

    results = {
        'status': status,
        'success': success,
    }
    return results


def add_organization_we_vote_id_from_politician_to_campaignx(
        number_to_update=1000,
        state_code=None,
):
    """
    If a CampaignX entry has a linked_politician_we_vote_id, but no organization_we_vote_id,
    then add organization_we_vote_id to the entry
    """
    campaignx_list_to_update = []
    organization_dict_by_politician_we_vote_id = {}
    organization_list = []
    politician_we_vote_id_list = []
    politician_we_vote_ids_not_found_list = []
    status = ''
    success = True
    total_to_update_after = 0
    update_list = []
    updates_made = 0
    updates_needed = False

    try:
        queryset = CampaignX.objects.all()  # Cannot be 'readonly' because we need to update entries below.
        if positive_value_exists(state_code):
            queryset = queryset.filter(state_code__iexact=state_code)
        queryset = queryset.exclude(
            Q(linked_politician_we_vote_id__isnull=True) | Q(linked_politician_we_vote_id=''))
        # NOTE: IF instead of checking for existing organization_we_vote_id,
        #  we could use this script with an analysis boolean to verify we have stored correct organization_we_vote_id
        queryset = queryset.filter(
            Q(organization_we_vote_id__isnull=True) | Q(organization_we_vote_id=''))
        total_to_update = queryset.count()
        total_to_update_after = total_to_update - number_to_update if total_to_update > number_to_update else 0
        campaignx_list_to_update = list(queryset[:number_to_update])
        for one_campaignx in campaignx_list_to_update:
            if positive_value_exists(one_campaignx.linked_politician_we_vote_id):
                if one_campaignx.linked_politician_we_vote_id not in politician_we_vote_id_list:
                    politician_we_vote_id_list.append(one_campaignx.linked_politician_we_vote_id)
    except Exception as e:
        status += "CAMPAIGNX_ORG_LINKS_QUERY_FAILED: " + str(e) + " "

    if campaignx_list_to_update and len(campaignx_list_to_update) == 0:
        status += "add_organization_we_vote_id_from_politician_to_campaignx_NO_CAMPAIGNX_RECORDS_FOUND_TO_UPDATE "
        return {
           'status': status,
           'success': success,
        }

    try:
        # Organization table has the master link to politician_we_vote_id, which is why we use that table
        if politician_we_vote_id_list and len(politician_we_vote_id_list) > 0:
            queryset = Organization.objects.using('readonly').all()
            queryset = queryset.filter(politician_we_vote_id__in=politician_we_vote_id_list)
            organization_list = list(queryset)
        for one_organization in organization_list:
            organization_dict_by_politician_we_vote_id[one_organization.politician_we_vote_id] = one_organization

        if organization_list and len(organization_list) == 0:
            status += \
                "No organizations found by politician_we_vote_id from the CampaignXs reviewed. " \
                "politician_we_vote_id_list: {politician_we_vote_id_list}" \
                "".format(politician_we_vote_id_list=politician_we_vote_id_list)

        for one_campaignx in campaignx_list_to_update:
            if one_campaignx.linked_politician_we_vote_id in organization_dict_by_politician_we_vote_id:
                organization = organization_dict_by_politician_we_vote_id[one_campaignx.linked_politician_we_vote_id]
                one_campaignx.organization_we_vote_id = organization.we_vote_id
                update_list.append(one_campaignx)
                updates_needed = True
                updates_made += 1
            else:
                politician_we_vote_ids_not_found_list.append(one_campaignx.linked_politician_we_vote_id)
    except Exception as e:
        status += "ERROR_ORGANIZATION_QUERY_add_organization_we_vote_id_from_politician_to_campaignx query: {e} " \
                  "".format(e=e)
        success = False

    if updates_needed:
        try:
            CampaignX.objects.bulk_update(update_list, ['organization_we_vote_id'])
            status += \
                "add_organization_we_vote_id_from_politician_to_campaignx: " \
                "{updates_made:,} campaignx entries updated with organization_we_vote_id " \
                "out of {updates_planned}. " \
                "{total_to_update_after:,} remaining. " \
                "politician_we_vote_ids_not_found_list: {politician_we_vote_ids_not_found_list} " \
                "".format(
                    politician_we_vote_ids_not_found_list=politician_we_vote_ids_not_found_list,
                    total_to_update_after=total_to_update_after,
                    updates_made=updates_made,
                    updates_planned=len(campaignx_list_to_update),
                )
        except Exception as e:
            status += "ERROR_CAMPAIGNX_BULK_UPDATE_add_organization_we_vote_id_from_politician_to_campaignx: {e} " \
                      "politician_we_vote_ids_not_found_list: {politician_we_vote_ids_not_found_list}" \
                      "".format(
                          e=e,
                          politician_we_vote_ids_not_found_list=politician_we_vote_ids_not_found_list)
            success = False
    else:
        status += \
            "add_organization_we_vote_id_from_politician_to_campaignx: " \
            "{total_to_update_after:,} remaining. " \
            "".format(
                total_to_update_after=total_to_update_after)

    results = {
        'status': status,
        'success': success,
    }
    return results
