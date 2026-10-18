# KK-67 Docker

![Docker](https://img.shields.io/badge/Docker-2CA5E0?style=for-the-badge&logo=docker&logoColor=white)
![Node](https://img.shields.io/badge/Node.js-339933?style=for-the-badge&logo=nodedotjs&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PHP](https://img.shields.io/badge/php-%23777BB4.svg?style=for-the-badge&logo=php&logoColor=white)

KK-67 website uses the following services:

- [KK-67 Frontend](https://github.com/Kraftsportsklubben-av-1967/kk67-frontend)
- [KK-67 Backend](https://github.com/Kraftsportsklubben-av-1967/kk67-backend)
- [KK-67 Backend (PHP version)](https://github.com/Kraftsportsklubben-av-1967/kk67-backend-php)


## Prerequesits

You will need docker-compose to be able to use this repository

0. https://docs.docker.com/compose/install/

## Setup

1. Clone the repo with submodules

```sh
$ git clone --recurse-submodules git@github.com:Kraftsportsklubben-av-1967/kk67-docker.git
```

> If you already cloned without `--recurse-submodules`, run:
> ```sh
> $ git submodule update --init --recursive
> ```

2. Copy `.env.example` to `.env` in the repository root. This local file is
   Git-ignored; keep secrets out of `.env.example`.

3. Follow the setup guides in each submodule to configure their `.env` files

4. Build the compose `docker-compose up --build`

> After this is done you can simply use `docker-compose up`

1. The services will be running:
   1. Frontend: `http://localhost:3000` (configurable via `FE_PORT`)
   2. PHP backend: `http://localhost:4000` (configurable via `BE_PHP_PORT`)
   3. Flask backend: `http://localhost:5000` (enabled by the `dev` compose profile, e.g. `docker compose --profile dev up`)

`FE_PORT` and `BE_PHP_PORT` change host ports only; the containers listen on
3000 and 4000. If you change the PHP host port, update the frontend's development
backend URL too. `FE_PROXY_PORT` must match the frontend's `VITE_PROXY_PORT`.

> Additional outputs will be displayed in your terminal. Remember to close this once you're done.

## Checks

With Python 3 and Docker Compose installed, check the port wiring without
starting containers:

```sh
python -m unittest discover -s tests
```

## Deployments

Each application owns its upload scripts, tests and GitHub Actions workflow:

- [Frontend deployment](https://github.com/Kraftsportsklubben-av-1967/kk67-frontend#production-ci)
- [PHP backend deployment](https://github.com/Kraftsportsklubben-av-1967/kk67-backend-php)

Their CI checks out only the application itself; it does not clone this Docker
repository or fetch deployment scripts from another project. Production uploads
run after merges or pushes to frontend `master` and PHP backend `main`.

Existing FTP credentials can stay in this repository's private, ignored `.env`.
Pass that file's path with the application uploader's `-EnvFilePath` option;
there is no need to copy the password. Explicit `-Credential` takes precedence.
CI uses encrypted application-repository secrets instead of a local file.

Keep `.env` and editor backups private. Saved local passwords are plaintext;
never commit them or put FTP secrets in `VITE_` variables.

## Why docker-compose?

Using docker-compose allows us to use virtual machines to load all dependencies and development environment without interfering with our own personal setup. It recreates an identical environment for everyone using the `docker-compose.yml` config file. As for members of KK, this repository is mainly ment for development purposes. How the frontend and backend is actually is deployed is unfortunatley without docker, but theres nothing we can do about that currently due to our ISP...

Check out this [video](https://www.youtube.com/watch?v=Gjnup-PuquQ&ab_channel=Fireship) to learn more
