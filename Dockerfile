FROM python:latest

# install python and pip modules
RUN python3 -m pip install --upgrade pip
COPY requirements.txt requirements.txt
RUN python3 -m pip install -r requirements.txt

# define the working directory
COPY server server
WORKDIR /server

# copy our files into the container
ENTRYPOINT python3 server.py
