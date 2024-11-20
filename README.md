# onboarding-search-1

This was done as a part of Onboarding as an Elastic Customer Architect. The goal of the project is to learn the features of Elasticsearch

I spend a lot of time on youtube videos. Some of these videos are long, like the Lex Fridman podcasts that last 3 hours or longer. Days or weeks after I watch a video, I want to sometimes revisit something that was talked in the video. I would like a way to give the general wording of what they talked, and it will tell me at what part of the video they discussed it, so that I cue to that time spot. There is no app on the web to do that. By the way, even if I knew the exact phrase that they talked, there is no app on the web that will give me the time stamp of that; so the app I want is one step more than that. 


## Set-Up 

Clone the repo, navigate to main folder, and install dependencies.
```bash
pip install -r requirements.txt
```

To run the youtube API, you need to set up gcloud API key, and also set up an Application Default Credentials as suggested in https://cloud.google.com/docs/authentication/provide-credentials-adc#how-to

Create a .env file and fill out the following:
```bash
ELASTIC_ENDPOINT="your Elastic endpoint"
ELASTIC_API_KEY="your Elastic API Key"
ELASTICSEARCH_INDEX="youtube_subtitles"
ELASTIC_MODEL_ID="elser_v2"
```
When you enter a youtube URL and press the button to "Process", it will load the youtube subtitles into Elasticsearch. 
Here's the mapping for the youtube_subtitles index:
```
    "mappings": {
      "_meta": {
        "created_by": "file-data-visualizer"
      },
      "properties": {
        "end_time": {
          "type": "double"
        },
        "start_time": {
          "type": "double"
        },
        "text": {
          "type": "text",
          "copy_to": [
            "text_semantic"
          ]
        },
        "text_semantic": {
          "type": "semantic_text",
          "inference_id": "my-elser-endpoint",
          "model_settings": {
            "task_type": "sparse_embedding"
          }
        },
        "title": {
          "type": "text"
        },
        "video_id": {
          "type": "keyword"
        }
      }
    }

## Running the App

Run the following command to start the app
```
python3 streamlit run main.py
```

## Use

1. Select the video from the left panel
2. Search an approximate text on the main panel. The search returns the text, cued up to the time that the text was said. 
3. Click play and enjoy!

