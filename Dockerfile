FROM python:3.6
COPY requirements.txt /tmp
RUN pip install -U setuptools
RUN pip install -r /tmp/requirements.txt
RUN mkdir -p /weather_app
COPY ./weather_app.py /weather_app
WORKDIR /weather_app
EXPOSE 8080
CMD ["python", "weather_app.py"]
