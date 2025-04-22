[Back to Install Table of Contents](README_API_INSTALL.md)

[Link to WeVote Server load test](../loadtest/README.md)

# Politician Page LoadTest 

## Introduction
   When Google (or a voter) visits one of our Politician URLs, it seems like sometimes there is a delay retrieving the politician information from the API server. This delay seems to be causing Google to then “de-list” the politician page. The information does seem to eventually load, but too late for Google. (See “PAGE PRIOR TO API LOADING“ vs. “FULLY LOADED PAGE” below) I think this is related to our server network running out of available network connections for API calls.

   What we've done with this Politician Page Loadtest, is to stress test our system to confirm/deny this is the case. We can run this test, to see what happens when our network receives many requests in rapid succession. (Related to Jira WV-891)

## Install Locust
  [Install Locust](https://docs.locust.io/en/latest/installation.html)

## Run Politician Page Loadtest
   Follow the below steps and run the commands from the WeVoteServer folder:
   
    1.  $ loadtest/Politician_Page_Load.sh
    
    2.  Open http://localhost:8089 in your web browser and start the testing. (according to the current code there are 2000 users, spawning rate is 2000 and the process runs for 10min.)
    3.  Wait and Check for failures.
    4.  The response time for each request is logged in ‘response.log’ file under loadtest/logs directory.
           (Request Event arguments (arguments in the log file):
                request_type – Request type method used
                name – Path to the URL that was called (or override name if it was used in the call to the client)
                response_time – Time in milliseconds until exception was thrown
                response_length – Content-length of the response)
  
    5.  If there are no failures please try running the same code in master-worker model by modifying the code as below,
          Master:
          Politician_Page_Load.sh:
              DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
              locust -f $DIR/PoliticianPageLoad.py --host=https://api.wevoteusa.org --masters --users 100 --spawn-rate 100 --run-time 10m
              	master - loadtest/Politician_Page_Load.sh
          Worker:
              open separate terminals and run the below command (open 4-5 terminals): 
              $ workers - locust -f loadtest/PoliticianPageLoad.py --worker
        


  
  
