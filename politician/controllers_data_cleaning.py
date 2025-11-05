# politician/controllers_data_cleaning.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

from django.db.models import Q

from config.base import get_environment_variable
import wevote_functions.admin
from wevote_functions.functions import positive_value_exists
from wevote_functions.functions_date import generate_localized_datetime_from_obj
from .controllers import add_alternate_names_to_next_spot, generate_campaignx_for_politician
from .models import Politician, PoliticianManager
from .controllers_generate_color import generate_background

POLITICIANS_SYNC_URL = get_environment_variable("POLITICIANS_SYNC_URL")  # politiciansSyncOut
TWITTER_API_ON = positive_value_exists(get_environment_variable("TWITTER_API_ON", no_exception=True))
WE_VOTE_SERVER_ROOT_URL = get_environment_variable("WE_VOTE_SERVER_ROOT_URL")
WEB_APP_ROOT_URL = get_environment_variable("WEB_APP_ROOT_URL")

logger = wevote_functions.admin.get_logger(__name__)


def batch_process_maintenance_scripts_politician():
    status = ''
    success = True

    # ##################
    # Make sure we have a version of the politician's name without a middle initial (for matching endorsements)
    results = generate_google_civic_name_alternates(
        number_to_generate=1000,
    )
    if positive_value_exists(results['status']):
        status += results['status'] + ":: "

    # ##################
    # Generate a unique background color for each politician so their photo has a rectangle to sit in
    results = generate_politician_photo_backgrounds(
        number_to_generate=10,
    )
    if positive_value_exists(results['status']):
        status += results['status'] + ":: "

    # ##################
    # Create seo_friendly_path for all politicians who currently don't have one
    results = generate_politician_seo_friendly_paths(
        number_to_create=1000,
    )
    if positive_value_exists(results['status']):
        status += results['status'] + ":: "

    # ##################
    # Check all entries that have Politician.linked_campaignx_we_vote_id and
    # make sure we have that corresponding CampaignX entry. If not, delete the Politician.linked_campaignx_we_vote_id
    # value.
    results = delete_linked_campaignx_we_vote_id_if_campaignx_not_found(
        number_to_verify=1000,
    )
    if positive_value_exists(results['status']):
        status += results['status'] + ":: "

    # ##################
    # Create default CampaignX for all politicians who currently don't have one
    results = generate_campaignx_for_every_politician(
        number_to_create=1000,
    )
    if positive_value_exists(results['status']):
        status += results['status'] + ":: "

    # ##################
    # Find all politicians with linked_campaignx_we_vote_id and make sure Campaignx
    # entry includes linked_politician_we_vote_id. If it doesn't, or linked_politician_we_vote_id in CampaignX entry
    # doesn't match the Politician.we_vote_id, update it.
    results = update_campaignx_with_linked_politician_we_vote_id(
        number_to_update=1000,
    )
    if positive_value_exists(results['status']):
        status += results['status'] + ":: "

    results = {
        'status': status,
        'success': success,
    }
    return results


def delete_linked_campaignx_we_vote_id_if_campaignx_not_found(
        number_to_verify=1000,
        state_code=None,
):
    """
    Check all entries that have Politician.linked_campaignx_we_vote_id and
    make sure we have that corresponding CampaignX entry. If not, delete the Politician.linked_campaignx_we_vote_id
    value.
    """
    records_cleared = 0
    status = ''
    success = True
    total_to_convert_after = 0
    update_list = []
    updates_made = 0
    updates_needed = False

    try:
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
        linked_campaignx_we_vote_id_list = list(linked_campaignx_we_vote_id_list[:number_to_verify])

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

        total_to_convert = politician_query.count()
        total_to_convert_after = total_to_convert - number_to_verify if total_to_convert > number_to_verify else 0
        datetime_now = generate_localized_datetime_from_obj()[1]
        if existing_campaignx_we_vote_ids and len(existing_campaignx_we_vote_ids) > 0:
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
        if non_existent_campaignx_we_vote_ids and len(non_existent_campaignx_we_vote_ids) > 0:
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
    except Exception as e:
        status += "ERROR_POLITICIAN_QUERY_delete_linked_campaignx_we_vote_id_if_campaignx_not_found query: {e} " \
                  "".format(e=e)
        success = False

    if updates_needed:
        try:
            Politician.objects.bulk_update(
                update_list, [
                    'linked_campaignx_we_vote_id',
                    'linked_campaignx_we_vote_id_date_last_updated',
                    'linked_campaignx_we_vote_id_verified'])
            status += \
                "delete_linked_campaignx_we_vote_id_if_campaignx_not_found " \
                "{updates_made:,} politicians scanned for a current linked_campaignx_we_vote_id. " \
                "{records_cleared:,} records had Politician.linked_campaignx_we_vote_id cleared out. " \
                "{total_to_convert_after:,} remaining. " \
                "".format(
                    records_cleared=records_cleared,
                    total_to_convert_after=total_to_convert_after,
                    updates_made=updates_made)
        except Exception as e:
            status += "ERROR_POLITICIAN_BULK_UPDATE_delete_linked_campaignx_we_vote_id_if_campaignx_not_found: {e} " \
                "".format(e=e)
            success = False
    else:
        status += \
            "delete_linked_campaignx_we_vote_id_if_campaignx_not_found " \
            "{total_to_convert_after:,} remaining. " \
            "".format(
                total_to_convert_after=total_to_convert_after)

    results = {
        'status': status,
        'success': success,
    }
    return results


