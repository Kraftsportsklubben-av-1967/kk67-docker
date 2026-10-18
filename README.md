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

## Frontend deployment (FTPS)

`scripts\upload-frontend.ps1` builds `webroot\kk67-frontend` with `yarn build`
and uploads the **contents** of its `dist` folder. The default destination is
`ftp.c9ry3m6by.service.one`, directory
`c9ry3m6by_kk67ctcg/webroots/r1058728`, relative to the FTP login directory.
The destination must already exist.

Use PowerShell 7, Node.js 20.12 or newer, Yarn, and `curl.exe` with FTP/FTPS
support. Install the frontend dependencies first if needed:

```powershell
yarn --cwd .\webroot\kk67-frontend install --frozen-lockfile
```

Build and preview the destination and file count without connecting or asking
for credentials:

```powershell
pwsh -File .\scripts\upload-frontend.ps1 -WhatIf
```

Build and upload to the live site:

```powershell
pwsh -File .\scripts\upload-frontend.ps1
```

To save credentials, fill in these entries in the **repository-root `.env`**,
not the frontend's `.env`:

```dotenv
FTP_USERNAME='your-ftp-username'
FTP_PASSWORD='your-ftp-password'
```

Quote values containing spaces, `#`, or `$`. The script uses Node's built-in
dotenv parser without executing the file or expanding variables. `.env` is
Git-ignored and no longer tracked, but stores the password as **plaintext**;
keep it private. Never put these secrets in `VITE_` variables.

An explicit `-Credential` takes precedence over `.env`. If both saved values are
empty or absent, the script prompts securely; if only one is set, it stops with
an error. Credentials reach curl through standard input, not process arguments.
`-WhatIf` neither reads saved credentials nor connects to the server. Explicit
FTPS is required, with certificate verification enabled and no unencrypted fallback.

Use `-SkipBuild` to upload an existing `dist`, or combine it with `-WhatIf` to
preview without rebuilding. `-FtpHost` and `-RemotePath` override the destination.
The script creates asset subdirectories, overwrites matching files, and uploads
`index.html` last. It **never deletes remote files**, so backend files and
separately uploaded media absent from the build are preserved. A local video
included in `dist` will be uploaded along with the other frontend assets.

Only build output is uploaded: frontend source, `.env`, the backend, and the
frontend root's `.htaccess` are not included. Keep the server's existing SPA
routing configuration. Upload failures stop deployment, but files already
uploaded are not rolled back; the upload is not atomic.

## Why docker-compose?

Using docker-compose allows us to use virtual machines to load all dependencies and development environment without interfering with our own personal setup. It recreates an identical environment for everyone using the `docker-compose.yml` config file. As for members of KK, this repository is mainly ment for development purposes. How the frontend and backend is actually is deployed is unfortunatley without docker, but theres nothing we can do about that currently due to our ISP...

Check out this [video](https://www.youtube.com/watch?v=Gjnup-PuquQ&ab_channel=Fireship) to learn more
