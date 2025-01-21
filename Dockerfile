# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY app/requirements.txt /app/

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the app directory contents into the container at /app
COPY app /app

# Make port 3000 available to the world outside this container
EXPOSE 3000

# Define environment variable
ENV MODULE_NAME=server
ENV VARIABLE_NAME=app
ENV PORT=3000

# Run server.py when the container launches
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "3000"]