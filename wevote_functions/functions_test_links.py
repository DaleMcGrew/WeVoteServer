import requests
import wordninja
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from urllib.parse import urlparse
from langdetect import detect, LangDetectException
from config.environment_variable_functions import get_environment_variable
# import DNS
import tldextract
# from ipwhois import IPWhois
import re


# Load environment variables from .env file
def get_required_env_var(var_name):
    value = get_environment_variable(var_name)

    if value is None:
        raise ValueError(f"Environment variable '{var_name}' is missing from the env file.")
    if value.strip() == "":
        raise ValueError(f"Environment variable '{var_name}' is set but has a null/empty value in the env file.")

    return value


try:
    BROWSERSTACK_USERNAME = get_required_env_var("BROWSERSTACK_USERNAME")
    BROWSERSTACK_ACCESS_KEY = get_required_env_var("BROWSERSTACK_ACCESS_KEY")
except Exception as e:
    BROWSERSTACK_USERNAME = ''
    BROWSERSTACK_ACCESS_KEY = ''


# Function to render JavaScript-heavy pages using Selenium and BrowserStack
def get_rendered_page_content(url):

    options = Options()
    bstack_options = {
        "os": "Windows",
        "osVersion": "11",
        "browserName": "Chrome",
        "browserVersion": "latest",
        "projectName": "My Project",
        "buildName": "Build 1",
        "sessionName": "Link Test",
        "userName": BROWSERSTACK_USERNAME,
        "accessKey": BROWSERSTACK_ACCESS_KEY,
    }
    options.set_capability('bstack:options', bstack_options)

    try:
        driver = webdriver.Remote(
        command_executor='http://hub.browserstack.com/wd/hub',
        options=options
        )
        driver.get(url)
        driver.implicitly_wait(5)
        return driver.page_source
    except Exception as e:
        print(f"Error rendering page: {e}")
        return ""
    finally:
        driver.quit()


# Function to extract politician name from URL using wordninja
def extract_politician_name(url: str) -> list:
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "").lower()

    if any(social in domain for social in ["facebook", "twitter", "x.com", "instagram", "linkedin", "tiktok", "snapchat"]):
        # Social profile: take the first part of the path
        path_parts = parsed.path.strip("/").split("/")
        if path_parts:
            raw_text = path_parts[0]  # first part (e.g., username)
        else:
            raw_text = domain
    else:
        # Regular website: take the domain name before the first dot
        raw_text =  domain.split(".")[0].lower()
    
    # Split into candidate words
    tokens = wordninja.split(raw_text)

    # Filter out noise: single letters, generic words, years, etc.
    stopwords = {"for", "vote", "elect", "my", "our", "team"}
    tokens = [
        t for t in tokens
        if len(t) > 2 and not t.isdigit() and t.lower() not in stopwords
    ]

    return tokens


# Function to validate URL format
def is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return all([parsed.scheme, parsed.netloc])  # Ensure scheme (http/https) and domain exist
    except ValueError:
        return False


# Function to detect language of the text
def detect_language(text):
    try:
        return detect(text)
    except LangDetectException:
        return "unknown"


# Function to toggle between http and https   
def toggle_http_https(url: str) -> str:
    if url.startswith("https://"):
       return  url.replace("https://", "http://", 1)  
    elif url.startswith("http://"):
       return url.replace("http://", "https://", 1)
    return url


# Functions to check for SSL and domain alias redirects
def normalize_url(url):
    """Removes scheme and trailing slash for comparison"""
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]  # remove www
    return f"{netloc}{parsed.path}".rstrip('/')


# Check for SSL redirect (http to https)
def is_ssl_redirect(original_url, redirected_url):
    return original_url.startswith("http://") and redirected_url.startswith("https://") \
           and normalize_url(original_url) == normalize_url(redirected_url)


# Check for domain alias redirect (e.g., twitter.com to x.com)
def is_domain_alias_redirect(original_url, redirected_url):
    # Add any domain equivalences here
    domain_aliases = {
        "twitter.com": "x.com",
        "www.twitter.com": "x.com",  # add both if needed
    }
    orig_parsed = urlparse(original_url)
    redir_parsed = urlparse(redirected_url)

    orig_domain = orig_parsed.netloc.lower().replace("www.", "")
    redir_domain = redir_parsed.netloc.lower().replace("www.", "")
    
    return domain_aliases.get(orig_domain) == redir_domain and orig_parsed.path == redir_parsed.path


