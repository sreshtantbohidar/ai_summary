

# #prod pg password ----
# # PG_PASSWORD = 'postgres'


# #prod pg hostname ----
# # PG_HOSTNAME='192.168.0.122' 

# USERNAME="fatadmin"
# PASSWORD="fatadmin"
# DJANGO_PORT=8000
# DJANGO_HOST = "192.168.1.127"

# #dev pg hostname ----
# PG_HOSTNAME='192.168.1.127'
# PG_PORT = 5432
# PG_DB_NAME = 'fatboy_dev_db_latest'
# # PG_PASSWORD = 'TeCtUmFaTbOy%40321'
# PG_PASSWORD = "TeCtUmFaTbOy321"
# PG_USER = 'postgres'

# #~~~~~~~~~~~~~~~~~~~~~~~~
# CHILD_RELATIONSHIP_ID=7
# PARENT_RELATIONSHIP_ID=6
# ROAD_RELATIONSHIP_ID=11


# #~~~~~~~~~~~~~~~~~~~Activities IDs~~~~~~~~~~form_activities(table_name)~~~~~~~~~~
# DEPLOYMENT_ACTIVITY=386
# EQUIPMENT_ACTIVITY=378
# INFRA_ACTIVITY_ID=382
# PATROLLING_ACTIVITY_ID=390

# #prod sftp username ----
# # SFTP_USERNAME = 'ubuntu'
# #dev sftp username ----
# #~~~~~~~~~~~~~~~~~~~~~~SFTP config~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# SFTP_HOST = '192.168.1.127'
# SFTP_PORT = 22
# SFTP_USERNAME = 'app'
# SFTP_PASSWORD = 'MrServer@234$'
# SFTP_BASE_PATH='/home/app/Documents/fatboy/fatboy/ftpserver'
# SFTP_PRIVATE_KEY="/app/ssh/id_ed25519"
# USER_ID=1
# TELECOM_CONFIG_FILE = 'database.config'
# #prod http file path ----
# # HTTP_FILE_PATH = 'http://192.168.0.122:9000'
# #prod elastic address ----
# # ELASTIC_ADDRESS = "http://192.168.0.128:9200"



# #~~~~~~~~~~~~~~~~~~Elastic config~~~~~~~~~~~~~~~~~~~~~~~~~

# #dev http file path ----
# HTTP_FILE_PATH = 'http://192.168.1.127:9000'
# #dev elastic address ----
# ELASTIC_ADDRESS ='http://192.168.1.16:9200'
# ELASTIC_USER = 'elastic'
# ELASTIC_PASSWD = 'uHMkl_b8DuAskF2E1h5x'
# ELASTIC_API_DATAVIEW="http://192.168.1.174:5601/api/data_views/data_view"


# ELASTIC_HOST = '192.168.1.16'
# ELASTIC_PORT = 9200
# ELASTIC_CLIENT_SCHEME = "http"
# KIBANA_HOST='http://192.168.1.174:5601'
# CUREENT_INDEX_NAME="fatboy_ifc"
# CURRENT_INDEX_NAME="fatboy_ifc"
# NOMIONATIM_SEARCH_BASE_URL = "http://192.168.1.170/nominatim/search.php"

# #~~~~~~~~~~~~~~~~~~~~~~LLM IP~~~~~~~~~~~~~~~~~~~~~~
# LLM_IP='192.168.1.125'
# LLM_PORT=11434
# IFC_LLM_PORT=3001
# LLM_MODEL="gemma2:9b-instruct-q8_0"
# SMALL_LLM_MODEL="gemma2:9b-instruct-q8_0"
# KEY="YHEZW6Z-9CPMHWX-GWYR3VF-8GYF582"
# IFC_LLM_TOKEN='Y7GFVMX-PS94J8V-NJ6PZN6-GAE41MX'
# IFS_WORKSPCE_URL="http://192.168.1.125:3001"
# Fusion_Analysis_Workspace="Fusion Analysis"

# #~~~~~~~~~~~~~~~~~~~Postgre And Elastic Connection~~~~~~~~~~
# import psycopg2
# from elasticsearch import Elasticsearch

# BASE_URL = f'http://{DJANGO_HOST}:{DJANGO_PORT}'
# es = Elasticsearch([{'host': ELASTIC_HOST, 'port': ELASTIC_PORT, 'scheme': 'http'}])
# def postgres_connection():
#     try:
#         conn = psycopg2.connect(
#             database=PG_DB_NAME,
#             host=PG_HOSTNAME,
#             user=PG_USER,
#             password=PG_PASSWORD,
#             port=PG_PORT,
#         )
#         return conn
#     except psycopg2.Error as e:
#         print(f"Error connecting to PostgreSQL: {e}")
#         return None





USERNAME="fatadmin"
PASSWORD="fatadmin"
DJANGO_PORT=8000
DJANGO_HOST = "192.168.1.125"

#dev pg hostname ----
PG_HOSTNAME='192.168.1.125'
PG_PORT = 5432
PG_DB_NAME = 'isquare'
# PG_PASSWORD = 'TeCtUmFaTbOy%40321'
PG_PASSWORD = "TeCtUmFaTbOy321"
PG_USER = 'postgres'
SECRET_KEY_DECRYPT="edftugcka"
#~~~~~~~~~~~~~~~~~~~~~~~~
CHILD_RELATIONSHIP_ID=7
PARENT_RELATIONSHIP_ID=6
ROAD_RELATIONSHIP_ID=11


