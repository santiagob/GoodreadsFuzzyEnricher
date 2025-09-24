import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import quote, urljoin
from tqdm import tqdm

def normalize_title(title):
    """Normalize book title for better matching."""
    if pd.isna(title) or title == '':
        return ''
    title = str(title).lower().strip()
    # Remove common edition/format info
    title = re.sub(r'\b(anniversary|edition|illustrated|collector|gift|pack|hardcover|paperback|kindle|ebook)\b.*', '', title)
    # Remove punctuation except spaces and alphanumeric
    title = re.sub(r'[^\w\s]', ' ', title)
    # Remove extra spaces
    title = ' '.join(title.split())
    return title

def search_goodreads(query, max_retries=3):
    """Search Goodreads for a book and return metadata."""
    normalized_query = normalize_title(query)
    search_url = f"https://www.goodreads.com/search?q={quote(normalized_query)}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive'
    }
    for attempt in range(max_retries):
        try:
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            # Try multiple selectors for robustness
            results = soup.find_all('tr', {'itemtype': 'http://schema.org/Book'})
            if not results:
                results = soup.find_all('div', class_='bookBox')
            if not results:
                results = soup.find_all('table', class_='tableList')
                if results:
                    results = results[0].find_all('tr')[1:]  # Skip header row
            if not results:
                return {'exact_title': '', 'author': '', 'publish_date': '', 'goodreads_url': ''}
            first_result = results[0]
            # Extract book title
            title_elem = first_result.find('a', class_='bookTitle')
            if not title_elem:
                title_elem = first_result.find('a', href=re.compile(r'/book/show/'))
            exact_title = title_elem.get_text(strip=True) if title_elem else ''
            # Extract book URL
            book_url = urljoin('https://www.goodreads.com', title_elem['href']) if title_elem and title_elem.get('href') else ''
            # Extract author
            author_elem = first_result.find('a', class_='authorName')
            if not author_elem:
                author_elem = first_result.find('a', href=re.compile(r'/author/show/'))
            author = author_elem.get_text(strip=True) if author_elem else ''
            # Extract publication date
            pub_date = ''
            pub_elem = first_result.find('span', class_='greyText smallText')
            if pub_elem:
                pub_text = pub_elem.get_text(strip=True)
                year_match = re.search(r'\b(19|20)\d{2}\b', pub_text)
                if year_match:
                    pub_date = year_match.group()
            return {
                'exact_title': exact_title,
                'author': author,
                'publish_date': pub_date,
                'goodreads_url': book_url
            }
        except requests.RequestException:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return {'exact_title': '', 'author': '', 'publish_date': '', 'goodreads_url': ''}
        except Exception:
            return {'exact_title': '', 'author': '', 'publish_date': '', 'goodreads_url': ''}

def process_book_csv(input_file, book_column, output_file=None, delay=1.5):
    """
    Process a CSV file with book names and add Goodreads metadata.
    Parameters:
        input_file: Path to input CSV file
        book_column: Name of the column containing book titles
        output_file: Path to output CSV file (optional)
        delay: Delay between requests in seconds
    """
    df = pd.read_csv(input_file)
    total = len(df)
    print(f"Processing {total} entries from '{input_file}'...")
    
    if book_column not in df.columns:
        raise ValueError(f"Column '{book_column}' not found in CSV. Available columns: {list(df.columns)}")
    df['exact_book_name'] = ''
    df['author'] = ''
    df['publish_date'] = ''
    df['goodreads_link'] = ''
    
    
    for index, row in tqdm(df.iterrows(), total=total, desc="Enriching with Goodreads data"):
        book_name = row[book_column]
        if pd.isna(book_name) or book_name == '':
            continue
        metadata = search_goodreads(book_name)
        df.loc[index, 'exact_book_name'] = metadata['exact_title']
        df.loc[index, 'author'] = metadata['author']
        df.loc[index, 'publish_date'] = metadata['publish_date']
        df.loc[index, 'goodreads_link'] = metadata['goodreads_url']
        time.sleep(delay)
        
    # Save to output file
    if output_file is None:
        output_file = input_file.replace('.csv', '_with_goodreads.csv')
    df.to_csv(output_file, index=False)
    print(f"Results saved to: {output_file}")
    return df

import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import quote, urljoin

# ... (your function definitions remain unchanged) ...

if __name__ == "__main__":
    import tkinter as tk
    from tkinter import filedialog, simpledialog

    # Hide the main tkinter window
    root = tk.Tk()
    root.withdraw()

    # Ask user to select the input CSV file
    input_file = filedialog.askopenfilename(
        title="Select input CSV file",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )
    if not input_file:
        print("No file selected. Exiting.")
        exit()

    # Read the CSV header to get column names
    df = pd.read_csv(input_file, nrows=0)
    columns = df.columns.tolist()

    # Ask user for the column name containing book titles
    book_column = simpledialog.askstring(
        "Book Column",
        f"Enter the name of the column containing book titles (leave blank to use '{columns[0]}'):"
    )

    # If not specified, use the first column
    if not book_column or book_column.strip() == "":
        book_column = columns[0]

    # Ask user to select output file (optional)
    output_file = filedialog.asksaveasfilename(
        title="Save output CSV as...",
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )
    if not output_file:
        output_file = None  # Will use default naming

    process_book_csv(input_file, book_column, output_file)