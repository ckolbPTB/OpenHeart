FROM python:3.8

ENV http_proxy "http://webproxy.berlin.ptb.de:8080"
ENV https_proxy "http://webproxy.berlin.ptb.de:8080"

COPY . /app
WORKDIR /app

RUN pip install -r requirements.txt
RUN pip install -e .

ENV FLASK_APP "openheart"
env FLASK_DEBUG "1"

CMD ["python3", "-m", "flask", "init-db", ]
CMD ["python3", "-m", "flask", "run", "--host=0.0.0.0", "--port=5001"]
