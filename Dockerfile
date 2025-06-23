FROM python:3.13.2-alpine

WORKDIR /app

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 3333

CMD ["flask", "run", "--host=0.0.0.0"]