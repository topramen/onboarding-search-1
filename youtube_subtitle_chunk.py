import os
import re
import json
from youtube_transcript_api import YouTubeTranscriptApi

def get_video_id(url):
    # Regular expression pattern to match various YouTube URL formats
    pattern = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=)?(?:embed\/)?(?:v\/)?(?:shorts\/)?(?:live\/)?(?:(?!videos)(?!channel)(?!user)(?!playlist).)*'
    
    # Try to match the pattern in the URL
    match = re.search(pattern + '([\w-]{11})', url)
    
    if match:
        return match.group(1)
    else:
        return None

def download_subtitles(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return [{'start': entry['start'], 'duration': entry['duration'], 'text': entry['text'], 'video_id': video_id} for entry in transcript]
    except Exception as e:
        print(f"Error downloading subtitles: {str(e)}")
        return None


def chunk_subtitles(subtitles, chunk_size=60, overlap=10):
    chunks = []
    current_chunk = []
    current_time = 0

    for sub in subtitles:
        start_time = sub['start']
        if start_time > current_time + overlap:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = []
            current_time = start_time

        current_chunk.append(sub)
        if start_time + sub['duration'] > current_time + chunk_size:
            current_time = start_time + sub['duration'] - overlap

    if current_chunk:
        chunks.append(current_chunk)

    return chunks

def save_chunks_to_files(chunks):
    if not chunks or not chunks[0]:
        print("No chunks to save.")
        return

    video_id = chunks[0][0]['video_id']
    file_name = f"{video_id}.ndjson"
    file_path = os.path.join(os.getcwd(), file_name)

    with open(file_path, 'w') as f:
        for chunk in chunks:
            chunk_text = " ".join([sub['text'] for sub in chunk])
            start_time = chunk[0]['start']
            end_time = chunk[-1]['start'] + chunk[-1]['duration']
            chunk_data = {
                "video_id": video_id,
                "start_time": start_time,
                "end_time": end_time,
                "text": chunk_text
            }
            f.write(json.dumps(chunk_data) + '\n')

    print(f"Chunks saved to {file_name} in NDJSON format.")



if __name__ == "__main__":
    url = "https://www.youtube.com/watch?v=DcWqzZ3I2cY"
    video_id = get_video_id(url)
    print(f"Video ID: {video_id}")
    
    if video_id:
        subtitles = download_subtitles(video_id)
        print(f"Subtitles: {subtitles[:2]}...")  # Print first two subtitle entries
        
        if subtitles:
            chunks = chunk_subtitles(subtitles)
            print(f"Number of chunks: {len(chunks)}")
            print(f"First chunk: {chunks[0][:2]}...")  # Print first two entries of the first chunk
            
            save_chunks_to_files(chunks)
            print("Chunks saved to files.")
        else:
            print("Failed to download subtitles.")
    else:
        print("Failed to extract video ID from URL.")
