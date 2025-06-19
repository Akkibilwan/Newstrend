# ----------------------- requirements.txt -----------------------
# streamlit
# openai
# requests
# googlenews
# pandas

# ----------------------- .streamlit/secrets.toml -----------------------
# [default]
# OPENAI_API_KEY = "your-openai-api-key"
# APIFY_TOKEN = "your-apify-token"

# ----------------------- app.py -----------------------
import streamlit as st
import requests
from datetime import datetime
import pandas as pd

# Load secrets
openai_key = st.secrets["OPENAI_API_KEY"]
apify_token = st.secrets["APIFY_TOKEN"]

st.set_page_config(page_title="Social Signal Bot", layout="wide")
st.title("📈 Social Signal Bot")

# Sidebar inputs
topic = st.sidebar.text_input("Enter a topic", value="technology")
num_articles = st.sidebar.slider("Number of news to analyze", 1, 10, 5)
run_bot = st.sidebar.button("🚀 Run Bot")

# ---- OpenAI Phrase Extraction ----
def extract_search_phrase_openai(headline: str) -> str:
    headers = {
        "Authorization": f"Bearer {openai_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-4",
        "temperature": 0.7,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a phrase extractor. Given a specific news headline, extract a unique, natural-sounding keyphrase "
                    "that best represents the search term people would use on Twitter or Reddit to find this news. "
                    "Avoid generic phrases. Return only the phrase."
                )
            },
            {"role": "user", "content": f"Headline: {headline}"}
        ]
    }
    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content'].strip('"')
    return ""

# ---- Fetch news headlines from Google News ----
def fetch_news(topic: str, num_articles: int):
    from GoogleNews import GoogleNews
    googlenews = GoogleNews(lang='en')
    googlenews.search(topic)
    result = googlenews.result()[:num_articles]
    return result

# ---- Fetch tweets from Apify Actor ----
@st.cache_data(show_spinner=False)
def fetch_twitter_data_raw(phrase):
    url = "https://api.apify.com/v2/acts/kaitoeasyapi~twitter-x-data-tweet-scraper-pay-per-result-cheapest/run-sync-get-dataset-items"
    try:
        response = requests.post(
            f"{url}?token={apify_token}",
            json={"twitterContent": phrase},
            timeout=90
        )
        if response.status_code != 200:
            return []
        return response.json()
    except Exception as e:
        st.error(f"Error contacting Apify: {e}")
        return []

# ---- Compute Twitter Virality Score ----
def compute_twitter_virality(df):
    if df.empty or "viewCount" not in df.columns:
        return 0, "Low"
    max_views = df["viewCount"].max()
    if max_views >= 100_000:
        return 90, "High"
    elif max_views >= 50_000:
        return 70, "Medium"
    else:
        return 30, "Low"

# ---- Main Bot Execution ----
if run_bot:
    st.info("⏳ Fetching news and analyzing social signals...")
    news_items = fetch_news(topic, num_articles)

    for idx, article in enumerate(news_items):
        st.markdown(f"### 📰 {idx + 1}. [{article['title']}]({article['link']})")

        phrase = extract_search_phrase_openai(article["title"])
        st.markdown(f"- 🔑 **Phrase:** `{phrase}`")

        twitter_json = fetch_twitter_data_raw(phrase)

        with st.expander("🔍 Raw Tweet Data from Apify"):
            if isinstance(twitter_json, list) and twitter_json:
                df = pd.DataFrame(twitter_json)
                st.dataframe(df)
                score, level = compute_twitter_virality(df)
                st.success(f"📊 Twitter Virality Score: **{score}/100** ({level})")
            else:
                st.warning("No tweet data received from Apify.")
