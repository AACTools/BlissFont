#!/usr/bin/env python3
import os
import sys
import zipfile
import requests

# BCI-AV 2025 and Unicode Proposals URLs
URLS = {
    "gloss_map": "http://www.blissymbolics.net/BCI-AV_2025-02-15/BCI-AV_SKOG_2025-02-15_ID_to_gloss_map.txt",
    "svg_zip": "http://www.blissymbolics.net/BCI-AV_2025-02-15/bliss_svg_id.zip",
    "derivations_xlsx": "http://www.blissymbolics.net/BCI-AV_2025-02-15/BCI-AV_SKOG_2025-02-15_(en+sv+no+fi+hu+de+nl+af+ru+is+lt+lv+po+fr+es+pt+it+dk)+derivations_8483-29642.xlsx",
    "pdf_n5130": "http://unicode.org/wg2/docs/n5130-blissymbols.pdf",
    "pdf_n5149": "http://unicode.org/wg2/docs/n5149-blissymbols-keyboards.pdf",
    "pdf_n5171": "http://unicode.org/wg2/docs/n5171-bliss-radicals.pdf",
    "pdf_n5228": "https://www.unicode.org/L2/L2023/23138-n5228-blissymbols.pdf"
}

RAW_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "raw"))
SVG_EXTRACT_DIR = os.path.join(RAW_DIR, "svgs")

def download_file(url, target_path):
    print(f"Downloading: {url} -> {target_path}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        block_size = 1024 * 64  # 64 KB
        
        with open(target_path, 'wb') as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=block_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        sys.stdout.write(f"\rProgress: {percent:.1f}% ({downloaded}/{total_size} bytes)")
                        sys.stdout.flush()
            print() # Newline after progress
        print("Download complete.")
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        sys.exit(1)

def extract_zip(zip_path, extract_dir):
    print(f"Extracting: {zip_path} -> {extract_dir}")
    try:
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Get list of files to show progress
            file_list = zip_ref.namelist()
            total_files = len(file_list)
            for i, member in enumerate(file_list):
                zip_ref.extract(member, path=extract_dir)
                if i % 100 == 0 or i == total_files - 1:
                    sys.stdout.write(f"\rExtracting: {i+1}/{total_files} files")
                    sys.stdout.flush()
            print()
        print("Extraction complete.")
    except Exception as e:
        print(f"Error extracting {zip_path}: {e}")
        sys.exit(1)

def main():
    # Make sure target directories exist
    os.makedirs(RAW_DIR, exist_ok=True)
    
    # 1. Download ID to Gloss map
    gloss_map_path = os.path.join(RAW_DIR, "BCI-AV_SKOG_2025-02-15_ID_to_gloss_map.txt")
    if not os.path.exists(gloss_map_path):
        download_file(URLS["gloss_map"], gloss_map_path)
    else:
        print(f"Gloss map already exists: {gloss_map_path}")
        
    # 2. Download Excel derivations and translations
    xlsx_path = os.path.join(RAW_DIR, "BCI-AV_SKOG_2025-02-15_derivations_translations.xlsx")
    if not os.path.exists(xlsx_path):
        download_file(URLS["derivations_xlsx"], xlsx_path)
    else:
        print(f"Excel derivations file already exists: {xlsx_path}")
        
    # 3. Download and Extract SVG Zip
    svg_zip_path = os.path.join(RAW_DIR, "bliss_svg_id.zip")
    if not os.path.exists(svg_zip_path):
        download_file(URLS["svg_zip"], svg_zip_path)
    else:
        print(f"SVG Zip archive already exists: {svg_zip_path}")
        
    # Extract ZIP
    if os.path.exists(svg_zip_path):
        # We extract if target svgs dir doesn't exist or is empty
        if not os.path.exists(SVG_EXTRACT_DIR) or not os.listdir(SVG_EXTRACT_DIR):
            extract_zip(svg_zip_path, SVG_EXTRACT_DIR)
        else:
            print(f"SVG directory already exists and is not empty: {SVG_EXTRACT_DIR}")

    # 4. Download Unicode and Keyboard spec PDFs
    pdf_keys = ["pdf_n5130", "pdf_n5149", "pdf_n5171", "pdf_n5228"]
    for key in pdf_keys:
        filename = URLS[key].split("/")[-1]
        pdf_path = os.path.join(RAW_DIR, filename)
        if not os.path.exists(pdf_path):
            download_file(URLS[key], pdf_path)
        else:
            print(f"PDF already exists: {pdf_path}")

    print("\nData bootstrapping process complete!")

if __name__ == "__main__":
    main()
