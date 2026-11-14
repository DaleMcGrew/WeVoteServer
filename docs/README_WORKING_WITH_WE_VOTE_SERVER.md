# Working with WeVoteServer API Endpoints

[Back to Install Table of Contents](README_API_INSTALL.md)

## Staying Synchronized with Latest Code

If you are returning to work on WeVoteServer after a few weeks or months, these are the steps:

Pull the latest code from the repository. Then:
For MAC:
####
    $ cd /Users/<YOUR NAME HERE>/PythonProjects/WeVoteServer/
    $ source /Users/<YOUR NAME HERE>/PythonEnvironments/WeVoteServer3.11/bin/activate

And if you are not using Docker, you will need to:

    (WeVoteServer3.11)$ pip install -r requirements.txt
    (WeVoteServer3.11)$ python manage.py makemigrations
    (WeVoteServer3.11)$ python manage.py migrate
    (WeVoteServer3.11)$ python manage.py createcachetable

For Linux/WSL:
####
    $ cd ~/<YOUR NAME HERE>/PythonProjects/WeVoteServer/
    $ source ~/<YOUR NAME HERE>/PythonEnvironments/WeVoteServer3.11/bin/activate

And if you are not using Docker, you will need to:

    (WeVoteServer3.11)$ pip install -r requirements.txt
    (WeVoteServer3.11)$ python manage.py makemigrations
    (WeVoteServer3.11)$ python manage.py migrate
    (WeVoteServer3.11)$ python manage.py createcachetable
    
Compare your local version of "config/environment_variables.json" with the master template version 
"[config/environment_variables-template.json](config/environment_variables-template.json)" and add or remove entries.


## Start up the Django server without Docker

Here are some commands we use quite a lot:
For MAC:
####
    $ cd /Users/<YOUR NAME HERE>/PythonProjects/WeVoteServer/
    $ source /Users/<YOUR NAME HERE>/PythonEnvironments/WeVoteServer3.11/bin/activate
    (WeVoteServer3.11)$ python manage.py runserver

For Linux/WSL:
####
    $ cd ~/<YOUR NAME HERE>/PythonProjects/WeVoteServer/
    $ source ~/<YOUR NAME HERE>/PythonEnvironments/WeVoteServer3.11/bin/activate
    (WeVoteServer3.11)$ python manage.py runserver

Find API admin tools here [https://wevotedeveloper.com:8000/admin](https://wevotedeveloper.com:8000/admin) or [http://localhost:8000/admin](http://localhost:8000/admin)

Find documentation for all the APIs here [https://wevotedeveloper.com:8000/apis/v1/docs](https://wevotedeveloper.com:8000/apis/v1/docs) or [http://localhost:8000/apis/v1/docs](http://localhost:8000/apis/v1/docs)

## Test Data

In order to effectively work with WeVoteServer, you will need election data. We have made it easy to set up your 
database with initial data that will help you do development. Visit the Admin Menu  to run "Fast Load Data From We Vote Master Servers"
[https://wevotedeveloper.com:8000/admin/sync_dashboard/](https://wevotedeveloper.com:8000/admin/sync_dashboard/) or [http://localhost:8000/admin/sync_dashboard/](http://localhost:8000/admin/sync_dashboard/) on your local machine and click the
"Fast Load" button. This takes about a half hour to complete, on a fast machine on a fast network.


## Working with WebApp 
See notes on working with the [Node/React/Flux WebApp mobile website](https://github.com/wevote/WebApp/blob/develop/docs/working/README_WORKING_WITH_WEB_APP.md) day-to-day

## Coding Standards

Please use descriptive full word variable names.

* In the lifecycle of most projects, fixing bugs and maintaining current features end up taking 
50%+ of total engineering time.
* Our goal is to create a code base that is easy to understand, making fixing bugs and maintaining 
current features as painless as possible. We will have many engineers working with this code, 
and we want to be welcoming to engineers who are new to the project.
* Short variable names can often create confusion, where a new engineer needs to spend time 
figuring out what a short variable name actually means. (Ex/ “per” or “p” instead of “person”.) 
For this project please use descriptive full word variable names.
* Fellow engineers should be able to zoom around the code and not get stopped with riddles created by short names.

## Checking In Code - Please Run Tests

Before checking in your code:

Request access to the We Vote team so you can check in code. Email: Dale.McGrew@WeVoteUSA.org

Please make sure to run our tests before checking in any code (Still not working in Python3 yet):

    source venv/bin/activate
    cd WeVoteServer
    python manage.py test

[Back to Install Table of Contents](README_API_INSTALL.md)
