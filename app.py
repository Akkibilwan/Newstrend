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
import json

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
    # The URL for running the actor and getting dataset items synchronously
    url = f"https://api.apify.com/v2/acts/kaitoeasyapi~twitter-x-data-tweet-scraper-pay-per-result-cheapest/run-sync-get-dataset-items?token={APIFY_TOKEN}"
    
    # CORRECTED PAYLOAD: The API expects twitterContent to be a string.
    payload = {
        "twitterContent": phrase 
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        # Make the POST request to the Apify API
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        
        # Check if the request was successful
        if response.status_code == 200:
            # The .json() method will parse the JSON response body into a Python list
            return response.json()
        else:
            # Display the specific error message from the API if available
            st.error(f"Error {response.status_code}: {response.text}")
            return []
            
    except Exception as e:
        st.error(f"API Request Failed: {e}")
        return []

def compute_virality_score(tweets):
    if not tweets:
        return 0, "Low"

    # Ensure all items in tweets are dictionaries before processing
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

            with st.expander("🔍 Twitter Data & Virality"):
                # Use a spinner to show that data is being fetched
                with st.spinner(f"Searching for tweets about '{phrase}'..."):
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
                        } for tweet in tweets if isinstance(tweet, dict)]
                        st.write(tweet_table)
                    else:
                        st.info("No tweets found or an error occurred while fetching data.")
