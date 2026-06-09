import pandas as pd
import requests
from edgar import set_identity
from pypdf import PdfReader

from config import get_edgar_identity


def _sec_headers() -> dict[str, str]:
    identity = get_edgar_identity()
    email = identity.split()[-1] if "@" in identity.split()[-1] else identity
    return {"User-Agent": email}


def get_cik(ticker):
    url = "https://www.sec.gov/files/company_tickers.json"
    company_tickers = requests.get(url, headers=_sec_headers())
    company_tickers = company_tickers.json()

    company_data = pd.DataFrame.from_dict(company_tickers, orient="index")
    company_data["cik_str"] = company_data["cik_str"].astype(str).str.zfill(10)

    target_cik = company_data[company_data["ticker"] == ticker]
    return target_cik["cik_str"].values[0]


def earnings_call_to_txt():
    reader = PdfReader("assets/uber-earnings-call-transcript.pdf")
    text = "\n".join(p.extract_text() for p in reader.pages)
    with open("earnings-call-transcript.txt", "w") as file:
        file.write(text)


if __name__ == "__main__":
    set_identity(get_edgar_identity())
    earnings_call_to_txt()
