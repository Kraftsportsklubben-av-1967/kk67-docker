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

1. Clone the repo

```sh
$ git clone git@github.com:Kraftsportsklubben-av-1967/kk67-docker.git
```

2. Create a `webroot` folder

3. Clone the above repositories into `./webroot` and follow their guides to set them up with docker-compose

4. Build the compose `docker-compose up --build`

> After this is done you can simply use `docker-compose up`

1. The services will be running:
   1. Backend: `http://localhost:4000`
   2. Frontend: `http://localhost:3000`

> Additional outputs will be displayed in your terminal. Remember to close this once you're done.

## Why docker-compose?

Using docker-compose allows us to use virtual machines to load all dependencies and development environment without interfering with our own personal setup. It recreates an identical environment for everyone using the `docker-compose.yml` config file. As for members of KK, this repository is mainly ment for development purposes. How the frontend and backend is actually is deployed is unfortunatley without docker, but theres nothing we can do about that currently due to our ISP...

Check out this [video](https://www.youtube.com/watch?v=Gjnup-PuquQ&ab_channel=Fireship) to learn more
