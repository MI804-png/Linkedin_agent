# Docker Tutorial – Apache2 Web Service

## 1. What is Docker?

Docker is a platform that packages applications and their dependencies into containers.
Containers are lightweight, portable, and ensure consistency across different environments.

### Benefits of Docker:
- **Portability**
- **Isolation**
- **Scalability**
- **Faster deployment**

---

## 2. Creating a Dockerfile for Apache2

### Directory structure:
```
myapp/
├── Dockerfile
└── index.html
```

### Contents of `index.html`:
```html
<!DOCTYPE html>
<html>
<head>
    <title>Welcome to Apache2 in Docker</title>
</head>
<body>
    <h1>Hello from Dockerized Apache2!</h1>
</body>
</html>
```

### Contents of `Dockerfile`:
```dockerfile
FROM ubuntu
RUN apt update && apt upgrade -y && apt install apache2 -y
WORKDIR /srv/myapp
COPY ./index.html /var/www/html/index.html
ENTRYPOINT ["apachectl", "-D", "FOREGROUND"]
```

---

## 3. Building and Running the Docker Image

### Build the image:
```bash
docker build -t myapp .
```

### Run the container:
```bash
docker run -d -p 80:80 myapp
```

Visit the cloud instance IP in your browser to see the page.

---

## 4. Pushing to Docker Hub (Not required)

### Step 1: Login to Docker Hub
```bash
docker login
```

### Step 2: Tag the image
```bash
docker tag myapp username/myapp:latest
```

### Step 3: Push the image
```bash
docker push username/myapp:latest
```

### Step 4: Pull the image on another machine
```bash
docker pull username/myapp:latest
docker run -d -p 80:80 username/myapp:latest
```

---

## Notes:
- The `-d` flag runs the container in detached mode (background)
- The `-p 80:80` flag maps port 80 from the container to port 80 on the host
- Make sure Docker is installed and running on your system
- You may need sudo privileges depending on your Docker installation
