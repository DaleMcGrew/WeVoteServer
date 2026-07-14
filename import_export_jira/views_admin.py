# import_export_jira/views_admin.py
# Brought to you by We Vote. Be good.
# -*- coding: UTF-8 -*-

import os
import tempfile
import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from wevote_functions.functions import positive_value_exists
from voter.models import voter_has_authority
from admin_tools.views import redirect_to_sign_in_page
from config.base import get_environment_variable
from jira.exceptions import JIRAError
from .controllers import JiraExcelLoader, JiraApiControl, MAX_SUBTASK_COLUMNS

logger = logging.getLogger(__name__)


def get_jira_config():
    """
    Lazy-load JIRA configuration from environment variables.

    Returns:
        Tuple of (jira_url, username, api_token, project_key, missing_vars)
    """
    jira_url = get_environment_variable("JIRA_URL", no_exception=True)
    jira_username = get_environment_variable("JIRA_USERNAME", no_exception=True)
    jira_api_token = get_environment_variable("JIRA_API_TOKEN", no_exception=True)
    jira_project_key = get_environment_variable("JIRA_PROJECT_KEY", no_exception=True)

    missing_vars = [
        name
        for name, val in [
            ("JIRA_URL", jira_url),
            ("JIRA_USERNAME", jira_username),
            ("JIRA_API_TOKEN", jira_api_token),
            ("JIRA_PROJECT_KEY", jira_project_key),
        ]
        if not val
    ]

    return jira_url, jira_username, jira_api_token, jira_project_key, missing_vars


@login_required
def jira_import_view(request):
    authority_required = {"admin"}
    if not voter_has_authority(request, authority_required):
        return redirect_to_sign_in_page(request, authority_required)

    jira_url, jira_username, jira_api_token, jira_project_key, missing_vars = (
        get_jira_config()
    )

    preview_summary = None
    import_stats = None
    action = None

    if request.method == "POST":
        action = request.POST.get("action", "")
        uploaded_file = request.FILES.get("excel_file")

        if not uploaded_file:
            messages.error(
                request,
                "No file uploaded. Please select an Excel (.xlsx) or CSV (.csv) file.",
            )
        else:
            # Validate file extension early
            valid_extensions = {".xlsx", ".xls", ".csv"}
            ext = os.path.splitext(uploaded_file.name)[1].lower()
            if ext not in valid_extensions:
                messages.error(
                    request, "Please upload a valid file (.xlsx, .xls, or .csv)"
                )
            else:
                tmp_path = None
                try:
                    suffix = ext or ".xlsx"
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=suffix
                    ) as tmp:
                        for chunk in uploaded_file.chunks():
                            tmp.write(chunk)
                        tmp_path = tmp.name

                    try:
                        raw_count = int(request.POST.get("subtask_count", 0))
                    except (ValueError, TypeError):
                        raw_count = 0
                    subtask_count = max(0, min(raw_count, MAX_SUBTASK_COLUMNS))
                    subtask_names = []
                    for i in range(subtask_count):
                        name = request.POST.get(f"subtask_name_{i}", "").strip()
                        if name:
                            subtask_names.append(name)

                    loader = JiraExcelLoader(tmp_path, subtask_names=subtask_names)

                    if action == "preview":
                        preview_summary = loader.get_summary()
                        # Warn user about large uploads
                        total_items = (
                            preview_summary["totals"]["total_candidates"]
                            + preview_summary["totals"]["total_sub_tasks"]
                            + preview_summary["total_epics"]
                        )
                        if total_items > 500:
                            messages.warning(
                                request,
                                f"Large import detected: {total_items} total items. "
                                f"Import may take several minutes.",
                            )
                        if total_items > 2000:
                            messages.warning(
                                request,
                                f"Very large import: {total_items} items. "
                                f"Consider splitting into smaller batches.",
                            )
                    elif action == "import":
                        if missing_vars:
                            messages.error(
                                request,
                                f"Cannot import: missing JIRA credentials: {', '.join(missing_vars)}",
                            )
                        else:
                            epics = loader.load()
                            try:
                                api_control = JiraApiControl(
                                    jira_url=jira_url,
                                    username=jira_username,
                                    api_token=jira_api_token,
                                    project_key=jira_project_key,
                                )
                            except JIRAError as e:
                                messages.error(
                                    request,
                                    f"Failed to connect to JIRA: {str(e)}. "
                                    f"Check your credentials and JIRA URL.",
                                )
                            else:
                                import_stats = api_control.load_all_epics(epics)
                                messages.success(request, "Import to JIRA completed.")
                except ValueError as e:
                    messages.error(request, f"Invalid file format: {str(e)}")
                except FileNotFoundError as e:
                    messages.error(request, f"File error: {str(e)}")
                except JIRAError as e:
                    logger.exception("JIRA API error during import")
                    messages.error(request, f"JIRA API error: {str(e)}")
                except Exception as e:
                    logger.exception("Unexpected error processing JIRA import")
                    messages.error(request, f"Unexpected error: {str(e)}")
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        os.unlink(tmp_path)

    template_values = {
        "missing_vars": missing_vars,
        "preview_summary": preview_summary,
        "import_stats": import_stats,
        "action": action,
        "header_suggestions": (
            preview_summary.get("header_suggestions", []) if preview_summary else []
        ),
    }
    return render(request, "import_export_jira/jira_import.html", template_values)
