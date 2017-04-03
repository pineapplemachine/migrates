export PROFILE='/home/vagrant/.bash_profile'

echo 'export PYENV_ROOT="/home/vagrant/.pyenv"' >> $PROFILE
echo 'export ES_HEAP_SIZE=2g' >> $PROFILE
source $PROFILE

# Install dependencies
echo "Installing dependencies..."
apt-get update >> 'setup-deps.log'
apt-get install git -y --fix-missing >> 'setup-deps.log'
apt-get install libbz2-dev libssl-dev libreadline-dev -y --fix-missing >> 'setup-deps.log'
apt-get install libsqlite3-dev tk-dev -y --fix-missing >> 'setup-deps.log'

# Create a working directory
mkdir /migrates
chown vagrant /migrates
cd /migrates

# Clone migrates repo
echo "Cloning migrates git repository..."
git clone https://github.com/pineapplemachine/migrates.git migrates >> 'setup-migrates.log'
chown vagrant migrates
chown vagrant migrates/migrates
echo 'alias migrates="python -m migrates.__main__"' >> $PROFILE
cd migrates

# Install and start Elasticsearch
echo "Installing Java 7..."
apt-get install openjdk-7-jre-headless -y --fix-missing >> 'setup-java.log'

echo "Installing Java 8..."
apt-get install python-software-properties debconf-utils -y >> 'setup-java.log'
apt-add-repository ppa:webupd8team/java -y >> 'setup-java.log'
apt-get update >> 'setup-java.log'
# Bypass installation dialog http://askubuntu.com/a/190674
echo debconf shared/accepted-oracle-license-v1-1 select true | sudo debconf-set-selections
echo debconf shared/accepted-oracle-license-v1-1 seen true | sudo debconf-set-selections
apt-get install oracle-java8-installer -y &>> 'setup-java.log'

echo "Downloading Elasticsearch 1.7.2..."
wget https://download.elasticsearch.org/elasticsearch/elasticsearch/elasticsearch-1.7.2.deb &>> 'setup-es.log'
echo "Downloading Elasticsearch 2.4.2..."
wget https://download.elasticsearch.org/elasticsearch/elasticsearch/elasticsearch-2.4.2.deb &>> 'setup-es.log'
echo "Downloading Elasticsearch 5.3.0..."
wget https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-5.3.0.deb &>> 'setup-es.log'

# https://github.com/pyenv/pyenv-installer#installation--update--uninstallation
echo "Installing pyenv..."
curl -L https://raw.githubusercontent.com/pyenv/pyenv-installer/master/bin/pyenv-installer | bash >> 'setup-pyenv.log'
echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> $PROFILE
echo 'eval "$(pyenv init -)"' >> $PROFILE
echo 'eval "$(pyenv virtualenv-init -)"' >> $PROFILE
source $PROFILE
eval "$(pyenv init -)"

echo "Installing Python 2.7.13..."
pyenv install 2.7.13 >> 'setup-python-27.log'
pyenv shell 2.7.13 >> 'setup-python-27.log'
pip install /migrates/migrates
echo "Installing Python 3.6.1..."
pyenv install 3.6.1 >> 'setup-python-36.log'
pyenv shell 3.6.1 >> 'setup-python-36.log'
pip install /migrates/migrates

sudo chown vagrant /home/vagrant/ -R
