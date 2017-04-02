from setuptools import setup

__version__ = (0, 1, 0)
__versionstr__ = '.'.join(str(i) for i in __version__)

with open('readme.md', 'U') as description_file:
    long_description = description_file.read()

with open('requirements.txt', 'U') as reqs_file:
    install_requires = reqs_file.read().splitlines()

setup(
    name='migrates',
    description='Migration tool for Elasticsearch.',
    license='GNU General Public License v3.0',
    url='https://github.com/pineapplemachine/migrates/',
    long_description=long_description,
    version=__versionstr__,
    author="Sophie Kirschner",
    author_email='sophiek@pineapplemachine.com',
    packages=['migrates'],
    install_requires=install_requires
)
