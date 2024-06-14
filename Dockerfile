# Use the official Python image
FROM python:3.11

# Set the working directory
WORKDIR /app

# Copy the local directory contents into the container at /app
COPY . /app

# Install dependencies
RUN pip3 install --upgrade pip && pip3 install -r requirements.txt

# Set the default command to run the application
CMD ["sh", "run.sh"]
