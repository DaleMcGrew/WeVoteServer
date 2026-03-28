# README for Installation with Docker
[Back to root README](../README.md)

Only [Docker Desktop](https://docs.docker.com/get-docker/) is required.

[WSL 2](https://learn.microsoft.com/en-us/windows/wsl/compare-versions#comparing-wsl-1-and-wsl-2) users should follow [this guide](https://docs.docker.com/desktop/wsl/) as well.

## Installation

### 1. Clone your WeVoteServer fork (replace wevote with your github username)

  ```
  git clone https://github.com/wevote/WeVoteServer.git
  cd WeVoteServer
  ```

### 2. Create an environment file called `.env` to provide required settings. Example:

  ```
  DATABASE_PASSWORD=MyDBpassword
  DJANGO_SUPERUSER_EMAIL=email@test.com
  DJANGO_SUPERUSER_PASSWORD=MyAdminPassword

  # You can optionally override the default values for database user and name
  # DATABASE_USER=postgres
  # DATABASE_NAME=wevoteserverdb
  ```

### 3. Create Docker network
We will run all WeVote docker containers in an isolated docker network. Since the backend (WeVoteServer) and frontend (WebApp) both use docker compose (which typically manages docker networks for us), we must manually create this shared network to avoid conflicts. Even if you are not planning on running your own frontend, this step must still be completed.
```
docker network create wevote
```

### 4. Starting the containers

To start the WeVote API service and dependencies, use one of these commands. If you are just getting started, we recommend using the first (foreground) method below. These commands assume you are in the `WeVoteServer` folder created in Step 1 above.

#### 1. Start in the foreground (for debugging/logs):
```
docker compose up
```
This command builds, (re)creates, and starts all services, and aggregates their logs in your terminal. **Press `Ctrl+C` to stop the containers gracefully.**

#### 2. Start in the background (detached mode):
```
docker compose up -d
```
The `-d` (detached) flag runs containers in the background, leaving them running after you exit the terminal. Once started in detached state, use this command to stop the containers:
```
docker compose down
```

Once the containers are running, you can now access the API at [http://localhost:8000/](http://localhost:8000/)

### 5. Remove containers and data

To stop and remove all containers and saved data (including database data), run the following command. Only do this if you want to completely remove your development environment or start over from scratch.
```
docker compose down -v
```
You can also remove the wevote docker network:
```
docker network rm wevote
```

## Resources

1. Docker Compose
    
    - [CLI](https://docs.docker.com/compose/reference/)

    - [Networking](https://docs.docker.com/compose/networking/)

2. PostgreSQL

    - [Official Docker Image](https://hub.docker.com/_/postgres)

[Back to root README](../README.md)
