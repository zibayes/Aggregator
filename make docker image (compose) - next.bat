set COMPOSE_BAKE=true
set DOCKER_BUILDKIT=1
set COMPOSE_DOCKER_CLI_BUILD=1
docker-compose build --parallel --progress=plain
pause