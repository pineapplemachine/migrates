from setuptools import setup

__version__ = (0, 1, 0)
__versionstr__ = '.'.join(str(i) for i in __version__)

with open('README', 'rb') as description_file:
    long_description = description_file.read()

with open('requirements.txt', 'rb') as reqs_file:
    install_requires = reqs_file.read().split('\n')

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
