import os


def main(build):
    if build:
        os.system('docker-compose up --build')
    else:
        os.system('docker-compose up --no-recreate')


if __name__ == '__main__':
    main(False)  # True False
