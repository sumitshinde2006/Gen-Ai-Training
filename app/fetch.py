
# app/fetch.py

import requests
from pathlib import Path

RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

documents = {
    "dogr_varieties.html":
        "https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit",

    "manage_onion_garlic.pdf":
        "https://www.manage.gov.in/publications/eBooks/Good%20Agricultural%20Practices%20in%20Onion%20and%20Garlic.pdf",

    "dogr_garlic.html":
        "https://www.dogr.res.in/index.php/component/content/article/garlicagropedia?layout=edit"
}


def download_documents():

    for filename, url in documents.items():

        try:
            print(f"\nDownloading: {filename}")

            response = requests.get(url, timeout=30)
            response.raise_for_status()

            file_path = RAW_DIR / filename
            file_path.write_bytes(response.content)

            print(f"Downloaded successfully: {file_path}")

        except requests.exceptions.Timeout:
            print(f"Timeout error: {filename}")

        except requests.exceptions.RequestException as error:
            print(f"Download failed: {error}")

        except OSError as error:
            print(f"File saving error: {error}")


if __name__ == "__main__":
    download_documents()
