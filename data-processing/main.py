import requests
import pandas as pd
from pypdf import PdfReader
from edgar import set_identity, Company, Filing

headers = {'User-Agent': 'saracheak@gmail.com'}
set_identity("Sara Cheakdkaipejchara saracheak@gmail.com")
fmp_api_key = "7eQNl9ZJ6ebp3YRXABaK8HXshV8xwNdb"

def get_cik(ticker):
    #get json data from SEC
    url = 'https://www.sec.gov/files/company_tickers.json'
    company_tickers = requests.get(url, headers=headers)
    company_tickers = company_tickers.json()

    #put in dataframe
    company_data = pd.DataFrame.from_dict(company_tickers, orient='index')
    
    #cik numbers have to be 10 digits so fill in leading zeroes if needed
    company_data['cik_str'] = company_data['cik_str'].astype(str).str.zfill(10)

    target_cik = company_data[company_data['ticker'] == ticker]
    target_cik = target_cik['cik_str'].values[0]

    return target_cik

def get_earnings_call(ticker, year, quarter):
    url = f"https://financialmodelingprep.com/stable/earning-call-transcript?symbol={ticker}&year={year}&quarter={quarter}&apikey={fmp_api_key}"
    response = requests.get(url).json()
    earnings_call = response[0].get("content")
    return earnings_call

def earnings_call_to_txt():
    reader = PdfReader("assets/uber-earnings-call-transcript.pdf")
    text = "\n".join(p.extract_text() for p in reader.pages)
    with open("earnings-call-transcript.txt", "w") as file:
        file.write(text)

if __name__ == "__main__":
    earnings_call_to_txt()