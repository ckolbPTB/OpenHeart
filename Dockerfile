FROM python:3.8.13-slim

# Install requirements
RUN mkdir /openheart
WORKDIR /openheart
ADD requirements.txt /openheart/
RUN pip install -r requirements.txt

# Add code
ADD . /openheart/

# Make port 80 available to the world outside this container
EXPOSE 80

# Define environment variable
# ENV NAME World

# Run app.py when the container launches
CMD ["python", "app.py"]