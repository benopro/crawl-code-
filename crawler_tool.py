import os
import random
import sqlite3
import logging
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template_string
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# Flask app
app = Flask(__name__)

# Setup logging
logging.basicConfig(
    filename="crawler.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

DATABASE = "crawler_data.db"

# SQLite setup
def setup_database():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crawled_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            href TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def fetch_url_requests(url, headers=None, retries=3):
    for attempt in range(retries):
        try:
            logging.info(f"Fetching URL: {url}, attempt {attempt + 1}")
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            with open("last_page.html", "w", encoding="utf-8") as f:
                f.write(response.text)
            return response.text
        except requests.exceptions.RequestException as e:
            logging.warning(f"Request failed for {url}, retry {attempt + 1}/{retries}: {e}")
    logging.error(f"Failed to fetch {url} after {retries} retries.")
    return None

def parse_html(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    data = []
    headings = soup.find_all(["h2", "h3"])
    logging.info(f"Found {len(headings)} headings in the page.")

    for heading in headings:
        if heading.get("id"):  # Chỉ lấy các thẻ có id (tiêu đề mục)
            title = heading.get_text(strip=True)
            content = []
            sibling = heading.find_next_sibling()
            while sibling and sibling.name not in ["h2", "h3"]:
                if sibling.name == "p":
                    content.append(sibling.get_text(strip=True))
                elif sibling.name == "ul":
                    for li in sibling.find_all("li"):
                        content.append(li.get_text(strip=True))
                sibling = sibling.find_next_sibling()
            data.append({
                "title": title,
                "content": " ".join(content),
                "href": f"{base_url}#{heading.get('id')}"
            })
    logging.info(f"Extracted {len(data)} sections from the page.")
    return data

def save_to_database(data):
    if not data:
        logging.warning("No data to save!")
        return
    logging.info(f"Saving {len(data)} items to the database.")
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.executemany(
        "INSERT INTO crawled_data (title, content, href) VALUES (:title, :content, :href)", data
    )
    conn.commit()
    conn.close()
    logging.info("Data saved successfully.")

@app.route("/")
def dashboard():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT title, content, href FROM crawled_data")
    rows = cursor.fetchall()
    conn.close()
    template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Crawled Data</title>
    </head>
    <body>
        <h1>Crawled Data</h1>
        <table border="1">
            <tr>
                <th>Title</th>
                <th>Content</th>
                <th>Link</th>
            </tr>
            {% for row in data %}
            <tr>
                <td>{{ row[0] }}</td>
                <td>{{ row[1] }}</td>
                <td><a href="{{ row[2] }}" target="_blank">Link</a></td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    """
    return render_template_string(template, data=rows)

@app.route("/api/crawled_data")
def api_data():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT title, content, href FROM crawled_data")
    rows = cursor.fetchall()
    conn.close()
    return jsonify([{"title": row[0], "content": row[1], "href": row[2]} for row in rows])

def crawl_wikipedia(urls, use_selenium=False):
    setup_database()
    headers = {"User-Agent": random.choice([
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36"
    ])}
    for url in urls:
        logging.info(f"Crawling URL: {url}")
        html = fetch_url_requests(url, headers)
        if html:
            base_url = url.split("#")[0]
            data = parse_html(html, base_url)
            save_to_database(data)
        else:
            logging.warning(f"Skipping URL: {url}")

if __name__ == "__main__":
    urls = [
        "https://en.wikipedia.org/wiki/Hide_(TV_series)"
    ]
    crawl_wikipedia(urls)
    app.run(host="0.0.0.0", port=5000, debug=True)
