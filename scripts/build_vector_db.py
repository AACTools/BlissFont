#!/usr/bin/env python3
import os
import urllib.request
import json
import numpy as np

GLOVE_URL = "https://huggingface.co/JeremiahZ/glove/resolve/main/glove.6B.50d.txt"
RAW_DIR = os.path.join("data", "raw")
PROCESSED_DIR = os.path.join("data", "processed")
GLOVE_TXT_PATH = os.path.join(RAW_DIR, "glove.6B.50d.txt")
JSON_PATH = os.path.join(PROCESSED_DIR, "bliss_character_data.json")

VECTORS_BIN_PATH = os.path.join(PROCESSED_DIR, "vectors.bin")
VOCAB_TXT_PATH = os.path.join(PROCESSED_DIR, "vocab.txt")

def download_glove():
    if not os.path.exists(GLOVE_TXT_PATH):
        print(f"Downloading GloVe vectors from {GLOVE_URL}...")
        os.makedirs(RAW_DIR, exist_ok=True)
        # Download streaming to show progress
        with urllib.request.urlopen(GLOVE_URL) as response, open(GLOVE_TXT_PATH, 'wb') as out_file:
            meta = response.info()
            file_size = int(meta.get("Content-Length", 0))
            print(f"File size: {file_size / (1024 * 1024):.2f} MB")
            
            downloaded = 0
            block_size = 8192
            while True:
                buffer = response.read(block_size)
                if not buffer:
                    break
                downloaded += len(buffer)
                out_file.write(buffer)
                # print progress every 20MB
                if downloaded % (20 * 1024 * 1024) < block_size:
                    print(f"Downloaded: {downloaded / (1024 * 1024):.2f} MB / {file_size / (1024 * 1024):.2f} MB")
        print("Download completed successfully!")
    else:
        print("GloVe text file already exists.")

def build_vector_db():
    print("Building vector database...")
    
    # 1. Load active BCI words we need to match
    bci_words = set()
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            records = json.load(f)
            for rec in records:
                gloss = rec["glosses"]["en"].lower().strip()
                gloss_clean = gloss.replace("-(to)", "").replace("_(to)", "").strip()
                # Add individual words in compound glosses
                for word in gloss_clean.split():
                    bci_words.add(word)
                bci_words.add(gloss_clean)
    print(f"Loaded {len(bci_words)} active BCI-AV vocab terms.")

    vocab = []
    vectors = []
    
    # Keep the first 100,000 words in GloVe (the most frequent) 
    # plus any additional BCI-AV words
    max_glove_limit = 100000
    
    word_count = 0
    with open(GLOVE_TXT_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) != 51:
                continue
                
            word = parts[0].lower()
            
            # Keep if within limit OR if it is a BCI vocabulary word
            if word_count < max_glove_limit or word in bci_words:
                vocab.append(word)
                vector = np.array([float(x) for x in parts[1:]], dtype=np.float32)
                vectors.append(vector)
                
            word_count += 1
            if word_count % 100000 == 0:
                print(f"Processed {word_count} GloVe source lines...")
                
    # Convert vectors list to a numpy float16 matrix
    print("Formatting vectors to float16 binary matrix...")
    vectors_matrix = np.vstack(vectors).astype(np.float16)
    
    # Write files
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    
    # Write vocab
    print(f"Writing vocab.txt with {len(vocab)} words...")
    with open(VOCAB_TXT_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(vocab))
        
    # Write binary vectors
    print(f"Writing vectors.bin ({vectors_matrix.nbytes / (1024 * 1024):.2f} MB)...")
    with open(VECTORS_BIN_PATH, 'wb') as f:
        f.write(vectors_matrix.tobytes())
        
    print("Vector database built successfully!")

def main():
    download_glove()
    build_vector_db()

if __name__ == "__main__":
    main()
