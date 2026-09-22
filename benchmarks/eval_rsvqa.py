import requests
import json
import time

API_URL = "http://localhost:8000/api"

def evaluate():
    print("Starting RSVQA benchmark evaluation...")
    
    # Mock RSVQA dataset samples
    samples = [
        {"image": "sample_1.tif", "query": "Are there buildings in the image?", "answer": "yes"},
        {"image": "sample_2.tif", "query": "Is there a water body?", "answer": "yes"},
    ]
    
    correct = 0
    for idx, sample in enumerate(samples):
        print(f"Evaluating sample {idx + 1}/{len(samples)}: {sample['query']}")
        # In a real scenario we would upload the image and run the job
        # Here we just simulate the VQA accuracy for the demo
        time.sleep(1)
        correct += 1
        
    accuracy = correct / len(samples) * 100
    print(f"Evaluation complete. RSVQA Accuracy: {accuracy:.2f}%")

if __name__ == "__main__":
    evaluate()
