from elasticsearch import Elasticsearch
import cohere
from dotenv import load_dotenv
import os

load_dotenv()

# Initialize Elasticsearch client
client = Elasticsearch(
    os.getenv('ELASTIC_ENDPOINT'),
    api_key=os.getenv('ELASTIC_API_KEY')
)

# Initialize Cohere client
cohere_client = cohere.Client(os.getenv("COHERE_API_KEY"))


# Create an inference endpoint for reranking
client.inference.put_model(
    task_type="rerank",
    inference_id="cohere_rerank",
    body={
        "service": "cohere",
        "service_settings": {
            "api_key": os.getenv("COHERE_API_KEY"),
            "model_id": "rerank-english-v3.0"
        },
        "task_settings": {
            "top_n": 10
        }
    }
)