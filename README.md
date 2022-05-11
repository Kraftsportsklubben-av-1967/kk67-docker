# KK-67 Docker

![Docker](https://img.shields.io/badge/Docker-2CA5E0?style=for-the-badge&logo=docker&logoColor=white)
![Node](https://img.shields.io/badge/Node.js-339933?style=for-the-badge&logo=nodedotjs&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)

KK-67 website uses the following services:

- [KK-67 Frontend](https://github.com/Kraftsportsklubben-av-1967/kk67-frontend)
- [KK-67 Backend](https://github.com/Kraftsportsklubben-av-1967/kk67-backend)

1. Create a `webroot` folder

2. Clone the above repositories into `./webroot`

3. Build the compose `docker-compose up --build`

> After this is done you can simply use `docker-compose up`

1. The services will be running:
   1. KK BE: `http://localhost:5000`
   2. KK FE: `http://localhost:3000`

> Additional outputs will be displayed in your terminal. Remember to close this once you're done.

## Why docker-compose?

Using docker-compose allows us to use virtual machines to load all dependencies and development environment without interfering with our own personal setup. It recreates an identical environment for everyone using the `docker-compose.yml` config file.

Check out this [video](https://www.youtube.com/watch?v=Gjnup-PuquQ&ab_channel=Fireship) to learn more
