from setuptools import setup, find_packages

with open('README.md', 'r') as stream:
    long_description = stream.read()

setup(
    name='Amsync',
    version='0.0.4',
    url='https://github.com/ellandor/Amsync',
    license='MIT',
    author='SempreLegit',
    description='An async library to easily create bots for the amino.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    keywords=[
        'aminoapps',
        'amino-py',
        'amino',
        'amino-bot',
        'narvii',
        'api',
        'python',
        'python3',
        'python3.x',
        'amino-async',
    ],
    install_requires=[
        'aiohttp',
        'aiofiles',
        'ujson',
        'pybase64',
        'peewee',
        'python-dotenv',
    ],
    setup_requires=['wheel'],
    classifiers=[
        'Development Status :: 1 - Planning',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.8',
    ],
    packages=find_packages(),
)