def generate_campaignx_for_every_politician(
        number_to_create=1000,
        state_code=None,
):
    status = ''
    success = True
    total_to_convert_after = 0
    update_list = []
    updates_made = 0
    updates_needed = False

    try:
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
    except Exception as e:
        status += "ERROR_POLITICIAN_QUERY_generate_campaignx_for_every_politician query: {e} ".format(e=e)
        success = False

    if updates_needed:
        try:
            Politician.objects.bulk_update(
                update_list, ['linked_campaignx_we_vote_id', 'linked_campaignx_we_vote_id_date_last_updated'])
            status += \
                "generate_campaignx_for_every_politician Generated CampaignX for {updates_made:,} politicians. " \
                "{total_to_convert_after:,} remaining. " \
                "".format(
                    total_to_convert_after=total_to_convert_after,
                    updates_made=updates_made)
        except Exception as e:
            status += "ERROR_POLITICIAN_BULK_UPDATE_generate_campaignx_for_every_politician: {e} ".format(e=e)
            success = False
    else:
        status += "NO_UPDATES_NEEDED_generate_campaignx_for_every_politician "

    results = {
        'status': status,
        'success': success,
    }
    return results


def generate_politician_photo_backgrounds(
        number_to_generate=10,
        state_code=None,
):
    politicians_not_updated = 0
    status = ''
    success = True
    total_to_convert_after = 0
    update_list = []
    updates_made = 0
    updates_needed = False

    try:
        politician_query = Politician.objects.all()
        politician_query = politician_query.exclude(
            Q(we_vote_hosted_profile_image_url_large__isnull=True) |
            Q(we_vote_hosted_profile_image_url_large="")
        )
        politician_query = politician_query.exclude(profile_image_background_color_needed=False)
        if positive_value_exists(state_code):
            politician_query = politician_query.filter(state_code__iexact=state_code)
        total_to_convert = politician_query.count()
        total_to_convert_after = total_to_convert - number_to_generate if total_to_convert > number_to_generate else 0
        politician_list_to_convert = list(politician_query[:number_to_generate])

        for politician in politician_list_to_convert:
            politician.profile_image_background_color_needed = False
            if positive_value_exists(politician.we_vote_hosted_profile_image_url_large):
                politician.profile_image_background_color = generate_background(politician)
                updates_made += 1
                update_list.append(politician)
                updates_needed = True
            else:
                politicians_not_updated += 1
        if total_to_convert == 0:
            status += "All politicians have been updated with a background color for profile photo."
    except Exception as e:
        status += "ERROR_POLITICIAN_QUERY-generate_politician_photo_backgrounds: {e} ".format(e=e)
        success = False

    if updates_needed:
        try:
            Politician.objects.bulk_update(update_list, ['profile_image_background_color',
                                                         'profile_image_background_color_needed'])
            status += \
                "generate_politician_photo_backgrounds {updates_made:,} updates made. " \
                "Politicians without picture URL:  {politicians_not_updated:,}. " \
                "{total_to_convert_after:,} remaining. " \
                "".format(
                    politicians_not_updated=politicians_not_updated,
                    total_to_convert_after=total_to_convert_after,
                    updates_made=updates_made)
        except Exception as e:
            status += "ERROR_POLITICIAN_BULK_UPDATE-generate_politician_photo_backgrounds: {e} ".format(e=e)
            success = False
    else:
        status += "NO_UPDATES_NEEDED_generate_politician_photo_backgrounds "
    results = {
        'status': status,
        'success': success,
    }
    return results


def generate_politician_seo_friendly_paths(
        number_to_create=1000,
        state_code=None,
):
    status = ''
    success = True
    total_to_convert_after = 0
    update_list = []
    updates_made = 0
    updates_needed = False

    try:
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
    except Exception as e:
        status += "ERROR_POLITICIAN_QUERY-generate_politician_seo_friendly_paths query: {e} ".format(e=e)
        success = False

    if updates_needed:
        try:
            Politician.objects.bulk_update(update_list,
                                           ['seo_friendly_path', 'seo_friendly_path_date_last_updated'])
            status += \
                "generate_politician_seo_friendly_paths " \
                "{updates_made:,} politicians updated with new seo_friendly_path. " \
                "{total_to_convert_after:,} remaining. " \
                "".format(
                    total_to_convert_after=total_to_convert_after,
                    updates_made=updates_made)
        except Exception as e:
            status += "ERROR_POLITICIAN_BULK_UPDATE-generate_politician_seo_friendly_paths: {e} ".format(e=e)
            success = False
    else:
        status += "NO_UPDATES_NEEDED_generate_politician_seo_friendly_paths "

    results = {
        'status': status,
        'success': success,
    }
    return results


