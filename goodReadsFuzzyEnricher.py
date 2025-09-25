import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import quote, urljoin
from tqdm import tqdm
import difflib
import argparse
import io
import sys
import tkinter as tk
from tkinter import simpledialog
from tkinter import filedialog

# Check for optional dependencies
try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except Exception:
    RAPIDFUZZ_AVAILABLE = False
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False
    

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

def search_goodreads(query, max_retries=3, max_results=5):
    """Search Goodreads for a book and return a list of candidate metadata dicts.
    Returns up to `max_results` candidates (may be empty list on failure).
    """
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
                return []

            candidates = []
            for res in results:
                if len(candidates) >= max_results:
                    break
                title_elem = res.find('a', class_='bookTitle')
                if not title_elem:
                    title_elem = res.find('a', href=re.compile(r'/book/show/'))
                exact_title = title_elem.get_text(strip=True) if title_elem else ''
                book_url = urljoin('https://www.goodreads.com', title_elem['href']) if title_elem and title_elem.get('href') else ''
                author_elem = res.find('a', class_='authorName')
                if not author_elem:
                    author_elem = res.find('a', href=re.compile(r'/author/show/'))
                author = author_elem.get_text(strip=True) if author_elem else ''
                pub_date = ''
                ratings_count = 0
                pub_elem = res.find('span', class_='greyText smallText uitext')
                if pub_elem:
                    pub_text = pub_elem.get_text(strip=True)
                    year_match = re.search(r'\b(19|20)\d{2}\b', pub_text)
                    if year_match:
                        pub_date = year_match.group()
                    # Try to extract number of ratings from the same element (e.g. "1,234 ratings")
                    ratings_count = 0
                    try:
                        ratings_match = re.search(r"([0-9][0-9,]*)\s+rating", pub_text, flags=re.IGNORECASE)
                        if ratings_match:
                            ratings_count = int(ratings_match.group(1).replace(',', ''))
                    except Exception:
                        ratings_count = 0
                # Try to extract an image URL from the result
                img_elem = res.find('img')
                image_url = ''
                if img_elem:
                    image_url = img_elem.get('src') or img_elem.get('data-src') or ''
                    # Some src may be relative or contain parameters; try to clean
                    if image_url and image_url.startswith('//'):
                        image_url = 'https:' + image_url
                candidates.append({
                    'exact_title': exact_title,
                    'author': author,
                    'publish_date': pub_date,
                    'ratings_count': ratings_count,
                    'goodreads_url': book_url,
                    'image_url': image_url
                })
            return candidates
        except requests.RequestException:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return []
        except Exception:
            return []

