from setuptools import setup


setup(
    name='transip-stack-api',
    version='1.0.2',
    install_requires=[
        'bs4>=0.0.1',
        'lxml>=3.8.0',
        'requests>=2.18.2',
        'webdavclient>=1.0.8',
        'pycurl==7.43.0'
    ],
    url='https://github.com/Paradoxis/TransIP-STACK-API',
    license='MIT',
    author='Paradoxis',
    author_email='luke@paradoxis.nl',
    description='Unofficial wrapper for the TransIP STACK API',
    keywords=['TransIP', 'STACK', 'Storage'],
    download_url='https://codeload.github.com/Paradoxis/TransIP-STACK-API/tar.gz/master')
