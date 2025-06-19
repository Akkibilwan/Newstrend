# app.py

import streamlit as st
import requests
from GoogleNews import GoogleNews
from keybert import KeyBERT
from typing import List, Dict

# -------------------- Streamlit Config --------------------
st.set_page_config(page_title="Social Signal Bot", layout="wide")
st.title("📡 Social Signal Bot")

# -------------------- Sidebar Inputs --------------------
st.sidebar.header("Configuration")
topic = st.sidebar.text_input("Enter a news topic", value="technology")
num_articles = st.sidebar.slider("Number of news articles", 1, 10, 5)
run = st.sidebar.button("Run Bot")

# -------------------- Caching Utilities --------------------
@st.cache_data(show_spinner=False)
def fetch_news(topic: str, count: int) -> List[str]:
    googlenews = GoogleNews(lang='en')
    googlenews.search(topic)
    articles = googlenews.result()[:count]
    return [a['title'] for a in articles]

@st.cache_resource
def get_kw_model():
    return KeyBERT()

@st.cache_data
def extract_keywords(texts: List[str], kw_model, top_n: int = 5) -> Dict[str, List[str]]:
    keywords_dict = {}
    for title in texts:
        keywords = [kw[0] for kw in kw_model.extract_keywords(title, top_n=top_n)]
        keywords_dict[title] = keywords
    return keywords_dict

@st.cache_data
def scrape_reddit(keyword: str, max_results: int = 5) -> List[Dict[str, str]]:
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://www.reddit.com/search.json?q={keyword}&limit={max_results}"
    response = requests.get(url, headers=headers)
    posts = []
    if response.status_code == 200:
        for post in response.json().get("data", {}).get("children", []):
            data = post.get("data", {})
            posts.append({
                "title": data.get("title", ""),
                "subreddit": data.get("subreddit", "")
            })
    return posts

# Safe Twitter Scraper Loader
def safe_scrape_tweets(keyword: str, max_results: int = 5) -> List[Dict[str, str]]:
    try:
        import snscrape.modules.twitter as sntwitter
        tweets = []
        for i, tweet in enumerate(sntwitter.TwitterSearchScraper(f"{keyword} lang:en").get_items()):
            if i >= max_results:
                break
            tweets.append({
                "username": tweet.user.username,
                "content": tweet.content
            })
        return tweets
    except Exception as e:
        st.warning(f"⚠️ Could not load tweets for '{keyword}': {e}")
        return []

# -------------------- Execution --------------------
if run:
    st.subheader("🔍 Fetching News")
    headlines = fetch_news(topic, num_articles)
    if not headlines:
        st.error("No headlines found.")
        st.stop()
    st.success(f"Fetched {len(headlines)} headlines")

    st.subheader("🧠 Extracting Keywords")
    kw_model = get_kw_model()
    keywords_dict = extract_keywords(headlines, kw_model)
    all_keywords = list({kw for kws in keywords_dict.values() for kw in kws})
    st.success(f"Extracted {len(all_keywords)} unique keywords")

    with st.expander("📰 Headlines & Keywords", expanded=True):
        for title, keywords in keywords_dict.items():
            st.markdown(f"**Headline:** {title}")
            st.markdown(f"`Keywords:` {', '.join(keywords)}")
            st.markdown("---")

    st.subheader("📲 Social Signals")

    tabs = st.tabs(["Twitter", "Reddit"])

    with tabs[0]:
        for kw in all_keywords:
            with st.expander(f"🐦 Tweets for: {kw}"):
                tweets = safe_scrape_tweets(kw)
                if not tweets:
                    st.info("No tweets found.")
                    continue
                for t in tweets:
                    st.markdown(f"- **@{t['username']}**: {t['content']}")

    with tabs[1]:
        for kw in all_keywords:
            with st.expander(f"👽 Reddit Posts for: {kw}"):
                posts = scrape_reddit(kw)
                if not posts:
                    st.info("No Reddit posts found.")
                    continue
                for p in posts:
                    st.markdown(f"- [{p['title']}] - r/{p['subreddit']}")

    st.balloons()
