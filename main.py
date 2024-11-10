import streamlit as st
import os
from elasticsearch import Elasticsearch, AsyncElasticsearch
# from utils import get_current_time, count_words_in_conversation
# from streamlit_components.es import save_conversation, load_conversation, get_elasticsearch_results, create_RAG_context, get_valid_indices
# from settings import valid_index_list
from dotenv import load_dotenv
from youtube_utils import get_youtube_title, chunk_youtube_video, get_video_id
import json
import cohere

load_dotenv()


es = Elasticsearch(
    os.getenv('ELASTIC_ENDPOINT'),
    api_key=os.getenv('ELASTIC_API_KEY')
)
index_name = os.environ.get("ELASTICSEARCH_INDEX")

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
    search_body = {
        "size": 5,  # Limit the number of returned documents to 5
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

def rerank_with_cohere(documents, query):
    # cohere_client = cohere.Client(os.getenv("COHERE_API_KEY"))
    # cohere_endpoint = cohere_client.inference.get_model("cohere_rerank")    
    rerank_response = es.inference.inference(
        inference_id="cohere_rerank",
        body={
            "query": query,
            "input": documents,
            "task_settings": {
                "return_documents": False
            }
        }
    )
    return rerank_response



# Function to display ELSER results
def display_elser_results():
    if 'elser_results' in st.session_state and st.session_state.elser_results:
        results = st.session_state.elser_results
        # st.subheader(f"Results for Video: {selected_video[1]}")
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

try:
    # Elasticsearch setup
    es_endpoint = os.environ.get("ELASTIC_ENDPOINT")
    es_client = Elasticsearch(
        es_endpoint,
        api_key=os.environ.get("ELASTIC_API_KEY")
    )
except Exception as e:
    es_client=None


# Main app logic
st.set_page_config(layout="wide")
set_page_container_style()

# LEFT SIDEBAR
with st.sidebar:
    st.title("Ingest Youtube Video ")

    # YouTube URL input and chunk button
    youtube_url = st.text_input("Enter YouTube URL:")
    if st.button("Process Video"):
        if youtube_url:
            video_id = get_video_id(youtube_url)
            # Check if video exists in elasticsearch
            try:
                existing_video = es_client.count(
                    index=index_name,
                    body={"query": {"term": {"video_id": video_id}}}
                )
                if existing_video["count"] > 0:
                    st.warning("This video has already been processed and indexed.")
                else:
                    chunk_youtube_video(youtube_url)
                    ingest_video_subtitles(video_id)
            except Exception as e:
                st.error(f"Error checking video status: {str(e)}")
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
query = st.text_input("Enter your search query (Cmd-R/Ctrl-R to refresh):")


# Re-rank button
if st.button("Rank with ELSER and Re-rank with Cohere"):
    if query and selected_video_id:
        with st.spinner("Re-ranking..."):
            if 'elser_results' not in st.session_state or not st.session_state.elser_results:
                st.session_state.elser_results = search_elasticsearch(query=query, video_id=selected_video_id)
            
            results = st.session_state.elser_results
            # Filter results with a score higher than a threshold, which is 0.0 for testing
            filtered_results = [hit['_source']['text'] for hit in results['hits']['hits'] if hit['_score'] > 0.0]
            print(f"Debug: Number of filtered results: {len(filtered_results)}")
            if filtered_results:
                reranked_results = rerank_with_cohere(filtered_results, query)
                print(f"Debug: Number of reranked results: {len(reranked_results['rerank'])}")
                st.subheader(f"Re-ranked Results for video: {selected_video[1]}")
                sorted_results = sorted(results['hits']['hits'], 
                                        key=lambda x: next((item['relevance_score'] for item in reranked_results['rerank'] if item['index'] == results['hits']['hits'].index(x)), 0),
                                        reverse=True)

                for hit in sorted_results:
                    source = hit['_source']
                    score = hit['_score']
                    rerank_score = next((item['relevance_score'] for item in reranked_results['rerank'] if item['index'] == results['hits']['hits'].index(hit)), 0)
                    
                    st.write(f"Original Score: {score:.2f}")
                    st.write(f"Reranked Score: {rerank_score:.6f}")
                    st.write(f"Start Time: {source['start_time']:.2f}")
                    st.write(f"Text: {source['text']}")
                    
                    # Add YouTube video frame cued up to the start time
                    video_url = f"https://www.youtube.com/embed/{selected_video_id}?start={int(source['start_time'])}"
                    st.components.v1.iframe(src=video_url, width=560, height=315)
                    
                    st.write("---")
            else:
                st.write("No results with a score higher than 3.0 found for this video.")
    else:
        st.warning("Please enter a query and select a video before re-ranking.")

# Display ELSER results if they exist (to keep them visible after re-ranking)
if 'elser_results' in st.session_state:
    st.subheader(f"Original ELSER Results for video: {selected_video[1]}")
    display_elser_results()
