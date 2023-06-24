FROM python:3.9

COPY requirements.txt /opt

WORKDIR /opt

RUN pip install --no-cache-dir -r requirements.txt

COPY . /opt

ENTRYPOINT ["python3", "-u", "virtualDron.py"]