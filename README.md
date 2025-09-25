# GoodReadsFuzzyEnricher
Turn book lists from screenshots into rich, research-ready CSVs—no summaries, just real books.

## Why I Made This
I kept seeing ads for Headway, the app that summarizes books. Their lists of “must-read” books were intriguing, but I wanted to read the actual books, not just summaries, and I didn’t want to pay for a service I wouldn’t use. So, I started taking screenshots of their book lists from ads, then used an LLM to extract the book titles into a CSV.
But a plain list of titles isn’t enough. I wanted more: authors, publication years and Goodreads links That’s why I built goodReadsFuzzyEnricher a script that takes your CSV of book titles and enriches it with all the info you need, straight from Goodreads.

## What It Does
Enriches your CSV: Adds author, publication year, ratings, and Goodreads link for each book.
Fuzzy matches titles: Handles typos and variations in book names.
Interactive selection: If there’s ambiguity, you get a slick GUI to pick the right book (with cover images!).
Batch processing: Handles big lists with a progress bar so you always know what’s happening.

## See It In Action
When fuzzy matching can’t decide, you get to choose the right book from a visual picker:


## How To Use
Prepare your CSV: One column with book titles (from screenshots, LLMs, wherever).
Run the script:
```
python goodReadsFuzzyEnricher.py
```

Pick your CSV and column: The script will guide you with file and column pickers.

Let it work: Watch the progress bar. If a book isn’t matched automatically, you’ll get to pick from candidates (with covers).

Get your enriched CSV: Find it saved alongside your original file.

## Requirements
Python 3.7+
pandas, requests, beautifulsoup4, tqdm
(Optional for best experience) Pillow, rapidfuzz
Install dependencies with:
```
pip install -r requirements.txt
```

## Contribute
PRs and suggestions welcome!

### 📄 License
MIT


**Enjoy reading, not just summarizing!**