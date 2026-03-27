import json
import logging
import os

# Django must be initialized at module level so it runs once per cold start
# and is reused across warm Lambda invocations.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

import wevote_functions.admin

logger = wevote_functions.admin.get_logger(__name__)


def handler(event, context):
    """
    Lambda handler for SQS-triggered async jobs.

    Replaces the long-polling runsqsworker.py management command.
    Messages arrive from submit_web_function_job() in aws/controllers.py.

    On success Lambda automatically deletes the message from the queue.
    On exception the message becomes visible again and eventually routes to
    the dead-letter queue after maxReceiveCount retries.
    """
    for record in event['Records']:
        message_id = record['messageId']
        attributes = record.get('messageAttributes', {})

        if 'Function' not in attributes:
            logger.error("SQS record %s missing Function attribute", message_id)
            raise ValueError(f"SQS record {message_id} missing required Function message attribute")

        function_name = attributes['Function']['stringValue']
        body = json.loads(record['body'])

        logger.info("SQS Lambda: function=%s messageId=%s", function_name, message_id)

        if function_name == 'caching_facebook_images_for_retrieve_process':
            from import_export_facebook.controllers import caching_facebook_images_for_retrieve_process
            caching_facebook_images_for_retrieve_process(
                body['repair_facebook_related_voter_caching_now'],
                body['facebook_auth_response_id'],
                body['voter_we_vote_id_attached_to_facebook'],
                body['voter_we_vote_id_attached_to_facebook_email'],
                body['voter_we_vote_id'],
            )
        elif function_name == 'voter_cache_facebook_images_process':
            from voter.controllers import voter_cache_facebook_images_process
            voter_cache_facebook_images_process(
                body['voter_id'],
                body['facebook_auth_response_id'],
                False,  # is_retrieve — always False for this job type
            )
        else:
            raise ValueError(f"Unknown SQS function: {function_name}")
