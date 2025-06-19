# requirements.txt
# streamlit
# openai
# requests
# googlenews
# python-dotenv

import streamlit as st
import requests
from datetime import datetime, timedelta
from GoogleNews import GoogleNews
import openai
import os

# Load OpenAI API Key from secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]
APIFY_TOKEN = st.secrets["APIFY_API_TOKEN"]

# ---------- Utility Functions ----------

def fetch_news(topic: str, num_articles: int):
    googlenews = GoogleNews(lang='en')
    googlenews.search(topic)
    result = googlenews.results(sort=True)
    return result[:num_articles]

def extract_phrase_with_openai(headline: str):
    prompt = f"""
    Extract a concise, human-searchable phrase from this news headline:
    "{headline}"
    Only return the phrase. Do not include quotes or extra text.
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        return "Could not generate phrase"

def fetch_tweets_from_apify(phrase):
    url = f"https://api.apify.com/v2/acts/kaitoeasyapi~twitter-x-data-tweet-scraper-pay-per-result-cheapest/run-sync-get-dataset-items?token={APIFY_TOKEN}"
    payload = {
        "twitterContent": phrase
    }
    try:
        response = requests.post(url, json=payload, timeout=120)
        if response.status_code == 200:
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

    total_impressions = sum(tweet.get("viewCount", 0) for tweet in tweets)
    max_impressions = max(tweet.get("viewCount", 0) for tweet in tweets)

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

            with st.expander("🔍 Twitter Data & Virality"):
                tweets = fetch_tweets_from_apify(phrase)
                score, label = compute_virality_score(tweets)
                st.markdown(f"**Virality Score:** {score}/100 ({label})")

                if tweets:
                    tweet_table = [{
                        "Tweet": tweet.get("text", ""),
                        "Views": tweet.get("viewCount", 0),
                        "Likes": tweet.get("likeCount", 0),
                        "Retweets": tweet.get("retweetCount", 0),
                        "URL": tweet.get("url", "")
                    } for tweet in tweets]
                    st.write(tweet_table)
                else:
                    st.info("No tweets found or error fetching data.")
