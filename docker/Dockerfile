FROM python:3.8-alpine

COPY requirements.txt /opt

WORKDIR /opt

RUN pip install --no-cache-dir -r requirements.txt

COPY . /opt

ENTRYPOINT ["python3", "-u", "virtualDron_anomaly.py"]