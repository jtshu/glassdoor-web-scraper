import httpx
import json
import csv
from typing import List

# Function to extract company ID from the search suggestion
def find_companies(query: str) -> str:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://www.glassdoor.com/',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive'
    }
    result = httpx.get(
        url=f"https://www.glassdoor.com/searchsuggest/typeahead?numSuggestions=8&source=GD_V2&version=NEW&rf=full&fallback=token&input={query}",
        headers=headers
    )
    if result.status_code != 200:
        raise Exception(f"Failed to fetch data, status code: {result.status_code}")

    try:
        data = json.loads(result.text)
    except json.JSONDecodeError:
        print("Failed to parse JSON response:")
        print(result.text)
        raise

    if not data:
        raise Exception("No suggestions found for the query.")

    return data[0]["suggestion"]

def read_company_names_from_csv(csv_file: str) -> List[str]:
    company_names = []
    with open(csv_file, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        for row in reader:
            company_names.append(row[0])
    return company_names

def write_company_names_to_csv(company_names: List[str], output_file: str) -> None:
    with open(output_file, 'w', encoding='utf-8', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Company Name"])
        for name in company_names:
            writer.writerow([name])

if __name__ == "__main__":
    try:
        input_csv = 'company_names_tech01.csv'
        output_csv = 'processed_company_names.csv'

        company_names = read_company_names_from_csv(input_csv)
        processed_company_names = []

        for company_name in company_names:
            try:
                print(f"Processing company: {company_name}")
                processed_name = find_companies(company_name)
                print(f"Processed Company Name: {processed_name}")
                processed_company_names.append(processed_name)
            except Exception as e:
                print(f"Error processing {company_name}: {e}")

        write_company_names_to_csv(processed_company_names, output_csv)
        print(f"All processed company names have been written to {output_csv}")
    except Exception as e:
        print(f"Error: {e}")
