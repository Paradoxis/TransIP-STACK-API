from distutils.core import setup
from pip.req import parse_requirements
from pip.download import PipSession


setup(
    name='transip-stack-api',
    version='1.0.1',
    install_requires=list(str(line.name) for line in parse_requirements("requirements.txt", session=PipSession())),
    url='https://github.com/Paradoxis/TransIP-STACK-API',
    license='MIT',
    author='Paradoxis',
    author_email='luke@paradoxis.nl',
    description='Unofficial wrapper for the TransIP STACK API',
    keywords=['TransIP', 'STACK', 'Storage'],
    download_url='https://codeload.github.com/Paradoxis/TransIP-STACK-API/tar.gz/master',
)