def ask_user_choice_with_images(root, book_name, candidates):
    """Show a dialog that displays up to 3 candidates with covers and lets the user page through results.
    Returns the selected candidate dict or None if user chooses 'None of these' or cancels.
    """
    class ManualMatchDialog:
        def __init__(self, parent, book_name, candidates):
            self.parent = parent
            self.book_name = book_name
            self.candidates = candidates
            self.page = 0
            self.per_page = 3
            self.selected_idx = None
            self.photo_refs = []
            self.none_selected = False
            self.top = tk.Toplevel(parent)
            self.top.title('Select book match')
            self.top.transient(parent)
            # Make sure the dialog is visible and focused
            try:
                self.top.deiconify()
                self.top.lift()
                self.top.focus_force()
            except Exception:
                pass
            self.top.grab_set()
            # Ensure closing the window via the window manager triggers the same cleanup
            self.top.protocol('WM_DELETE_WINDOW', self.on_cancel)
            self.build_widgets()
            self.render_page()
            parent.wait_window(self.top)

        def build_widgets(self):
            tk.Label(self.top, text=f"Multiple matches found for: {self.book_name}").pack(padx=8, pady=6)
            self.frame = tk.Frame(self.top)
            self.frame.pack(padx=8, pady=4)
            # Controls
            ctrl = tk.Frame(self.top)
            ctrl.pack(fill='x', pady=6)
            self.more_btn = tk.Button(ctrl, text='Next set', command=self.on_more)
            self.more_btn.pack(side='left', padx=6)
            tk.Button(ctrl, text='Skip', command=self.on_none).pack(side='left', padx=6)
            tk.Button(ctrl, text='Cancel', command=self.on_cancel).pack(side='right', padx=6)
            tk.Button(ctrl, text='OK', command=self.on_ok).pack(side='right', padx=6)

        def render_page(self):
            for child in self.frame.winfo_children():
                child.destroy()
            self.photo_refs = []
            start = self.page * self.per_page
            end = start + self.per_page
            slice = self.candidates[start:end]
            if not slice:
                tk.Label(self.frame, text='No more results.').pack()
                return
            self.var = tk.IntVar(value=-1)
            for i, cand in enumerate(slice):
                idx = start + i
                f = tk.Frame(self.frame, relief='groove', bd=1)
                f.pack(side='left', padx=6, pady=4)
                if PIL_AVAILABLE and cand.get('image_url'):
                    # Place a placeholder so the dialog shows immediately
                    lbl = tk.Label(f, text='[loading image]')
                    lbl.pack()
                    # Ensure UI updates so the Toplevel is visible before network fetch
                    try:
                        self.top.update_idletasks()
                    except Exception:
                        pass
                    # Try to fetch and display the image (network may block briefly)
                    try:
                        resp = requests.get(cand['image_url'], timeout=6)
                        resp.raise_for_status()
                        img = Image.open(io.BytesIO(resp.content))
                        img.thumbnail((420, 600))
                        photo = ImageTk.PhotoImage(img)
                        lbl.config(image=photo, text='')
                        lbl.image = photo
                        self.photo_refs.append(photo)
                    except Exception:
                        lbl.config(text='[no image]')
                else:
                    tk.Label(f, text='[no image]').pack()
                title = cand.get('exact_title', '')
                author = cand.get('author', '')
                pub = cand.get('publish_date', '')
                tk.Radiobutton(f, text=f"{title}\n{author} ({pub})", variable=self.var, value=idx, wraplength=180, justify='left').pack()

        def on_more(self):
            self.page += 1
            self.render_page()

        def on_none(self):
            self.none_selected = True
            self.top.destroy()
            self.top.update()  # Force update to remove window from screen

        def on_cancel(self):
            self.selected_idx = None
            self.top.destroy()
            self.top.update()  # Force update to remove window from screen

        def on_ok(self):
            val = self.var.get()
            if val is not None and val >= 0:
                self.selected_idx = val
            self.top.destroy()
            self.top.update()  # Force update to remove window from screen

    dlg = ManualMatchDialog(root, book_name, candidates)

    if getattr(dlg, 'none_selected', False):
        return None
    if getattr(dlg, 'selected_idx', None) is not None:
        return candidates[dlg.selected_idx]
    return None

