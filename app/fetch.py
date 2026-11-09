
import requests
from pathlib import Path

RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

DOCUMENTS = {
    "dogr_varieties.html":
        "https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit",

    "dogr_garlic.html":
        "https://dogr.res.in/index.php/component/content/article/garlicagropedia?layout=edit",

    "manage_onion_garlic.pdf":
        "https://www.manage.gov.in/publications/eBooks/Good%20Agricultural%20Practices%20in%20Onion%20and%20Garlic.pdf"
}


def download_documents():

    for filename, url in DOCUMENTS.items():

        try:
            print(f"\nDownloading {filename}")

            response = requests.get(
                url,
                timeout=30,
                headers={"User-Agent": "KandaGuide Research Project"}
            )

            response.raise_for_status()

            if not response.content:
                raise ValueError("Downloaded file is empty")

            path = RAW_DIR / filename
            path.write_bytes(response.content)

            print(f"Successfully downloaded: {path}")

        except requests.exceptions.Timeout:
            print(f"Timeout while downloading {filename}")

        except requests.exceptions.RequestException as error:
            print(f"Download error: {error}")

        except (OSError, ValueError) as error:
            print(f"File error: {error}")


if __name__ == "__main__":
    download_documents()
