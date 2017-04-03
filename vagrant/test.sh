cd /migrates/migrates

eval "$(pyenv init -)"

pyenv shell 2.7.13
pip install elasticsearch==1.7.0 | sudo tee "setup-es-py.log"
pyenv shell 3.6.1
pip install elasticsearch==1.7.0 | sudo tee "setup-es-py.log"

echo "  Testing with Elasticsearch 1.7.2..."
sudo dpkg -i elasticsearch-1.7.2.deb | sudo tee "setup-es.log"
sudo /etc/init.d/elasticsearch start | sudo tee "setup-es.log"
sleep 12  # Wait for ES to become available
echo "    Testing with Python 2.7.13..."
pyenv shell 2.7.13
python 'test/__main__.py'
echo "    Testing with Python 3.6.1..."
pyenv shell 3.6.1
python 'test/__main__.py'
sudo /etc/init.d/elasticsearch stop | sudo tee "setup-es.log"

echo "  Testing with Elasticsearch 2.4.2..."
sudo dpkg -i elasticsearch-2.4.2.deb | sudo tee "setup-es.log"
sudo /etc/init.d/elasticsearch start | sudo tee "setup-es.log"
sleep 15  # Wait for ES to become available
echo "    Testing with Python 2.7.13..."
pyenv shell 2.7.13
python 'test/__main__.py'
echo "    Testing with Python 3.6.1..."
pyenv shell 3.6.1
python 'test/__main__.py'
sudo /etc/init.d/elasticsearch stop | sudo tee "setup-es.log"

echo "  Testing with Elasticsearch 5.3.0..."
sudo dpkg -i elasticsearch-5.3.0.deb | sudo tee "setup-es.log"
sudo /etc/init.d/elasticsearch start | sudo tee "setup-es.log"
sleep 15  # Wait for ES to become available
echo "    Testing with Python 2.7.13..."
pyenv shell 2.7.13
echo "      Testing with elasticsearch-py 1.7.0..."
python 'test/__main__.py'
echo "      Testing with elasticsearch-py 5.3.0..."
pip install elasticsearch==5.3.0 | sudo tee "setup-es-py.log"
python 'test/__main__.py'
echo "    Testing with Python 3.6.1..."
pyenv shell 3.6.1
echo "      Testing with elasticsearch-py 1.7.0..."
python 'test/__main__.py'
echo "      Testing with elasticsearch-py 5.3.0..."
pip install elasticsearch==5.3.0 | sudo tee "setup-es-py.log"
python 'test/__main__.py'
sudo /etc/init.d/elasticsearch stop | sudo tee "setup-es.log"

echo "All done running tests!"
