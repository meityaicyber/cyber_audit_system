import os
import sys

# Set HF_HOME so models are explicitly cached in the app directory for easier tracking (optional)
# os.environ["HF_HOME"] = "/app/models"

def download_models():
    print("Downloading HuggingFace models for offline use...")
    
    try:
        from transformers import pipeline
        
        # Zero-shot classification model
        model_name = "facebook/bart-large-mnli"
        
        print(f"Loading {model_name}...")
        # Instantiating the pipeline will download the model weights and cache them
        pipe = pipeline("zero-shot-classification", model=model_name)
        
        print("Download complete. Models are cached locally.")
        
    except Exception as e:
        print(f"Error downloading models: {e}")
        sys.exit(1)

if __name__ == "__main__":
    download_models()
