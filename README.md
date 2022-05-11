# KK-67 Docker

KK-67 website uses the following services:

- [KK-67 Frontend](https://github.com/Kraftsportsklubben-av-1967/kk67-frontend)
- [KK-67 Backend](https://github.com/Kraftsportsklubben-av-1967/kk67-backend)


## Prerequesits 

You will need docker-compose to be able to use this repository 

0. https://docs.docker.com/compose/install/


## Setup

1. Create a `webroot` folder

2. Clone the above repositories into `./webroot`

3. Run `docker-compose up`

4. The services will be running:
   1. KK BE: `http://localhost:5000`
   2. KK FE: `http://localhost:3000`
