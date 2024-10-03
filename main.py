import streamlit as st
import os
from elasticsearch import Elasticsearch, AsyncElasticsearch
# from utils import get_current_time, count_words_in_conversation
# from streamlit_components.es import save_conversation, load_conversation, get_elasticsearch_results, create_RAG_context, get_valid_indices
# from settings import valid_index_list
from dotenv import load_dotenv
import json
from datetime import datetime
load_dotenv()

def set_page_container_style():
    st.markdown(
        f"""
        <style>
            .sidebar .sidebar-content {{
                position: fixed;
                overflow-y: auto;
                height: 100vh;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_unique_video_ids(es_client, index_name):
    es = AsyncElasticsearch(
        os.getenv('ELASTIC_ENDPOINT'),
        api_key=os.getenv('ELASTIC_API_KEY')
    )    
    index_name = os.environ.get("ELASTICSEARCH_INDEX")

    try:
        response = es_client.search(
            index=index_name,
            body={
                "size": 0,
                "aggs": {
                    "unique_video_ids": {
                    "terms": {
                        "field": "video_id",
                        "size": 10000
                    }
                    }
                }
            }
        )
        video_ids = [bucket['key'] for bucket in response['aggregations']['unique_video_ids']['buckets']]
        return video_ids
    except Exception as e:
        st.error(f"Error fetching unique video IDs: {str(e)}")
        return []    
    

def search_elasticsearch(video_id, query):
    es = Elasticsearch(
        os.getenv('ELASTIC_ENDPOINT'),
        api_key=os.getenv('ELASTIC_API_KEY')
    )
    index_name = os.environ.get("ELASTICSEARCH_INDEX")
   
    search_body = {
        "query": {
            "bool": {
                "must": {
                    "nested": {
                        "path": "text_semantic.inference.chunks",
                        "query": {
                            "sparse_vector": {
                                "inference_id": "my-elser-endpoint",
                                "field": "text_semantic.inference.chunks.embeddings",
                                "query": query
                            }
                        },
                        "inner_hits": {
                            "size": 2,
                            "name": "youtube_subtitles.text_semantic",
                            "_source": [
                                "text_semantic.inference.chunks.text"
                            ]
                        }
                    }
                },
                "filter": {
                    "term": {
                        "video_id": video_id
                    }
                }
            }
        } 
    }
    
    try:
        response =  es.search(index=index_name, body=search_body)
        # es.close()
        return response
    except Exception as e:
        print(f"Error searching Elasticsearch: {str(e)}")
        # es.close()
        return None


try:
    # Elasticsearch setup
    es_endpoint = os.environ.get("ELASTIC_ENDPOINT")
    es_client = Elasticsearch(
        es_endpoint,
        api_key=os.environ.get("ELASTIC_API_KEY")
    )
except Exception as e:
    es_client=None

st.set_page_config(layout="wide")
set_page_container_style()


selected_indices=[]

# LEFT SIDEBAR
with st.sidebar:
    # st.title("Cluster Status")
    # es_connected=False
    # # TRY TO DISPLAY ERROR MESSAGE IF CONNECTION FAILS
    # try:
    #     es_connected = es_client.ping()
    #     es_health = es_client.cluster.health()
    # except Exception as e: 
    #     es_health='FAILURE'
    # st.markdown(f"**Cluster Endpoint:** {es_endpoint}")
    # if es_connected:
    #     st.markdown('<p style="background-color:#CCFFCC; color:#007700; padding:10px; border-radius:5px;"><strong>Connected to Elasticsearch Cluster</strong></p>', unsafe_allow_html=True)
    # else:
    #     st.markdown('<p style="background-color:#FFCCCC; color:#CC0000; padding:10px; border-radius:5px;"><strong>Failed to connect to Elasticsearch Cluster</strong></p>', unsafe_allow_html=True)
    # Elastic Search Components
    # save_conversation(es_client, get_current_time)
    # load_conversation(es_client)

    # List unique video IDs
    st.title("Unique Videos")
    index_name = os.environ.get("ELASTICSEARCH_INDEX")
    unique_video_ids = get_unique_video_ids(es_client, index_name)
    if unique_video_ids:
        selected_video_id = st.selectbox("Select Video ID", unique_video_ids)
    else:
        st.warning("No video IDs found.")




# RIGHT PANEL
st.title("Video Search")

# Query input field
query = st.text_input("Enter your search query:")

# Search button
if st.button("Search") and query and selected_video_ids:
    with st.spinner("Searching..."):
        for video_id in selected_video_ids:
            st.subheader(f"Results for Video ID: {video_id}")
            
            # Use the search_elasticsearch function to query Elasticsearch
            results = search_elasticsearch(query=query, video_id=video_id)
            
            # st.markdown(f"**Total Results:** {results.hits})

            if results:
                for hit in results['hits']['hits']:
                    source = hit['_source']
                    st.write(f"Start Time: {source['start_time']:.2f}")
                    st.write(f"Text: {source['text']}")
                    st.write("---")
            else:
                st.write("No results found for this video.")



