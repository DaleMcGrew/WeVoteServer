
import json
import logging

from django import forms
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from admin_tools.views import redirect_to_sign_in_page
from voter.models import voter_has_authority

class CloudWatchLogForm(forms.Form):
    level = forms.ChoiceField(
        choices=[
            ("INFO", "INFO"),
            ("ERROR", "ERROR"),
            ("WARN", "WARN"),
            ("DEBUG", "DEBUG"),
            ("CRITICAL", "CRITICAL"),
        ],
        required=True,
    )
    action = forms.CharField(max_length=120, required=True)
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}), required=True)
    user_context = forms.CharField(
        max_length=120,
        required=False,
        help_text="Optional: something like voter_id or username (avoid PII).",
    )

@login_required
def cloudwatch_log_form_view(request):
    # admin, analytics_admin, partner_organization, political_data_manager, political_data_viewer, verified_volunteer
    authority_required = {'admin'}
    if not voter_has_authority(request, authority_required):
        return redirect_to_sign_in_page(request, authority_required)

    result = None

    if request.method == "POST":
        form = CloudWatchLogForm(request.POST)
        if form.is_valid():

            result = {
                "action": form.cleaned_data["action"],
                "level": form.cleaned_data["level"],
                "message": form.cleaned_data["message"],
                "user_context": form.cleaned_data["user_context"],
            }
            if result["level"] == "INFO":
                logging.info("[TEST_WARNING]: " + json.dumps(result))
            elif result["level"] == "WARN":
                logging.warning("[TEST_WARNING]: " + json.dumps(result))
            elif result["level"] == "DEBUG":
                logging.debug("[TEST_WARNING]: " + json.dumps(result))
            elif result["level"] == "ERROR":
                logging.error("[TEST_WARNING]: " + json.dumps(result))
            elif result["level"] == "CRITICAL":
                logging.critical("[TEST_WARNING]: " + json.dumps(result))
            result["success"] = True
        else:
            result = {"success": False, "error": "Form invalid", "details": form.errors}
    else:
        form = CloudWatchLogForm()

    return render(request, "cloudwatch_logging/cloudwatch_logging_form.html", {
        "form": form,
        "result": result,
    })