# Function to check if a domain is parked by its registrar
def is_registrar_parked(domain: str) -> bool:
    """
    Determine if a domain is likely parked.
    Uses DNS + IPWhois.
    """
    try:
        # Extract clean domain (remove subdomains)
        extracted = tldextract.extract(domain)
        clean_domain = f"{extracted.domain}.{extracted.suffix}"

        # # Initialize and discover name servers
        # DNS.DiscoverNameServers()
        #
        # # Perform an A record lookup
        # request = DNS.Request(qtype="A")
        # response = request.req(name=clean_domain)
        #
        # # If no answers, domain likely parked or expired
        # if not response.answers:
        #     return True
        #
        # # Get IP address of the domain
        # ip_address = response.answers[0]['data']
        # obj = IPWhois(ip_address)
        # res = obj.lookup_rdap(asn_methods=["whois"])
        #
        #
        # # Known parked domain registrars (can extend this list)
        # parked_networks = [
        #     "godaddy", "namecheap", "network solutions", "domain.com",
        #     "google", "squarespace", "hover", "register.com",
        #     "tucows", "enom", "porkbun", "flywheel", "bluehost", "1&1", "ionos"
        # ]
        #
        # registrar = (res.get("network", {}) or {}).get("name", "")
        # if registrar and any(pn in registrar.lower() for pn in parked_networks):
        #     return True

        return False
    except Exception as e:
        # Fail-safe: assume parked if we can't determine
        return True


# Function to check if URL is a social media profile
def is_social_profile_url(url):
    social_keywords = ['facebook', 'twitter', 'x.com', 'instagram', 'linkedin', 'tiktok', 'snapchat']
    parsed_url = urlparse(url.lower())
    return any(keyword in parsed_url.netloc for keyword in social_keywords)

