import streamlit as st
import requests
import google.generativeai as genai
import pandas as pd
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="Steam Review Analyzer (Pro)", page_icon="🎮", layout="wide")
st.title("🎮 Steam 리뷰 심층 분석기 (Pro Ver.)")
st.markdown("""
App ID를 입력하면 **AI 분석 리포트**와 **플레이 타임 통계 차트**를 제공합니다.
""")

# ==========================================
# 2. 사이드바 설정
# ==========================================
with st.sidebar:
    st.header("⚙️ Settings")
    
    report_lang = st.radio("언어 / Language", ["🇰🇷 한국어", "🇺🇸 English"], index=0)
    st.divider()

    api_key = None
    try:
        if "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
            st.success(f"✅ API Key Loaded")
    except:
        pass

    if not api_key:
        api_key = st.text_input("Gemini API Key", type="password")
    
    target_count = st.slider("분석 데이터 수", 100, 1000, 300)

# 3. 데이터 수집 함수 (차트용 데이터도 같이 수집!)
def collect_data(app_id, target_count):
    reviews_text = [] # AI에게 보낼 텍스트
    playtimes = []    # 차트 그릴 숫자 데이터
    
    cursor = '*'
    params = {'json': 1, 'filter': 'updated', 'language': 'all', 'num_per_page': 100}
    
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    while len(reviews_text) < target_count:
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
            
            # 시간 계산 (분 -> 시간)
            hours = int(review['author']['playtime_forever'] / 60)
            vote = 'Recommended' if review['voted_up'] else 'Not Recommended'
            
            # 1. AI용 텍스트 저장
            reviews_text.append(f"[{hours}h] {vote}: {content}")
            
            # 2. 차트용 데이터 저장 (딕셔너리 형태)
            playtimes.append({
                "Hours": hours,
                "Vote": vote,
                "Review Length": len(content)
            })
            
            current_len = len(reviews_text)
            status_text.text(f"🔍 Data Collecting... {current_len}")
            progress_bar.progress(min(current_len / target_count, 1.0))
            
            if current_len >= target_count: break
        
        cursor = data.get('cursor')
        if not cursor: break
    
    status_text.empty()
    progress_bar.empty()
    
    # 데이터프레임으로 변환 (차트 그리기 쉽게)
    df = pd.DataFrame(playtimes)
    return reviews_text, df

# 4. 차트 그리는 함수 (NEW!)
def draw_charts(df):
    # 구간(Bin) 설정: 0~10h, 10~50h, 50~100h, 100h+
    bins = [0, 10, 50, 100, 100000]
    labels = ['0~10h (Newbie)', '10~50h (Mid)', '50~100h (Core)', '100h+ (Hardcore)']
    
    df['User Type'] = pd.cut(df['Hours'], bins=bins, labels=labels, right=False)
    
    # 차트 1: 유저 분포 (파이 차트)
    user_counts = df['User Type'].value_counts().reset_index()
    user_counts.columns = ['User Type', 'Count']
    
    fig1 = px.pie(user_counts, values='Count', names='User Type', 
                  title='🎮 Playtime Distribution (리뷰어 플레이 성향)',
                  hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
    
    # 차트 2: 구간별 추천/비추천 비율 (바 차트)
    fig2 = px.histogram(df, x="User Type", color="Vote", 
                        title="📊 Vote Ratio by Playtime (구간별 평가)",
                        barmode='group', color_discrete_map={'Recommended':'#66C2A5', 'Not Recommended':'#FC8D62'})

    return fig1, fig2

# 5. AI 분석 함수 (이전과 동일)
def analyze_gemini(api_key, reviews, lang_option):
    genai.configure(api_key=api_key)
    
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
    
    prompt_kr = """
    너는 게임 데이터 분석가야. 아래 데이터를 바탕으로 인사이트를 도출해줘.
    [가이드라인]
    1. 경쟁작 비교 언급 추출.
    2. 유저들의 구체적인 개선 제안(IF 분석) 정리.
    3. 플레이 타임별(초반/중반/고인물) 여론의 온도차 분석.
    
    [데이터]
    """ + full_text

    prompt_en = """
    Analyze the Steam review data as a Game Data Analyst.
    [Guidelines]
    1. Extract comparisons with competitor games.
    2. Summarize specific improvement suggestions (IF analysis).
    3. Analyze the sentiment difference between new players vs. hardcore players.
    
    [Data]
    """ + full_text
    
    final_prompt = prompt_en if "English" in lang_option else prompt_kr
    return model.generate_content(final_prompt).text

# ==========================================
# 6. 메인 실행 화면
# ==========================================
st.divider()
app_id = st.text_input("Steam App ID (ex: 413150)", placeholder="Type App ID here")

if st.button("🚀 Analyze / 분석 시작", type="primary", use_container_width=True):
    if not api_key or not app_id:
        st.error("API Key와 App ID를 확인해주세요.")
    else:
        with st.spinner("Collecting & Analyzing..."):
            # 데이터 수집 (텍스트 + 데이터프레임)
            reviews_text, df = collect_data(app_id, target_count)
            
            if reviews_text:
                # 1. 차트 그리기 (위쪽에 배치)
                st.subheader("📈 Data Dashboard")
                fig1, fig2 = draw_charts(df)
                col1, col2 = st.columns(2)
                with col1: st.plotly_chart(fig1, use_container_width=True)
                with col2: st.plotly_chart(fig2, use_container_width=True)
                
                # 2. AI 분석
                report = analyze_gemini(api_key, reviews_text, report_lang)
                
                # 3. 결과 출력
                st.markdown("---")
                st.subheader(f"📝 AI Analysis Report ({report_lang})")
                st.write(report)
                
                st.download_button("💾 Report Download", report, f"Report_{app_id}.txt")
            else:
                st.error("No reviews found.")
