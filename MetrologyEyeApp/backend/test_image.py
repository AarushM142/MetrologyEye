import httpx
import json

# Replace with the path to your snickers image
IMAGE_PATH = "snickers_back.jpg"

def test_label():
    url = "http://127.0.0.1:8000/api/analyze"
    
    with open(IMAGE_PATH, "rb") as f:
        files = {"file": ("snickers.jpg", f, "image/jpeg")}
        # If you didn't place an ID card in the photo, the scale will rely purely on the barcode
        print(f"Sending {IMAGE_PATH} to MetrologyEye API...")
        response = httpx.post(url, files=files, timeout=120.0)
        
        if response.status_code == 200:
            print("\nSuccess! Response:")
            print(json.dumps(response.json(), indent=2))
        else:
            print(f"Failed: {response.status_code}")
            print(response.text)

if __name__ == "__main__":
    test_label()
