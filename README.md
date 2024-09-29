# onboarding-search-1

This was done as a part of Onboarding as an Elastic Customer Architect. The goal of the project is to learn the features of Elasticsearch

I spend a lot of time on youtube videos. Some of these videos are long, like the Lex Fridman podcasts that last 3 hours or longer. Days or weeks after I watch a video, I want to sometimes revisit something that was talked in the video. I would like a way to give the general wording of what they talked, and it will tell me at what part of the video they discussed it, so that I cue to that time spot. There is no app on the web to do that. By the way, even if I knew the exact phrase that they talked, there is no app on the web that will give me the time stamp of that; so the app I want is one step more than that. 


## Data Set-Up 

Clone the repo, navigate to main folder, and install dependencies.
```bash
pip install -r requirements.txt
```

Create a .env file and fill out the following:
```bash
ELASTIC_ENDPOINT="your Elastic endpoint"
ELASTIC_API_KEY="your Elastic API Key"
ELASTICSEARCH_INDEX="youtube_subtitles"
ELASTIC_MODEL_ID="elser_v2"
```

The data loaded into Elasticsearch are the youtube subtitles. Here are the steps to load that.
1. Update the youtube_subtitle_chunk.py with the URL of the youtube video you want to load
2. Chunk the subtitles using
```
python
```python3 youtube_subtitle_chunk.py
```
This will create a file with ndjson extension. Repeat the above steps any number of times to create more ndjson file
3. Combine the ndjson files into a combined ndjson file
4. Using Kibana "File Upload" integration, upload the combined ndjson file to Elasticsearch
5. Change the mapping for the text field, and add a semantic_text field also
```
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
```
6. Import into an index named youtube_subtitles

## Running the App

Run the following command to start the app
```
python3 streamlit run main.py
```

## Use

1. Select the video from the left panel
2. Search an approximate text on the main panel. The search returns the text, and the time. Cue up the youtube video to that time, and enjoy!g