def process_book_csv(input_file, book_column, output_file=None, delay=0.5, no_confirm=False,
                     auto_score_threshold=0.80, gap_threshold=0.12):
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
    df['ratings_count'] = 0
    df['goodreads_link'] = ''
    
    
    for index, row in tqdm(df.iterrows(), total=total, desc="Enriching with Goodreads data"):
        book_name = row[book_column]
        if pd.isna(book_name) or book_name == '':
            continue
        candidates = search_goodreads(book_name)
        chosen = None
        if not candidates:
            chosen = {'exact_title': '', 'author': '', 'publish_date': '', 'ratings_count': 0, 'goodreads_url': ''}
        elif len(candidates) == 1:
            chosen = candidates[0]
        else:
            # Compute similarity scores between query and candidate titles
            titles = [c['exact_title'] for c in candidates]
            norm_query = normalize_title(book_name)
            scores = []
            for t in titles:
                nt = normalize_title(t)
                if RAPIDFUZZ_AVAILABLE:
                    # token_set_ratio is robust to reorderings and extra tokens
                    s = fuzz.token_set_ratio(norm_query, nt) / 100.0
                else:
                    # fallback: combine token jaccard with sequence matcher ratio
                    q_tokens = set(norm_query.split())
                    t_tokens = set(nt.split())
                    if q_tokens or t_tokens:
                        inter = len(q_tokens & t_tokens)
                        union = len(q_tokens | t_tokens)
                        jacc = inter / union if union else 0.0
                    else:
                        jacc = 0.0
                    seq = difflib.SequenceMatcher(None, norm_query, nt).ratio()
                    s = 0.6 * jacc + 0.4 * seq
                scores.append(s)
            # If top match is clearly better than second, or is very high absolute score, auto-select it
            sorted_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
            top_idx = sorted_idx[0]
            top = scores[top_idx]
            second = scores[sorted_idx[1]] if len(scores) > 1 else 0
            if no_confirm or top >= auto_score_threshold or (top - second) >= gap_threshold:
                chosen = candidates[top_idx]
            else:
                # Show candidates ordered by score in the image dialog (it pages in sets of 3)
                ordered_candidates = [candidates[i] for i in sorted_idx]

                selected = ask_user_choice_with_images(root, book_name, ordered_candidates)
                if selected:
                    chosen = selected
                else:
                    chosen = {'exact_title': '', 'author': '', 'publish_date': '', 'ratings_count': 0, 'goodreads_url': ''}

        df.loc[index, 'exact_book_name'] = chosen.get('exact_title', '')
        df.loc[index, 'author'] = chosen.get('author', '')
        df.loc[index, 'publish_date'] = chosen.get('publish_date', '')
        df.loc[index, 'ratings_count'] = chosen.get('ratings_count', 0)
        df.loc[index, 'goodreads_link'] = chosen.get('goodreads_url', '')
        time.sleep(delay)
        
    # Save to output file
    if output_file is None:
        output_file = input_file.replace('.csv', '_with_goodreads.csv')
    df.to_csv(output_file, index=False)
    print(f"Results saved to: {output_file}")
    return df

if __name__ == "__main__":
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

    # Let the user pick the column from a list instead of typing it
    class ColumnSelectDialog(simpledialog.Dialog):
        def __init__(self, parent, columns, title=None):
            self.columns = columns
            self.selected = None
            super().__init__(parent, title=title)

        def body(self, master):
            tk.Label(master, text="Select the column that contains book titles:").pack(padx=8, pady=(8, 0))
            self.listbox = tk.Listbox(master, selectmode=tk.SINGLE, exportselection=False)
            for col in self.columns:
                self.listbox.insert(tk.END, col)
            self.listbox.pack(padx=8, pady=8, fill=tk.BOTH, expand=True)
            # Select first item by default
            if self.columns:
                self.listbox.selection_set(0)
            # Bind double-click to accept
            self.listbox.bind('<Double-Button-1>', lambda e: self.ok())
            return self.listbox

        def apply(self):
            sel = self.listbox.curselection()
            if sel:
                self.selected = self.columns[sel[0]]
            
            self.destroy()
            self.update()  # Force update to remove window from screen

        def validate(self):
            # Always valid (there is at least one item)
            return True

    dialog = ColumnSelectDialog(root, columns, title="Book Column")
    book_column = dialog.selected if getattr(dialog, 'selected', None) else columns[0]

    # Ask user to select output file (optional)
    output_file = input_file.replace('.csv', '_with_goodreads.csv')

    # Parse optional command-line flags (e.g., to disable interactive confirmations)
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--no-confirm', action='store_true', help='Skip manual confirmation for ambiguous matches')
    parser.add_argument('--auto-score', type=float, default=0.80, help='Absolute score threshold (0-1) to auto-select top match')
    parser.add_argument('--gap-threshold', type=float, default=0.12, help='Minimum gap between top and second score to auto-select')
    args, _ = parser.parse_known_args()

    try:
        process_book_csv(
            input_file,
            book_column,
            output_file,
            no_confirm=args.no_confirm,
            auto_score_threshold=args.auto_score,
            gap_threshold=args.gap_threshold,
        )
    except KeyboardInterrupt:
        print('\nInterrupted by user. Cleaning up...')
        try:
            root.destroy()
        except Exception:
            pass
        sys.exit(1)
    finally:
        # Always attempt to destroy the root window to ensure no Tk resources remain
        try:
            root.destroy()
        except Exception:
            pass