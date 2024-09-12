import requests
import os
from PIL import Image
import io
import time
from dotenv import load_dotenv
import base64

load_dotenv()

QWEN_URL = os.getenv('QWEN_URL')

def process_images(image_paths, prompt):
    files = []
    for image_path in image_paths:
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()
        files.append(("images", (os.path.basename(image_path), image_data, "image/png")))

    data = {"prompt": prompt}

    try:
        response = requests.post(QWEN_URL, files=files, data=data)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        return f"Error processing request: {e}"
    

def process_images_batch(image_paths, prompt):
    requests_data = []
    for image_path in image_paths:
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()
        encoded_image = base64.b64encode(image_data).decode('utf-8')
        requests_data.append({
            "prompt": prompt,
            "images": [encoded_image]
        })

    try:
        response = requests.post(f"{QWEN_URL}/batch", json={"requests": requests_data})
        response.raise_for_status()
        return response.json()["generated_texts"]
    except requests.exceptions.RequestException as e:
        return f"Error processing request: {e}"

def test_qwen_batch():
    script_dir = os.path.dirname(__file__)
    test_dir = os.path.join(script_dir, "test_images")

    if not os.path.exists(test_dir):
        print(f"Error: Test directory not found at {test_dir}")
        return

    image_files = [os.path.join(test_dir, f) for f in os.listdir(test_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    print(f"Processing {len(image_files)} images")

    if not image_files:
        print(f"No image files found in {test_dir}")
        return

    prompt = "Return the provided complex table in JSON format that preserves information and hierarchy from the table at 100 percent accuracy."

    start_time = time.time()
    results = process_images_batch(image_files, prompt)
    end_time = time.time()

    total_time = end_time - start_time
    print(f"Batch processing results:")
    for i, result in enumerate(results):
        print(f"Result for image {i + 1}:")
        print(result)
        print("-" * 50)
    print(f"Total execution time for batch: {total_time:.2f} seconds")




def test_qwen_sync():
    script_dir = os.path.dirname(__file__)
    test_dir = os.path.join(script_dir, "test_images")

    if not os.path.exists(test_dir):
        print(f"Error: Test directory not found at {test_dir}")
        return

    image_files = [os.path.join(test_dir, f) for f in os.listdir(test_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

    if not image_files:
        print(f"No image files found in {test_dir}")
        return

    prompt = "Return the provided complex table in JSON format that preserves information and heirarchy from the table at 100 percent accuracy." 
    
    total_time = 0
    for image_file in image_files:
        start_time = time.time()
        result = process_images([image_file], prompt)
        end_time = time.time()
        
        processing_time = end_time - start_time
        total_time += processing_time
        
        print(f"Processing result for {os.path.basename(image_file)}:")
        print(result)
        print(f"Execution time: {processing_time:.2f} seconds")
        print("-" * 50)

    print(f"Total execution time for sync processing: {total_time:.2f} seconds")

if __name__ == "__main__":
    print("Testing Qwen Batch Processing:")
    test_qwen_batch()
    print("\n" + "=" * 50 + "\n")
    # print("Testing Qwen Sync Processing:")
    # test_qwen_sync()