FROM python:3.13.2

# set workdir
WORKDIR /app

# install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy app code
COPY . .

# expose port
EXPOSE 3333

CMD ["flask", "run", "--host=0.0.0.0"]