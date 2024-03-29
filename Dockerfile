FROM python:3.11.4-bookworm as build

RUN apt-get update && apt-get install --assume-yes \
    gcc \
    curl \
    python3 \
    python3-dev \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/rasp-shutter

RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

COPY pyproject.toml .

RUN poetry config virtualenvs.create false \
 && poetry install \
 && rm -rf ~/.cache

FROM python:3.11.4-slim-bookworm as prod

ARG IMAGE_BUILD_DATE

ENV TZ=Asia/Tokyo
ENV IMAGE_BUILD_DATE=${IMAGE_BUILD_DATE}

COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

WORKDIR /opt/rasp-shutter

COPY . .

EXPOSE 5000

CMD ["./flask/app/app.py", "-d"]
