import streamlit as st
import requests
import google.generativeai as genai
import time

# 1. 페이지 설정
st.set_page_config(page_title="Steam Review Analyzer (Global)", page_icon="🎮", layout="wide")
st.title("🎮 Steam 리뷰 심층 분석기 (Global Ver.)")
st.markdown("""
App ID만 입력하면 **유저 피드백과 개선점**을 심층 분석합니다.
Select language in the sidebar to change the report language.
""")

# ==========================================
# 2. 사이드바 설정 (언어 선택 기능 추가!)
# ==========================================
with st.sidebar:
    st.header("⚙️ Settings")
    
    # 🌍 언어 선택 버튼 (여기가 핵심!)
    report_lang = st.radio(
        "Report Language / 분석 언어",
        ["🇰🇷 한국어", "🇺🇸 English"],
        index=0
    )
    
    st.divider()

    # API 키 처리
    api_key = None
    try:
        if "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
            st.success(f"✅ API Key Loaded ({report_lang})")
    except:
        pass

    if not api_key:
        api_key = st.text_input("Gemini API Key", type="password")
        if not api_key:
            st.warning("Please enter API Key first.")
    
    target_count = st.slider("Review Count / 분석 개수", 50, 500, 200)

# 3. 데이터 수집 함수 (기존과 동일)
def collect_reviews(app_id, target_count):
    reviews = []
    cursor = '*'
    params = {'json': 1, 'filter': 'updated', 'language': 'all', 'num_per_page': 100}
    
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    while len(reviews) < target_count:
        params['cursor'] = cursor
        try:
            response = requests.get(f"https://store.steampowered.com/appreviews/{app_id}", params=params, timeout=10)
            data = response.json()
        except:
            break
            
        if 'reviews' not in data or not data['reviews']: break

        for review in data['reviews']:
            content = review['review'].replace("\n", " ").strip()
            if len(content) < 30: continue 
            
            playtime = int(review['author']['playtime_forever']/60)
            vote = 'Recommended' if review['voted_up'] else 'Not Recommended'
            reviews.append(f"[{playtime}h] {vote}: {content}")
            
            current_len = len(reviews)
            status_text.text(f"🔍 Collecting... {current_len} reviews")
            progress_bar.progress(min(current_len / target_count, 1.0))
            
            if current_len >= target_count: break
        
        cursor = data.get('cursor')
        if not cursor: break
    
    status_text.empty()
    progress_bar.empty()
    return reviews

# 4. AI 분석 함수 (언어에 따라 프롬프트 자동 변경)
def analyze_gemini(api_key, reviews, lang_option):
    genai.configure(api_key=api_key)
    
    # 모델 자동 선택
    available_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
    except:
        return "❌ Error: API Key is invalid."

    target_model = ""
    if 'models/gemini-1.5-flash' in available_models: target_model = 'gemini-1.5-flash'
    elif 'models/gemini-pro' in available_models: target_model = 'gemini-pro'
    elif available_models: target_model = available_models[0].replace('models/', '')
    else: return "❌ No available models found."

    model = genai.GenerativeModel(target_model)
    full_text = "\n".join(reviews)
    
    # 🇰🇷 한국어 프롬프트
    prompt_kr = f"""
    너는 글로벌 게임사의 시니어 UX 리서처이자 제품 전략가야. 
    아래 Steam 리뷰 데이터를 분석하여 '제품 개선을 위한 핵심 지표'를 도출해줘.

    [분석 가이드라인]
    1. 언어 통합: 리뷰 원문 언어와 상관없이 내용을 통합하여 분석할 것.
    2. 경쟁작 비교: 다른 게임과 비교하는 내용을 반드시 찾아서 인용할 것.
    3. 개선 제안 (IF 분석): "~하면 좋을 텐데" 같은 유저의 아쉬움과 제안을 시스템적으로 정리할 것.

    [결과 리포트 양식]
    1. 🔍 **경쟁사 대비 비교 분석**: 타 게임 언급 사례 및 우위/열위 포인트.
    2. 💡 **구체적 개선 제안 TOP 3**: 유저들이 가장 원하는 기능/시스템 변경사항.
    3. 📉 **치명적 이탈 요인 (Pain Points)**: 유저가 게임을 접게 만드는 결정적 원인.
    4. 🧩 **시스템적 제언**: 개발팀에게 전달할 한 줄 요약.

    [데이터]
    {full_text}
    """

    # 🇺🇸 English Prompt (For Global Reporting)
    prompt_en = f"""
    You are a Senior UX Researcher and Product Strategist at a global game company.
    Analyze the Steam review data below to derive 'key indicators for product improvement'.
    
    [Analysis Guidelines]
    1. Cross-Language Analysis: Analyze the context regardless of the original review language.
    2. Competitor Comparison: Identify and cite specific comparisons with other games (e.g., "Unlike Game X...").
    3. Improvement Suggestions (IF Analysis): Extract constructive feedback like "It would be better if..." or "I wish this system was..."

    [Report Format]
    **OUTPUT MUST BE IN ENGLISH.**
    
    1. 🔍 **Competitor Analysis**: Mentions of other games and comparative pros/cons.
    2. 💡 **Top 3 Improvement Requests**: Specific system/feature changes requested by users.
    3. 📉 **Critical Churn Factors (Pain Points)**: Decisive reasons why users quit the game.
    4. 🧩 **Systemic Recommendations**: A one-line summary for the development team.

    [Data]
    {full_text}
    """
    
    # 선택된 언어에 따라 프롬프트 결정
    final_prompt = prompt_en if "English" in lang_option else prompt_kr
    
    return model.generate_content(final_prompt).text

# ==========================================
# 5. 메인 실행 화면
# ==========================================
st.divider()

app_id = st.text_input("Steam App ID (ex: 413150)", placeholder="Type App ID here")

if st.button("🚀 Analyze / 분석 시작", type="primary", use_container_width=True):
    if not api_key:
        st.error("⚠️ Please enter API Key in the sidebar.")
    elif not app_id:
        st.warning("⚠️ Please enter App ID.")
    else:
        with st.spinner("Collecting data & Analyzing..."):
            data_list = collect_reviews(app_id, target_count)
            if data_list:
                # 함수 호출 시 언어 옵션도 같이 전달
                report = analyze_gemini(api_key, data_list, report_lang)
                
                st.markdown("---")
                st.subheader(f"📊 Analysis Report ({report_lang})")
                st.write(report)
                
                st.download_button("💾 Download Report", report, f"Report_{app_id}_{report_lang}.txt")
            else:
                st.error("No reviews found. Check App ID.")
