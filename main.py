import streamlit as st
import os
from elasticsearch import Elasticsearch, AsyncElasticsearch
# from utils import get_current_time, count_words_in_conversation
# from streamlit_components.es import save_conversation, load_conversation, get_elasticsearch_results, create_RAG_context, get_valid_indices
# from settings import valid_index_list
from dotenv import load_dotenv
from youtube_utils import get_youtube_title, chunk_youtube_video, get_video_id
import json


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
        video_info = [(video_id, get_youtube_title(video_id)) for video_id in video_ids]
        
        return video_info
    except Exception as e:
        st.error(f"Error fetching unique video IDs: {str(e)}")
        return []    
 
def ingest_video_subtitles(video_id):
    es = Elasticsearch(
        os.getenv('ELASTIC_ENDPOINT'),
        api_key=os.getenv('ELASTIC_API_KEY')
    )
    index_name = os.environ.get("ELASTICSEARCH_INDEX")
    file_name = f"{video_id}.ndjson"

    try:
        with open(file_name, 'r') as file:
            for line in file:
                subtitle = json.loads(line)
                # Add the document to Elasticsearch
                es.index(index=index_name, body=subtitle)
        
        print(f"Successfully ingested subtitles for video {video_id} into Elasticsearch.")
    except FileNotFoundError:
        print(f"File {file_name} not found.")
    except json.JSONDecodeError:
        print(f"Error decoding JSON in {file_name}.")
    except Exception as e:
        print(f"Error ingesting subtitles into Elasticsearch: {str(e)}")
    finally:
        es.close()

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
        },
        "_source": ["start_time", "text"],  # Include the fields we want to return
        "track_scores": True  # This ensures that scores are tracked and returned
    }
    
    try:
        response = es.search(index=index_name, body=search_body)
        return response
    except Exception as e:
        print(f"Error searching Elasticsearch: {str(e)}")
        return None


def rerank_elasticsearch(video_id, query):
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
        },
        "_source": ["start_time", "text"],
        "track_scores": True,
        "rescore": {
            "window_size": 50,
            "query": {
                "rescore_query": {
                    "inference": {
                        "model_id": "cross-encoder__ms-marco-minilm-l-6-v2",
                        "inference_config": {
                            "cross_encoder": {
                                "query": query
                            }
                        },
                        "input_field": "text",
                        "target_field": "reranked_score"
                    }
                },
                "score_mode": "total",
                "query_weight": 0.3,
                "rescore_query_weight": 0.7
            }
        }
    }
    
    try:
        response = es.search(index=index_name, body=search_body)
        return response
    except Exception as e:
        print(f"Error searching and reranking in Elasticsearch: {str(e)}")
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
    st.title("Ingest Youtube Video ")

    # YouTube URL input and chunk button
    youtube_url = st.text_input("Enter YouTube URL:")
    if st.button("Process Video"):
        if youtube_url:
            chunk_youtube_video(youtube_url)
            ingest_video_subtitles(get_video_id(youtube_url))
        else:
            st.warning("Please enter a valid YouTube URL.")

    # List unique videos
    index_name = os.environ.get("ELASTICSEARCH_INDEX")
    unique_videos = get_unique_video_ids(es_client, index_name)
    
    st.title("Select Youtube Video")
    if unique_videos:
        selected_video = st.selectbox("Pick from", unique_videos, format_func=lambda x: f"{x[1]} ({x[0]})")
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
        
        if results and results['hits']['hits']:
            filtered_results = [hit for hit in results['hits']['hits'] if hit['_score'] > 3.0]
            if filtered_results:
                st.markdown(f"**Total Results (Score > 3.0):** {len(filtered_results)}")
                for hit in filtered_results:
                    source = hit['_source']
                    score = hit['_score']
                    st.write(f"Score: {score:.2f}")
                    st.write(f"Start Time: {source['start_time']:.2f}")
                    st.write(f"Text: {source['text']}")
                    st.write("---")
            else:
                st.write("No results with a score higher than 3.0 found for this video.")
        else:
            st.write("No results found for this video.")

# Re-rank button
if st.button("Re-rank"):
    if query and selected_video_id:
        with st.spinner("Re-ranking..."):
            reranked_results = rerank_elasticsearch(query=query, video_id=selected_video_id)
            
            if reranked_results and reranked_results['hits']['hits']:
                st.subheader("Re-ranked Results")
                for hit in reranked_results['hits']['hits']:
                    source = hit['_source']
                    score = hit['_score']
                    st.write(f"Re-ranked Score: {score:.2f}")
                    st.write(f"Start Time: {source['start_time']:.2f}")
                    st.write(f"Text: {source['text']}")
                    st.write("---")
            else:
                st.write("No re-ranked results found for this video.")
    else:
        st.warning("Please enter a query and select a video before re-ranking.")