#~~~~~~~~~~~~~~~~~~~Activities IDs~~~~~~~~~~form_activities(table_name)~~~~~~~~~~
DEPLOYMENT_ACTIVITY=386
EQUIPMENT_ACTIVITY=378
INFRA_ACTIVITY_ID=382
PATROLLING_ACTIVITY_ID=390

#prod sftp username ----
# SFTP_USERNAME = 'ubuntu'
#dev sftp username ----
#~~~~~~~~~~~~~~~~~~~~~~SFTP config~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
SFTP_HOST = '192.168.1.125'
SFTP_PORT = 22
SFTP_USERNAME = 'demo'
SFTP_PASSWORD = 'Tec#2309@Tum'
SFTP_BASE_PATH="/home/demo/Documents/fatboy/fatboy/ftpserver/" #'/app/ftpserver' 
USER_ID=1
TELECOM_CONFIG_FILE = 'database.config'
#prod http file path ----
# HTTP_FILE_PATH = 'http://192.168.0.122:9000'
#prod elastic address ----
# ELASTIC_ADDRESS = "http://192.168.0.128:9200"



#~~~~~~~~~~~~~~~~~~Elastic config~~~~~~~~~~~~~~~~~~~~~~~~~

#dev http file path ----
HTTP_FILE_PATH = 'https://192.168.1.125:9000'
#dev elastic address ----
ELASTIC_ADDRESS ='https://192.168.1.125:9200'
ELASTIC_USER = 'elastic'
ELASTIC_PASSWD='30oIsFcjJa8Zao+iq5*e'
ELASTIC_API_DATAVIEW="https://192.168.1.125:5601/api/data_views/data_view"


ELASTIC_HOST = '192.168.1.125'
ELASTIC_PORT = 9200
ELASTIC_CLIENT_SCHEME = "https"
KIBANA_HOST='https://192.168.1.125:5601'
CUREENT_INDEX_NAME="fatboy_data"
CURRENT_INDEX_NAME="fatboy_data"
NOMIONATIM_SEARCH_BASE_URL = "http://192.168.1.170/nominatim/search.php"

#~~~~~~~~~~~~~~~~~~~~~~LLM IP~~~~~~~~~~~~~~~~~~~~~~
LLM_IP='192.168.1.125'
LLM_PORT=11434
IFC_LLM_PORT=3001
LLM_MODEL="llama3:8b-instruct-q8_0"
KEY="YHEZW6Z-9CPMHWX-GWYR3VF-8GYF582"
SMALL_LLM_MODEL="llama3:8b-instruct-q8_0"
ELASTICSEARCH_USERNAME = 'elastic'
ELASTICSEARCH_PASSWORD = '30oIsFcjJa8Zao+iq5*e'
ai_slave_host = '127.0.0.1'
ai_slave_port = '5001'
ollama_api_host = '192.168.1.125'
ollama_api_port = 11434

SFTP_PRIVATE_KEY="/root/.ssh/id_ed25519"



#~~~~~~~~~~~~~~~~~~LOgger~~~~~~~~~~~~~~~~~

import logging
import functools
import os

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(f"{LOG_DIR}/app.log"),
        logging.StreamHandler()
    ]
)




logger = logging.getLogger(__name__)
def log_function(func):
    """
    Logs function start, end, and full traceback on error.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger.info(f"STARTED: {func.__name__}")
        try:
            result = func(*args, **kwargs)
            logger.info(f"ENDED: {func.__name__}")
            return result
        except Exception:
            logger.error(
                f"ERROR in {func.__name__}",
                exc_info=True
            )
            raise
    return wrapper


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~Client Connebction~~~~~~~~~~~~~~~~~~~~~~~~~~~~

BASE_URL = f'https://{DJANGO_HOST}:{DJANGO_PORT}'

try:
    import psycopg2
except ImportError:
    psycopg2 = None
try:
    from elasticsearch import Elasticsearch
except ImportError:
    Elasticsearch = None
import requests
def postgres_connection():
    if psycopg2 is None:
        return None
    try:
        conn = psycopg2.connect(
            database=PG_DB_NAME,
            host=PG_HOSTNAME,
            user=PG_USER,
            password=PG_PASSWORD,
            port=PG_PORT,
        )
        return conn
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        logger.critical("Connection error", exc_info=True)
        return None


es = None
if Elasticsearch is not None:
    es = Elasticsearch(
        [{"host": ELASTIC_HOST, "port": ELASTIC_PORT, "scheme": ELASTIC_CLIENT_SCHEME}],
        basic_auth=(ELASTICSEARCH_USERNAME, ELASTICSEARCH_PASSWORD),
        verify_certs=False,
        ssl_show_warn=False
    )






IFS_WORKSPCE_URL="http://192.168.1.125:3001"
Fusion_Analysis_Workspace="Fusion Analysis"
IFC_LLM_TOKEN='Y7GFVMX-PS94J8V-NJ6PZN6-GAE41MX'


TRANSCRIBE_BASE_URL = "http://192.168.1.125:5060"