# Function to check URL status and analyze content
def check_url_status(url: str, politician_name: str, result: dict) -> dict:
    expired_site_keywords = [
        'notfound', 'this page could not be found', 'sorry', 'flywheel', 'godaddy', 'site paused', 'lapsed',
        'unknown domain',
        'denied', 'error', "this account doesn’t exist", 'website expired', "4d", "casino", "betting", "gambling", 
        "loan", "bitcoin", "crypto", "pharmacy", "hack","Daftar","game", "javascript is not available",
        "something went wrong", "log into facebook",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    }
    js_required_strings = [
        "javascript is not available",
        "please enable javascript",
        "use a supported browser",
        "something went wrong",
        "switch to a supported browser",
        "please disable extensions and try again",
        "this browser is not supported",
        "privacy related extensions may cause issues",
    ]
    result["is_social_account"] = is_social_profile_url(url)
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    result["is_registrar_parked_url"] = is_registrar_parked(domain)
    try:
        response = requests.get(url,  headers=headers, allow_redirects=True, timeout=5)
        result["final_url"] = response.url

        # Check for SSL or domain alias redirects
        is_redirect = normalize_url(url).lower() != normalize_url(response.url).lower()
        
        if is_redirect:
            result["is_redirect_ssl"] = is_ssl_redirect(url, response.url) or is_domain_alias_redirect(url, response.url)
            result["is_redirect"] = not result["is_redirect_ssl"]

        # Extract and clean the contents of the webpage    
        soup =  BeautifulSoup(response.content, "html.parser")
        content_cleaned = ' '.join(soup.get_text().lower().split())
        # Check for expired keywords
        matching_keywords = [keyword for keyword in expired_site_keywords if keyword in content_cleaned]

        # Detect language and extract politician name
        language = detect_language(content_cleaned)
        url_matching_words = extract_politician_name(url)

        if not content_cleaned.strip() or any(phrase in content_cleaned for phrase in js_required_strings) or result["is_social_account"] :
            rendered_content = get_rendered_page_content(url)
            soup = BeautifulSoup(rendered_content, "html.parser")
            content_cleaned = soup.get_text().strip().lower()
            matching_keywords = [keyword for keyword in expired_site_keywords if keyword.lower() in content_cleaned.lower()]
            language = detect_language(content_cleaned)
            url_matching_words = extract_politician_name(url)

        if result["is_social_account"]:
            result["social_account_does_not_exist"] = False
            if response.status_code in {404, 403}:
                result["status"] = "Failed"
                if url.startswith("http://"):
                    result["status_code_http"] = response.status_code
                    result["status_description_http"] = "This link is NOT available to the public"
                else:   
                    result["status_code_https"] = response.status_code
                    result["status_description_https"] = "This link is NOT available to the public"
                result["success"] = False
                return result
            elif response.status_code == 400:
                # Clean politician name
                politician_tokens = [
                    t for t in re.sub(r"[^\w\s]", "", politician_name).lower().split() if len(t) > 2
                ]

                matched_words = [
                    word for word in url_matching_words + politician_tokens if word in content_cleaned
                ]
                if matched_words:
                    matched_words = [word for word in url_matching_words if word in content_cleaned]
                    result["status"] = "Success" 
                    result["is_valid"] = True
                    if url.startswith("http://"):
                        result["status_code_http"] = response.status_code
                        result["status_description_http"] = "This link works fine"
                        result["status_code_https"] = 0
                        result["status_description_https"] = ""
                    else:
                        result["status_code_https"] = response.status_code
                        result["status_description_https"] = "This link works fine"
                        result["status_code_http"] = 0
                        result["status_description_http"] = ""
                    result["success"] = True 
                    return result
                
        if response.status_code == 200:
            result["is_valid"] = True
            result["status"] = "Success"
            status_description = None
            if result["is_social_account"]:
                result["social_account_does_not_exist"] = False
            if url.startswith("http://"):
                result["status_code_http"] = response.status_code
                result["status_description_http"] = "Valid URL"
            else:
                result["status_code_https"] = response.status_code
                result["status_description_https"] = "Valid URL"
            result["success"] = True              
            if "twitter.com" in url and "x.com" in result["final_url"]:
                result["status"] = "Success"
                status_description = "Twitter link works fine"
                result["success"] = True               
            elif normalize_url(url) != normalize_url(result["final_url"]):
                result["is_redirct"] = True
                result["is_valid"] = False
                result["status"] = "Failed"
                if result["is_social_account"]:
                    result["social_account_does_not_exist"] = True
                status_description = "Redirected to an unexpected domain"
                result["success"] = False                            
            elif matching_keywords or  language != "en":
                result["status"] = "Failed"
                result["is_valid"] = False
                if result["is_social_account"]:
                    result["social_account_does_not_exist"] = True
                status_description = "Parked domain or spam"
                result["success"] = False 
            if status_description:
                if url.startswith("http://"):
                    result["status_code_http"] = response.status_code
                    result["status_description_http"] = status_description
                else:
                    result["status_code_https"] = response.status_code
                    result["status_description_https"] = status_description
            return result
        elif response.status_code != 200:
            result["status"] = "Failed"
            if url.startswith("http://"):
                result["status_code_http"] = response.status_code
                result["status_description_http"] = "The Url is Not Active or Not Valid"
            else:
                result["status_code_https"] = response.status_code
                result["status_description_https"] = "The Url is Not Active or Not Valid"
            result["success"] = False
            return result
        return result
    except requests.exceptions.ConnectionError as e:
        result["status"] = "Failed"
        result["status_description_https"] = str(e)
        result["success"] = False
        return result
    except requests.exceptions.RequestException as e:
        result["status"] = "Failed"
        result["status_description_https"] = str(e)
        result["success"] = False
        print('ConnectionError:', e)
        return result


# Main function to validate link and gather status information
def is_valid_link_with_status(url: str, politician_name:str) -> dict:
    result = {
        "is_redirect": False,
        "is_redirect_ssl": False,
        "is_registrar_parked_url": False,
        "is_valid": False,
        "is_social_account": False,
        "social_account_does_not_exist": True,
        "status": "",
        "status_code_http": 0,
        "status_description_http": "",
        "status_code_https": 0,
        "status_description_https": "",
        "success": "",
        "incoming_url": url,
        "final_url": ""
    }

    if not is_valid_url(url):
        result["status"] = "Invalid URL"
        result["success"] = False
        return result

    result = check_url_status(url, politician_name, result)
    if result["success"]:
        return result

    alternative_url = toggle_http_https(url)
    return check_url_status(alternative_url, politician_name, result)


def test_urls(urls_to_test, politician_name):
    results = []
    for url in urls_to_test:
        result = is_valid_link_with_status(url, politician_name)
        results.append(result)

    return results
    