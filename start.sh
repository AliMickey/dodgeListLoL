#!/bin/bash
docker build -t dodgelistlol .
docker run -d -p 8001:80 --name=dodgelistlol --restart unless-stopped -v $PWD:/app -v $PWD/instance/dodgeListLoL.sqlite:/app/instance/dodgeListLoL.sqlite dodgelistlol