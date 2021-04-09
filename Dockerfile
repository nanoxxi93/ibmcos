FROM python:3.8-slim-buster
WORKDIR /app
COPY requirements.txt requirements.txt
RUN apt-get update \
&& apt-get install -y --no-install-recommends build-essential gcc g++ \
&& rm -rf /var/lib/apt/lists/* \
&& pip3 install -r requirements.txt \
&& apt-get purge -y --auto-remove build-essential gcc g++
COPY . .
CMD [ "waitress-serve", "app:app"]