def generate_google_civic_name_alternates(
        number_to_generate=1000,
        state_code=None,
):
    """
    Make sure we have a version of the politician's name without a middle initial (for matching endorsements)
    """
    status = ''
    success = True
    total_to_convert_after = 0
    update_list = []
    updates_failed = 0
    updates_made = 0
    updates_needed = False

    try:
        politician_query = Politician.objects.all()
        politician_query = politician_query.filter(google_civic_name_alternates_generated=False)
        if positive_value_exists(state_code):
            politician_query = politician_query.filter(state_code__iexact=state_code)
        total_to_convert = politician_query.count()
        total_to_convert_after = total_to_convert - number_to_generate if total_to_convert > number_to_generate else 0
        politician_list_to_convert = list(politician_query[:number_to_generate])
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
            else:
                updates_failed += 1
    except Exception as e:
        status += "ERROR_POLITICIAN_QUERY generate_google_civic_name_alternates query: {e} ".format(e=e)
        success = False

    if updates_needed:
        try:
            Politician.objects.bulk_update(update_list, [
                'google_civic_name_alternates_generated',
                'google_civic_candidate_name',
                'google_civic_candidate_name2',
                'google_civic_candidate_name3',
            ])
            status += \
                "{updates_made:,} google_civic_name_alternates_generated. " \
                "{total_to_convert_after:,} remaining. " \
                "".format(
                    total_to_convert_after=total_to_convert_after,
                    updates_made=updates_made)
        except Exception as e:
            status += "ERROR_POLITICIAN_BULK_UPDATE generate_google_civic_name_alternates: {e} ".format(e=e)
            success = False
    else:
        status += "NO_UPDATES_NEEDED_generate_google_civic_name_alternates "
    results = {
        'status': status,
        'success': success,
    }
    return results


def update_campaignx_with_linked_politician_we_vote_id(
        number_to_update=1000,
        state_code=None,
):
    """
    Find all politicians with linked_campaignx_we_vote_id and make sure Campaignx
    entry includes linked_politician_we_vote_id. If it doesn't, or linked_politician_we_vote_id in CampaignX entry
    doesn't match the Politician.we_vote_id, update it.
    """
    politician_update_list = []
    status = ''
    success = True
    total_to_convert_after = 0
    update_list = []
    updates_made = 0
    updates_needed = False
    from campaign.models import CampaignX

    try:
        politician_query = Politician.objects.all()
        politician_query = politician_query.exclude(
            Q(linked_campaignx_we_vote_id__isnull=True) |
            Q(linked_campaignx_we_vote_id="")
        )
        politician_query = politician_query.filter(linked_campaignx_we_vote_id_verified_in_campaignx=False)
        if positive_value_exists(state_code):
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

                        one_politician.linked_campaignx_we_vote_id_verified_in_campaignx = True
                        politician_update_list.append(one_politician)

                        updates_needed = True

            if positive_value_exists(one_campaignx.linked_politician_we_vote_id):
                campaignx_with_linked_politician_we_vote_id_count += 1
    except Exception as e:
        status += "ERROR_POLITICIAN_QUERY_update_campaignx_with_linked_politician_we_vote_id: {e} ".format(e=e)
        success = False

    if updates_needed:
        try:
            CampaignX.objects.bulk_update(
                update_list, ['linked_politician_we_vote_id'])
            status += \
                "update_campaignx_with_linked_politician_we_vote_id " \
                "{updates_made:,} politicians updated with new linked_campaignx_we_vote_id. " \
                "{total_to_convert_after:,} remaining. " \
                "".format(
                    total_to_convert_after=total_to_convert_after,
                    updates_made=updates_made)
        except Exception as e:
            status += "ERROR_CAMPAIGNX_BULK_UPDATE_update_campaignx_with_linked_politician_we_vote_id: {e} " \
                      "".format(e=e)
            success = False

        # Mark the politicians as verified
        try:
            Politician.objects.bulk_update(
                politician_update_list, ['linked_campaignx_we_vote_id_verified_in_campaignx'])
            status += \
                "{updates_made:,} updates of linked_campaignx_we_vote_id_verified_in_campaignx. " \
                "".format(
                    updates_made=updates_made)
        except Exception as e:
            status += "ERROR_POLITICIAN_BULK_UPDATE_update_campaignx_with_linked_politician_we_vote_id: {e} " \
                      "".format(e=e)
            success = False
    else:
        status += "NO_UPDATES_NEEDED_update_campaignx_with_linked_politician_we_vote_id "

    results = {
        'status': status,
        'success': success,
    }
    return results
