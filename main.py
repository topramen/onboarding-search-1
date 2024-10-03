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
        
        # Get YouTube titles for each video ID
        from youtube_utils import get_youtube_title
        video_info = [(video_id, get_youtube_title(video_id)) for video_id in video_ids]
        
        return video_info
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
    st.title("Youtube Video Insert and Select")

    # List unique videos
    index_name = os.environ.get("ELASTICSEARCH_INDEX")
    unique_videos = get_unique_video_ids(es_client, index_name)
    if unique_videos:
        selected_video = st.selectbox("Select Video", unique_videos, format_func=lambda x: f"{x[1]} ({x[0]})")
        selected_video_id = selected_video[0]
    else:
        st.warning("No videos found.")
        selected_video_id = None




# RIGHT PANEL
st.title("Search in Selected Video")

# Query input field
query = st.text_input("Enter your search query:")

# Search button
if st.button("Search") and query and selected_video_id:
    with st.spinner("Searching..."):
        st.subheader(f"Results for Video: {selected_video[1]}")
        
        # Use the search_elasticsearch function to query Elasticsearch
        results = search_elasticsearch(query=query, video_id=selected_video_id)
        
        if results:
            st.markdown(f"**Total Results:** {results['hits']['total']['value']}")
            for hit in results['hits']['hits']:
                source = hit['_source']
                st.write(f"Start Time: {source['start_time']:.2f}")
                st.write(f"Text: {source['text']}")
                st.write("---")
        else:
            st.write("No results found for this video.")



