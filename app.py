import streamlit as st
from GoogleNews import GoogleNews
from keybert import KeyBERT
import requests
from datetime import datetime
from openai import OpenAI
from typing import List, Dict

st.set_page_config(page_title="News Virality Analyzer", layout="wide")
st.title("📰 News Virality Analyzer")

# -------------------- Sidebar Inputs --------------------
topic = st.sidebar.text_input("Enter a topic", value="technology")
run = st.sidebar.button("Run Virality Scan")

# -------------------- Loaders --------------------
@st.cache_resource
def load_keybert():
    return KeyBERT()

@st.cache_resource
def openai_client():
    return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# -------------------- News Fetcher --------------------
@st.cache_data
def fetch_top_news(topic: str, limit: int = 5) -> List[str]:
    googlenews = GoogleNews(lang='en')
    googlenews.search(topic)
    articles = googlenews.result()
    seen = set()
    titles = []
    for a in articles:
        title = a['title'].strip()
        if title and title not in seen:
            seen.add(title)
            titles.append(title)
        if len(titles) == limit:
            break
    return titles

# -------------------- Keyphrase Extractor --------------------
@st.cache_data
def extract_phrases(_kw_model, headlines: List[str]) -> Dict[str, List[str]]:
    result = {}
    for title in headlines:
        phrases = [kw[0] for kw in _kw_model.extract_keywords(
            title,
            keyphrase_ngram_range=(2, 4),
            stop_words='english',
            use_mmr=True,
            diversity=0.7,
            top_n=2
        )]
        result[title] = phrases
    return result

# -------------------- Reddit Real Search --------------------
def fetch_reddit_posts(phrase: str, max_results: int = 5) -> List[Dict]:
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://www.reddit.com/search.json?q={requests.utils.quote(phrase)}&limit={max_results}&sort=new"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        posts = response.json().get("data", {}).get("children", [])
        result = []
        for post in posts:
            data = post.get("data", {})
            created_utc = datetime.utcfromtimestamp(data.get("created_utc", 0))
            if (datetime.utcnow() - created_utc).days <= 4:
                result.append({
                    "title": data.get("title", ""),
                    "subreddit": data.get("subreddit", ""),
                    "upvotes": data.get("score", 0),
                    "url": "https://reddit.com" + data.get("permalink", "")
                })
        return result
    except:
        return []

# -------------------- OpenAI Virality Estimator --------------------
def estimate_virality_with_openai(phrase: str) -> Dict[str, int]:
    client = openai_client()
    prompt = f"""
You are a social media analyst. Based on public data, estimate the virality of the following phrase:

Phrase: "{phrase}"
Time window: last 4 days
Platforms: Twitter only (Reddit will be real data)

Return a JSON object like:
{{
  "twitter_score": 0-100,
  "reason": "Short explanation why"
}}
Respond ONLY with the JSON.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200
        )
        reply = response.choices[0].message.content.strip()
        return eval(reply) if reply.startswith("{") else {"twitter_score": 0, "reason": "GPT parsing failed"}
    except Exception as e:
        return {"twitter_score": 0, "reason": str(e)}

# -------------------- Scoring --------------------
def compute_virality(t_score: int, r_score: int) -> Dict:
    combined = round((t_score * 0.55) + (r_score * 0.35), 1)
    label = "🔴 Low"
    if t_score >= 80 or r_score >= 80:
        label = "🟢 High"
    elif (t_score >= 50 and r_score >= 50) or combined >= 60:
        label = "🟡 Medium"
    return {"score": combined, "label": label}

# -------------------- MAIN --------------------
if run:
    st.subheader("📰 Step 1: Fetching News...")
    headlines = fetch_top_news(topic)
    if not headlines:
        st.error("No news found.")
        st.stop()
    st.success(f"Fetched {len(headlines)} headlines")

    st.subheader("🔍 Step 2: Extracting Searchable Phrases...")
    kw_model = load_keybert()
    phrase_dict = extract_phrases(_kw_model=kw_model, headlines=headlines)

    st.subheader("🧠 Step 3: Estimating Virality and Showing Sources")
    for title in headlines:
        phrases = phrase_dict.get(title, [])
        twitter_score = 0
        reddit_score = 0
        reason = "No signals detected"
        all_reddit_posts = []

        for phrase in phrases:
            twitter_data = estimate_virality_with_openai(phrase)
            twitter_score = max(twitter_score, twitter_data.get("twitter_score", 0))
            reason = twitter_data.get("reason", "")

            posts = fetch_reddit_posts(phrase)
            all_reddit_posts.extend(posts)
            for p in posts:
                if p['upvotes'] > 2000:
                    reddit_score = max(reddit_score, 90)

        final = compute_virality(twitter_score, reddit_score)

        with st.container():
            st.markdown(f"### 🗞️ {title}")
            st.markdown(f"**Key Phrases:** `{', '.join(phrases)}`")
            st.markdown(f"**OpenAI Reasoning:** {reason}")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label="🐦 Twitter Score", value=twitter_score)
            with col2:
                st.metric(label="👽 Reddit Score", value=reddit_score)
            with col3:
                st.metric(label="🔥 Overall", value=final['label'])

            if all_reddit_posts:
                with st.expander("🔗 Show Reddit Posts"):
                    for post in all_reddit_posts:
                        st.markdown(f"- [{post['title']}]({post['url']}) (r/{post['subreddit']}, 🔼 {post['upvotes']})")
            st.markdown("---")

    st.balloons()
