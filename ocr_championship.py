import os
import base64
import json
import time
import requests

# Configuration
API_KEY = "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"
IMAGE_PATH = r"c:\Users\master\tgbotikar-2\receipt.jpeg"

# Models to test (as provided by user)
MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "qwen/qwen2.5-vl-32b-instruct:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "mistralai/mistral-small-3.2-24b-instruct:free", # Checking if multimodal
    "google/gemma-3-12b-it:free", # Checking if multimodal
    "x-ai/grok-beta", # Trying a known grok identifier if 4.1 fails, but let's try user's first if valid, actually user said "x-ai/grok-4.1-fast" which might be hallucinated or very new. I'll stick to the likely multimodal ones first + user list.
]

# Let's use the exact list user gave, plus some known working ones if those fail.
# User list:
USER_MODELS = [
    "x-ai/grok-4.1-fast", # Might fail
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "mistralai/mistral-small-3.2-24b-instruct:free",
    "qwen/qwen2.5-vl-32b-instruct:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "google/gemma-3-12b-it:free",
    "google/gemma-3-27b-it:free",
    "google/gemini-2.0-flash-exp:free"
]

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def test_model(model_name, base64_image):
    print(f"\n--- Testing {model_name} ---")
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://foodflow.app", # Required by OpenRouter
        "X-Title": "FoodFlow Bot"
    }

    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Analyze this receipt. Return a JSON object with a list of items (name, price, quantity) and the total amount. Do not include markdown formatting, just raw JSON."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ]
    }

    start_time = time.time()
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30 # 30s timeout
        )
        duration = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            if "error" in result:
                print(f"❌ API Error: {result['error']}")
                return None
            
            content = result['choices'][0]['message']['content']
            print(f"✅ Success in {duration:.2f}s")
            print(f"Output snippet: {content[:200]}...")
            return {"model": model_name, "time": duration, "content": content, "status": "success"}
        else:
            print(f"❌ HTTP Error {response.status_code}: {response.text}")
            return {"model": model_name, "time": duration, "error": response.text, "status": "error"}
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return {"model": model_name, "time": 0, "error": str(e), "status": "error"}

def main():
    if not os.path.exists(IMAGE_PATH):
        print(f"Error: Image not found at {IMAGE_PATH}")
        return

    base64_img = encode_image(IMAGE_PATH)
    results = []

    print("🏆 STARTING OCR CHAMPIONSHIP 🏆")
    print("=================================")

    for model in USER_MODELS:
        result = test_model(model, base64_img)
        if result:
            results.append(result)

    print("\n\n📊 FINAL RESULTS 📊")
    print("===================")
    
    # Filter successes
    successes = [r for r in results if r["status"] == "success"]
    failures = [r for r in results if r["status"] == "error"]

    successes.sort(key=lambda x: x["time"])

    print(f"Total Models Tested: {len(USER_MODELS)}")
    print(f"Successful: {len(successes)}")
    print(f"Failed: {len(failures)}")

    if successes:
        print("\n🥇 WINNER (Fastest):")
        print(f"Model: {successes[0]['model']}")
        print(f"Time: {successes[0]['time']:.2f}s")
        
        print("\n🥈 RUNNER UP:")
        if len(successes) > 1:
            print(f"Model: {successes[1]['model']}")
            print(f"Time: {successes[1]['time']:.2f}s")
        else:
            print("None")
            
        print("\n📝 FULL RANKING:")
        for i, r in enumerate(successes):
            print(f"{i+1}. {r['model']} - {r['time']:.2f}s")
            
        # Save detailed log
        with open("ocr_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print("\nDetailed results saved to ocr_results.json")
    else:
        print("\n❌ NO MODELS SUCCEEDED. Check API key or image format.")

if __name__ == "__main__":
    main()
