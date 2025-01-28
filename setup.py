from setuptools import setup, find_packages

setup(
    name="my_project",  # Имя вашего пакета
    version="0.1",  # Версия вашего пакета
    packages=find_packages(),  # Находит все пакеты в проекте
    install_requires=[],  # Зависимости вашего проекта
    entry_points={
        'console_scripts': [
            'my_command=my_package.main:main',  # Команда для запуска
        ],
    },
    author="Ваше Имя",
    author_email="ваш_email@example.com",
    description="Краткое описание вашего проекта",
    long_description=open('README.md').read(),  # Длинное описание из README
    long_description_content_type='text/markdown',
    url="https://github.com/zibayes/Aggregator",  # URL вашего проекта
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',  # Минимальная версия Python
)