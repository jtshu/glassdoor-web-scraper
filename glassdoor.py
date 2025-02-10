import httpx
import json
import csv
import re
import time
import random
from parsel import Selector
from typing import List, Dict, Tuple
from openai import OpenAI
import os

# Function to extract company ID from the search suggestion
def find_companies(query: str) -> Tuple[str, str]:
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

    return data[0]["suggestion"], data[0]["employerId"]

# Function to parse interview details directly from HTML
def parse_interview_details(response: httpx.Response) -> List[Dict]:
    selector = Selector(response.text)
    interview_details = []

    interviews = selector.css("div[data-test^='Interview']")

    # Difficulty mapping
    difficulty_mapping = {
        "Difficult Interview": "Hard",
        "Average Interview": "Medium",
        "Easy Interview": "Easy"
    }

    # Skipping the first x number of entries, if necessary
    # interviews = interviews[4:]

    for interview in interviews:

        # Location and questions go first because they skip the entry if they're null
        location = interview.css("p.interview-details__interview-details-module__userLine::text").get()
        if location:
            match = re.search(r'\bin\b\s*(.*)', location)
            location = match.group(1) if match else ''
        if not location:  # Skip if location is empty
            continue

        questions = interview.css("div[data-test='question-container'] p.truncated-text__truncated-text-module__truncate::text").getall()
        if not questions: # Skip if questions is empty
            continue

        question_string = " ".join(questions)
        if len(question_string) > 200: # Skip if question field is over 200 characters
            continue

        # ChatGPT to rephrase question

        question_string = chatgpt_rephrase(question_string)

        # Get divs for interview difficulty but skip the first one since that points to experience instead
        difficulty_divs = interview.css("div.d-flex.flex-row.InterviewContainer__InterviewDetailsStyles__interviewExperience")
        difficulty = None
        if len(difficulty_divs) > 1:
            difficulty = difficulty_divs[1].css("span:not([class])::text").get()
            if difficulty in difficulty_mapping:
                difficulty = difficulty_mapping[difficulty]

        date_posted = interview.css("span.timestamp__timestamp-module__reviewDate::text").get()
        role = interview.css("h2.header__header-module__h2::text").get()

        # Calculated fields

        # Experience
        if "intern" in role.lower():
            experience = 0
        elif "entry" in role.lower():
            experience = random.randint(0,2)
        elif "manager" in role.lower():
            experience = random.randint(5,10)
        elif "director" in role.lower():
            experience = random.randint(10,15)
        elif "president" in role.lower():
            experience = random.randint(10,20)
        elif "chief" in role.lower():
            experience = random.randint(10,20)
        elif "senior" in role.lower():
            experience = random.randint(5,7)
        elif "principal" in role.lower():
            experience = random.randint(8,10)
        else:
            experience = random.randint(0,7)

        interview_detail = {
            "id": "",
            "created_at": date_posted,
            "question": question_string,
            "role": role,
            "difficulty": difficulty,
            "votes": 0,
            "reported": 0,
            "company_id": "",
            "location": location,
            "experience": experience,
            "updated_at": "",
            "question_source": "Glassdoor",
            "locked": "FALSE",
            "type": "", # Could be calculated, but couldn't figure out how to do it properly, so doing it in Excel instead
            "solution": "",
            "solution_source": "Generated",
            "category": "",
            "company_name": company_name # Not a field in the actual db but is needed to join on existing company table to get company_id
        }

        # Only add non-empty interview details
        if any(interview_detail.values()):
            interview_details.append(interview_detail)

    return interview_details

def scrape_interview_details(base_url: str, num_pages: int) -> List[Dict]:
    interview_details = []

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://www.glassdoor.com/',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive'
    }

    for i in range(num_pages):
        if i == 0:
            url = f"{base_url}.htm"
        else:
            url = f"{base_url}_P{i+1}.htm"
        # print(f"Fetching URL: {url}")  # Debugging line
        response = httpx.get(url, cookies={"tldp": "1"}, headers=headers, follow_redirects=True)
        if response.status_code != 200:
            print(f"Failed to fetch data, status code: {response.status_code}")
            continue
        more_details = parse_interview_details(response)
        # print(f"Page {i+1} - Extracted {len(more_details)} interview details") # Debugging line
        interview_details.extend(more_details)
        time.sleep(random.randint(1,3))

    return interview_details

def read_company_names_from_csv(csv_file: str) -> List[str]:
    company_names = []
    with open(csv_file, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        for row in reader:
            company_names.append(row[0])
    return company_names

def chatgpt_rephrase(question: str) -> str:
    os.environ["OPENAI_API_KEY"] = "" # Need to use env file to populate this key
    
    client = OpenAI()

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": f"Rephrase the following interview question/description in a straightforward and concise manner, avoiding unncessary filler words like 'Certainly', 'Sure', and 'Of course' and reply with only the rephrased content: {question}",
            },
        ],
    )
    return completion.choices[0].message.content

def get_solution_from_chatgpt(question: str, company_name: str) -> str:
    os.environ["OPENAI_API_KEY"] = "" # Need to use env file to populate this key
    
    client = OpenAI()

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": f"In one paragraph or less, explain how I can best answer this interview question for {company_name} in a straightforward and concise manner, avoiding unncessary filler words like 'Certainly', 'Sure', and 'Of course': {question}",
            },
        ],
    )
    return completion.choices[0].message.content

if __name__ == "__main__":
    try:
        company_names = read_company_names_from_csv('company_names_403t3.csv')

        all_interview_details = []

        for company_name in company_names:
            try:
                print(f"Processing company: {company_name}")
                company_name, company_id = find_companies(company_name)
                # print(f"Company Name: {company_name}, Company ID: {company_id}")

                base_url = f"https://www.glassdoor.com/Interview/{company_name}-Interview-Questions-E{company_id}"
                num_pages = 10  # Number of pages to scrape

                # Scrape interview details from the dynamically generated URLs
                interview_details = scrape_interview_details(base_url, num_pages)

                for detail in interview_details:
                    if detail['question']:
                        question = detail['question']
                        solution = get_solution_from_chatgpt(question, company_name)
                        detail['solution'] = solution
                
                all_interview_details.extend(interview_details)
            except Exception as e:
                print(f"Error processing {company_name}: {e}")

        # Write all interview details to a CSV file
        if all_interview_details:
            fieldnames = list(all_interview_details[0].keys())
            with open("all_interview_details_403t3.csv", "w", encoding="utf-8", newline='') as file:
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_interview_details)

        print("Web scraping completed.")
    except Exception as e:
        print(f"Error: {e}")
