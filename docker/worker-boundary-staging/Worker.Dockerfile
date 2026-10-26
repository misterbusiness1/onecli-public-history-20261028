FROM python:3.12-slim-bookworm
RUN useradd --uid 1000 --create-home worker
COPY onecli /usr/local/bin/onecli
COPY relay.py worker.py run.py /opt/isolation/
USER 1000:1000
WORKDIR /workspace
ENV HOME=/home/worker
ENTRYPOINT ["python3", "/opt/isolation/worker.py"]
