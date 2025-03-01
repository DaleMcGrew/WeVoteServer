import logging
import os
import random
from locust import HttpUser, task, constant, events

# --- Configure Logs ---
DIR = os.path.dirname(os.path.abspath(__file__))
log_dir = os.path.join(DIR, "logs")
os.makedirs(log_dir, exist_ok=True)

# Create the full path to your log file
log_file_path = os.path.join(log_dir, "response.log")

# Logger for requests
logger = logging.getLogger("logger")
logger.setLevel(logging.INFO)
handler = logging.FileHandler(log_file_path)
formatter = logging.Formatter('%(asctime)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# --- Event Listener ---
@events.request.add_listener
def log_success( url, exception, response_time, response_length, **kwargs):
    if exception:
        logger.info(f"Request to {url} failed with exception {exception} | Response time: {response_time} ms | Response length: {response_length}")
    else:
        logger.info(
            f"Request: {url}  | Response time: {response_time} ms | Response length: {response_length}"
        )


class PoliticianPageLoadTest(HttpUser):
    wait_time = constant(0)
    urls = [
            "/apis/v1/politicianRetrieve/?seo_friendly_path=lance-roorda-politician-from-iowa",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=nancy-a-montgomery-politician-from-new-york",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=chris-friedel-politician-from-montana",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=gary-seyring-politician-from-illinois",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=clint-barras-politician-from-florida",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=anne-flottman-politician-from-ohio",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=amy-lyon-politician-from-kansas",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=jamie-berryhill-politician-from-texas",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=chris-ekstrom-politician-from-texas",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=pablo-cuevas-politician-from-virginia",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=rebecca-s-colaw-politician-from-virginia",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=riley-edward-ingram-politician-from-virginia",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=peter-benik-politician-from-new-Hampshire",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=derek-morgan-politician-from-Nevada",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=jim-black-politician-from-north-Carolina",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=john-clark-politician-from-new-Mexico",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=greg-morris-politician-from-Georgia",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=vincent-wilson-politician-from-south-Carolina",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=brian-johnson-politician-from-Arizona",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=erika-stotts-pearson-politician-from-Tennessee",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=/ruth-linoz-politician-from-Oregon",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=michael-henry-politician-from-Connecticut",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=mitch-rushing-politician-from-Kentucky",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=michael-rennaker-politician-from-Indiana",
            "/apis/v1/politicianRetrieve/?seo_friendly_path=susan-larson-politician-from-Minnesota",
        ]
    
    @task
    def load_politician_pages(self):
        url = random.choice(self.urls)
        self.client.get(url, name="Politician Page")
