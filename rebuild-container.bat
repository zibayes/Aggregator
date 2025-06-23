docker build -t archeology-app -f Dockerfile  .

echo Delete old container...
docker rm -f archeology

echo Run new container...
docker run -d -p 5000:5000 --name archeology archeology-app
pause