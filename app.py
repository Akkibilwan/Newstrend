# requirements.txt dependencies
# streamlit
# requests
# keybert
# googlenews
# sentence-transformers
# openai

import streamlit as st
import requests
from datetime import datetime, timedelta
from GoogleNews import GoogleNews
from keybert import KeyBERT
from openai import OpenAI
import time

# -----------------------------
# Setup
# -----------------------------
st.set_page_config(page_title="Social Signal Bot", layout="wide")
st.title("📡 Social Signal Bot")

# API secrets
oai_key = st.secrets.get("OPENAI_API_KEY", "")
apify_token = st.secrets.get("APIFY_TOKEN", "")

# -----------------------------
# Utility functions
# -----------------------------
@st.cache_data(show_spinner=False)
def fetch_news(topic: str, count: int):
    googlenews = GoogleNews(lang='en')
    googlenews.search(topic)
    results = googlenews.results()[:count]
    return results

@st.cache_resource(show_spinner=False)
def load_kw_model():
    return KeyBERT()

@st.cache_data(show_spinner=False)
def extract_phrases_openai(headline: str) -> str:
    headers = {
        "Authorization": f"Bearer {oai_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": "Extract a single, short, natural-sounding phrase from the news headline that could be searched on Twitter or Reddit."},
            {"role": "user", "content": headline}
        ]
    }
    resp = requests.post("https://api.openai.com/v1/chat/completions", json=data, headers=headers)
    if resp.status_code == 200:
        return resp.json()['choices'][0]['message']['content'].strip('"')
    else:
        return ""

@st.cache_data(show_spinner=False)
def fetch_reddit_posts(phrase: str):
    url = f"https://www.reddit.com/search.json?q={phrase}&limit=5&sort=top"
    headers = {"User-agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        posts = []
        for child in response.json().get("data", {}).get("children", []):
            post = child.get("data", {})
            posts.append({
                "title": post.get("title"),
                "subreddit": post.get("subreddit"),
                "score": post.get("score"),
                "url": f"https://reddit.com{post.get('permalink')}"
            })
        return posts
    except:
        return []

@st.cache_data(show_spinner=False)
def fetch_tweets_apify(phrase: str):
    url = f"https://api.apify.com/v2/acts/kaitoeasyapi~twitter-x-data-tweet-scraper-pay-per-result-cheapest/run-sync-get-dataset-items?token={apify_token}"
    payload = {"twitterContent": phrase}
    try:
        resp = requests.post(url, json=payload, timeout=60)
        tweets = []
        if resp.status_code == 200:
            for tweet in resp.json()[:5]:
                tweets.append({
                    "text": tweet.get("text", ""),
                    "username": tweet.get("user", {}).get("username", ""),
                    "likeCount": tweet.get("likeCount", 0),
                    "retweetCount": tweet.get("retweetCount", 0),
                    "url": tweet.get("url", "")
                })
        return tweets
    except:
        return []

def compute_virality(tweets, reddit_posts, total_news=5):
    twitter_score = 0
    reddit_score = 0

    for t in tweets:
        score = t['likeCount'] + t['retweetCount']
        if score > 500:
            twitter_score += 80
        elif score > 100:
            twitter_score += 50
        else:
            twitter_score += 20

    for r in reddit_posts:
        if r['score'] > 2000:
            reddit_score += 80
        elif r['score'] > 500:
            reddit_score += 50
        else:
            reddit_score += 20

    twitter_score = min(100, twitter_score)
    reddit_score = min(100, reddit_score)
    news_score = 10 if total_news > 3 else 5

    final = round((0.55 * twitter_score) + (0.35 * reddit_score) + (0.10 * news_score))
    return twitter_score, reddit_score, news_score, final


# -----------------------------
# Streamlit Sidebar
# -----------------------------
topic = st.sidebar.text_input("Enter a news topic", value="technology")
count = st.sidebar.slider("Number of top news to fetch", 1, 10, 5)
run = st.sidebar.button("🚀 Run Bot")

if run:
    with st.spinner("Fetching top news headlines..."):
        headlines = fetch_news(topic, count)

    st.success(f"Fetched {len(headlines)} news results for topic '{topic}'")

    for idx, news in enumerate(headlines):
        title = news.get("title", "No title")
        st.markdown(f"### 📰 {idx+1}. {title}")

        with st.spinner("Generating key phrase..."):
            phrase = extract_phrases_openai(title)
        st.markdown(f"**🔑 Phrase:** `{phrase}`")

        with st.spinner("Fetching Reddit posts..."):
            reddit_posts = fetch_reddit_posts(phrase)

        with st.spinner("Fetching Tweets via Apify..."):
            twitter_posts = fetch_tweets_apify(phrase)

        t_score, r_score, n_score, final_score = compute_virality(twitter_posts, reddit_posts, total_news=len(headlines))

        st.markdown(f"**🧪 Platform Scores**:")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Twitter", t_score)
        col2.metric("Reddit", r_score)
        col3.metric("News Count", n_score)
        col4.metric("🔥 Combined Score", final_score)

        if final_score >= 70:
            st.success("🟢 High Virality")
        elif final_score >= 40:
            st.warning("🟡 Medium Virality")
        else:
            st.error("🔴 Low Virality")

        with st.expander("🔗 Show Reddit Posts"):
            for r in reddit_posts:
                st.write(f"- [{r['title']}]({r['url']}) (r/{r['subreddit']}, 🔺{r['score']})")

        with st.expander("🐦 Show Tweets"):
            for t in twitter_posts:
                st.write(f"- @{t['username']}: {t['text']}  ")
                st.write(f"  ❤️ {t['likeCount']} | 🔁 {t['retweetCount']}  [🔗 View Tweet]({t['url']})")

        st.markdown("---")
