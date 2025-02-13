# import_export_google_play_store/controllers.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

import json
import requests
from config.base import get_environment_variable
from exception.models import handle_exception
import wevote_functions.admin
from googleapiclient.discovery import build
from google.oauth2 import service_account


logger = wevote_functions.admin.get_logger(__name__)

OPENREPLAY_BASE_URL = get_environment_variable("OPENREPLAY_BASE_URL", no_exception=True)
OPENREPLAY_PROJECT_KEY = get_environment_variable("OPENREPLAY_PROJECT_KEY", no_exception=True)
OPENREPLAY_ORGANIZATION_KEY = get_environment_variable("OPENREPLAY_ORGANIZATION_KEY", no_exception=True)
# Replace with the path to your service account key file
SERVICE_ACCOUNT_FILE = '/Users/dalemcgrew/PycharmProjects/WeVoteServer/import_export_google_play_store/we-vote-ballot-fb222cde2c46.json'
SCOPES = ['https://www.googleapis.com/auth/playdeveloperreporting']


def build_service():
  """Builds the Play Developer Reporting API service."""
  creds = service_account.Credentials.from_service_account_file(
      SERVICE_ACCOUNT_FILE, scopes=SCOPES)
  service = build('playdeveloperreporting', 'v1beta1', credentials=creds)
  return service


def get_crash_rate(service, package_name):
  """Fetches crash rate data for the specified package."""
  try:
    request_body = {
        # "dimensions": ["versionCode"],
        "metrics": ["crashRate", "crashRate7dUserWeighted", "crashRate28dUserWeighted", "distinctUsers"],
        "timelineSpec": {
            "aggregationPeriod": "DAILY",
            "endTime": {
                "day": 30,
                "month": 11,
                "year": 2024
            },
            "startTime": {
                "day": 1,
                "month": 2,
                "year": 2022
            }
        }
    }
    result = service.vitals().crashrate().query(
        name=f"apps/{package_name}/crashRateMetricSet", body=request_body).execute()
    return result

  except Exception as e:
    print(f"get_crash_rate - An error occurred: {e}")
    return None


def get_anr_rate(service, package_name):
  """Fetches crash rate data for the specified package."""
  try:
    request_body = {
        # "dimensions": ["versionCode"],
        "metrics": ["anrRate", "anrRate7dUserWeighted", "distinctUsers"],
        "timelineSpec": {
            "aggregationPeriod": "DAILY",
            "endTime": {
                "day": 21,
                "month": 1,
                "year": 2025
            },
            "startTime": {
                "day": 1,
                "month": 2,
                "year": 2022
            }
        }
    }
    result = service.vitals().anrrate().query(
        name=f"apps/{package_name}/anrRateMetricSet", body=request_body).execute()
    return result

  except Exception as e:
    print(f"get_anr_rate - An error occurred: {e}")
    return None


def get_errors(service, package_name):
  try:
    # result = service.vitals().errors().counts().get(name=f"apps/{package_name}/errorCountMetricSet")
    # result = service.vitals().errors().reports()
    # return result
    request = service.vitals().errors().counts().get(name=f"apps/{package_name}/errorCountMetricSet")
    response = request.execute()
    return response
  except Exception as e:
    print(f"get_errors - An error occurred: {e}")
    return None

