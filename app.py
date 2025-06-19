
import streamlit as st
import requests
from datetime import datetime, timedelta
from GoogleNews import GoogleNews
from openai import OpenAI  # Import the new OpenAI class
import os
import json
import pandas as pd

# --- Initialize Clients ---
# Load secrets and initialize the OpenAI client once
# This is more efficient than setting the API key on every function call
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    APIFY_TOKEN = st.secrets["APIFY_API_TOKEN"]
except KeyError as e:
    st.error(f"Could not find secret: {e}. Please check your .streamlit/secrets.toml file.")
    st.stop()


# ---------- Utility Functions ----------

def fetch_news(topic: str, num_articles: int):
    googlenews = GoogleNews(lang='en')
    googlenews.search(topic)
    result = googlenews.results(sort=True)
    return result[:num_articles]

# --- UPDATED FUNCTION ---
def extract_phrase_with_openai(headline: str):
    prompt = f"""
    Extract a concise, human-searchable phrase from this news headline:
    "{headline}"
    Only return the phrase. Do not include quotes or extra text.
    """
    try:
        # Use the new syntax: client.chat.completions.create
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        # The response structure has also changed slightly
        return response.choices[0].message.content.strip()
    except Exception as e:
        # It's helpful to print the actual error to the console for debugging
        print(f"Error calling OpenAI: {e}")
        # Optionally, display a more specific error in the UI
        st.warning(f"Could not generate phrase due to an API error: {e}")
        return "Could not generate phrase"

def fetch_tweets_from_apify(phrase):
    url = f"https://api.apify.com/v2/acts/kaitoeasyapi~twitter-x-data-tweet-scraper-pay-per-result-cheapest/run-sync-get-dataset-items?token={APIFY_TOKEN}"
    payload = {
        "twitterContent": phrase
    }
    headers = {
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        if response.status_code in [200, 201]:
            return response.json()
        else:
            st.error(f"Error {response.status_code}: {response.text}")
            return []
    except Exception as e:
        st.error(f"API Request Failed: {e}")
        return []

def compute_virality_score(tweets):
    if not tweets:
        return 0, "Low"

    valid_tweets = [t for t in tweets if isinstance(t, dict)]
    if not valid_tweets:
        return 0, "Low"

    total_impressions = sum(tweet.get("viewCount", 0) for tweet in valid_tweets)
    
    view_counts = [tweet.get("viewCount", 0) for tweet in valid_tweets if "viewCount" in tweet]
    if not view_counts:
        max_impressions = 0
    else:
        max_impressions = max(view_counts)

    if max_impressions > 50000:
        score = 90
        label = "High"
    elif total_impressions > 10000:
        score = 60
        label = "Medium"
    else:
        score = 30
        label = "Low"
    return score, label

# ---------- Streamlit UI ----------

st.set_page_config(page_title="Social Signal Bot", layout="wide")
st.title("📈 Social Signal Bot")

with st.sidebar:
    topic = st.text_input("Enter news topic", value="technology")
    num_articles = st.slider("Number of news articles", 1, 10, 5)
    run_bot = st.button("Run Bot")

if run_bot:
    st.subheader("🗞️ Top News and Virality Check")
    news = fetch_news(topic, num_articles)

    if not news:
        st.warning("No news found. Try a different topic.")
    else:
        for item in news:
            headline = item['title']
            link = item['link']
            st.markdown(f"### 📰 [{headline}]({link})")

            phrase = extract_phrase_with_openai(headline)
            st.markdown(f"**🔑 Phrase:** `{phrase}`")

            # Only proceed if a phrase was successfully generated
            if phrase != "Could not generate phrase":
                with st.expander("🔍 Twitter Data & Virality"):
                    with st.spinner(f"Searching for tweets about '{phrase}'..."):
                        tweets = fetch_tweets_from_apify(phrase)
                        score, label = compute_virality_score(tweets)
                        st.markdown(f"**Virality Score:** {score}/100 ({label})")

                        if tweets:
                            processed_tweets = []
                            for tweet in tweets:
                                if isinstance(tweet, dict):
                                    processed_tweets.append({
                                        "Tweet": tweet.get("text", "N/A"),
                                        "Author": tweet.get("author", {}).get("userName", "N/A"),
                                        "Views": tweet.get("viewCount", 0),
                                        "Likes": tweet.get("likeCount", 0),
                                        "Retweets": tweet.get("retweetCount", 0),
                                        "URL": tweet.get("url", "N/A")
                                    })
                            
                            df = pd.DataFrame(processed_tweets)
                            st.dataframe(df, use_container_width=True)
                        else:
                            st.info("No tweets found or an error occurred while fetching data.")
