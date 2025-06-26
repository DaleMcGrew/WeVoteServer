# README for Installation with Docker
[Back to root README](../README.md)

Only [Docker Desktop](https://docs.docker.com/get-docker/) is required.

[WSL 2](https://learn.microsoft.com/en-us/windows/wsl/compare-versions#comparing-wsl-1-and-wsl-2) users should follow [this guide](https://docs.docker.com/desktop/wsl/) as well.

## Installation

1. Clone your WeVoteServer fork

    ```
    git clone https://github.com/wevote/WeVoteServer.git
    cd WeVoteServer
    ```

2. Create an environment file called `.env` to provide required settings. Example:

    ```
    DATABASE_PASSWORD=MyDBpassword
    DJANGO_SUPERUSER_EMAIL=email@test.com
    DJANGO_SUPERUSER_PASSWORD=MyAdminPassword

    # You can optionally override the default values for database user and name
    # DATABASE_USER=postgres
    # DATABASE_NAME=wevoteserverdb
    ```

3. Create and start containers

    ```
    docker compose up --detach --build --remove-orphans
    ```
    Use the `--profile` flag, if you need to also run the AWS localstack container (when developing features specific to AWS environment).
    ```
    docker compose --profile optional up --detach --build --remove-orphans
    ```
    Once docker is running, you can now access the API at [http://localhost:8000/](http://localhost:8000/)

4. Stop and remove containers

    ```
    docker compose down
    ```
    Use the `--volumes` flag to remove volumes (includes database data - you will lose all previously saved data). Only do this if you want to completely remove development environment or start over from scratch.
    ```
    docker compose down --volumes
    ```

## Resources

1. Docker Compose
    
    - [CLI](https://docs.docker.com/compose/reference/)

    - [Networking](https://docs.docker.com/compose/networking/)

2. PostgreSQL

    - [Official Docker Image](https://hub.docker.com/_/postgres)

[Back to root README](../README.md)
