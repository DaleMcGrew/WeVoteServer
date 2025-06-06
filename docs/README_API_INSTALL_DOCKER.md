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

2. Set environment variables in `.env`

    ```
    DATABASE_PASSWORD    
    DJANGO_SUPERUSER_EMAIL
    DJANGO_SUPERUSER_PASSWORD
    POSTGRES_DB
    POSTGRES_PASSWORD
    POSTGRES_USER
    ```

3. Create and start containers

    ```
    docker compose up --detach
    ```
    Use the `--profile` flag, if you need AWS
    ```
    docker compose --profile optional up --detach
    ```
    Access the API at [http://localhost:8000/](http://localhost:8000/)

4. Stop and remove containers

    ```
    docker compose down
    ```
    Use the `--volumes` flag to remove volumes
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
