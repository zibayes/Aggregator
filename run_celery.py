import os


def main():
    os.system('celery -A archeology worker --loglevel=info -P eventlet')


if __name__ == '__main__':
    main()
