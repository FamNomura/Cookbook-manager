import streamlit as st
from github import Github
from PIL import Image
import io
import datetime

# --- 設定 ---
st.set_page_config(page_title="レシピ投稿", page_icon="🍳")

# GitHubへの接続とカテゴリ取得（キャッシュ機能付き）
@st.cache_data(ttl=600)
def get_existing_categories():
    try:
        # シークレットが設定されていない場合の安全策
        if "GITHUB_TOKEN" not in st.secrets:
            return []
            
        token = st.secrets["GITHUB_TOKEN"]
        repo_name = st.secrets["REPO_NAME"]
        g = Github(token)
        repo = g.get_repo(repo_name)
        
        contents = repo.get_git_tree("main", recursive=True).tree
        
        categories = set()
        for content in contents:
            if content.path.startswith("docs/") and content.type == "tree":
                cat_name = content.path.replace("docs/", "")
                if cat_name != "images" and not cat_name.startswith("."):
                    categories.add(cat_name)
        
        return sorted(list(categories))
    except Exception as e:
        return []

# テキスト整形関数
def format_ingredients(text):
    if not text: return ""
    lines = text.strip().split('\n')
    formatted = []
    for line in lines:
        line = line.strip()
        if line:
            formatted.append(f"* {line}")
    return "\n".join(formatted)

def format_steps(text):
    if not text: return ""
    lines = text.strip().split('\n')
    formatted = []
    for i, line in enumerate(lines):
        line = line.strip()
        if line:
            formatted.append(f"{i+1}. {line}")
    return "\n".join(formatted)

# --- UI構築 ---
st.title("🍳 レシピ投稿アプリ Ver.2.1")

# カテゴリの読み込み
existing_cats = get_existing_categories()

# フォーム開始
with st.form("recipe_form"):
    # 1. 料理名
    title = st.text_input("料理名", placeholder="例：豚の角煮")
    
    # 2. カテゴリ選択（堅牢化：ラジオボタンで明示的にモード切替）
    st.markdown("### カテゴリ設定")
    cat_mode = st.radio("モード選択", ["既存から選ぶ", "新規作成する"], horizontal=True)
    
    final_category = ""
    
    if cat_mode == "既存から選ぶ":
        if existing_cats:
            final_category = st.selectbox("カテゴリ一覧", existing_cats)
        else:
            st.warning("既存のカテゴリが見つかりません。「新規作成する」を選んでください。")
    else:
        # 新規作成モード
        new_cat_input = st.text_input("新しいカテゴリ名を入力", placeholder="例：麺類/ラーメン")
        final_category = new_cat_input

    # 3. 画像
    uploaded_file = st.file_uploader("料理の写真", type=['jpg', 'jpeg', 'png'])

    # 4. 材料（自動整形）
    st.markdown("### 材料")
    st.caption("改行で区切って入力してください")
    raw_ingredients = st.text_area("材料入力", placeholder="豚肉 200g\n玉ねぎ 1個", height=150, label_visibility="collapsed")

    # 5. 手順（自動整形）
    st.markdown("### 手順")
    st.caption("改行で区切って入力してください（番号は自動でつきます）")
    raw_steps = st.text_area("手順入力", placeholder="切る\n焼く\n煮る", height=150, label_visibility="collapsed")

    # 6. メモ
    memo = st.text_area("メモ・ポイント", placeholder="コツや代用食材など")

    submitted = st.form_submit_button("レシピを投稿する", type="primary")

# --- 送信処理 ---
if submitted:
    if not title:
        st.error("エラー：料理名を入力してください")
    elif not final_category:
        st.error("エラー：カテゴリが空欄です")
    else:
        try:
            with st.spinner("送信中..."):
                token = st.secrets["GITHUB_TOKEN"]
                repo_name = st.secrets["REPO_NAME"]
                g = Github(token)
                repo = g.get_repo(repo_name)

                # A. 画像処理
                image_path = ""
                if uploaded_file:
                    image = Image.open(uploaded_file)
                    max_size = 1200
                    if max(image.size) > max_size:
                        image.thumbnail((max_size, max_size))
                    
                    img_byte_arr = io.BytesIO()
                    if image.mode in ("RGBA", "P"): 
                        image = image.convert("RGB")
                    
                    image.save(img_byte_arr, format='JPEG', quality=80, optimize=True)
                    img_byte_arr = img_byte_arr.getvalue()
                    
                    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
                    img_filename = f"img_{timestamp}.jpg"
                    
                    repo.create_file(
                        path=f"docs/images/{img_filename}",
                        message=f"Add image for {title}",
                        content=img_byte_arr
                    )
                    image_path = f"../images/{img_filename}"

                # B. テキスト整形
                formatted_ingredients = format_ingredients(raw_ingredients)
                formatted_steps = format_steps(raw_steps)

                md_content = f"# {title}\n\n"
                if image_path:
                    md_content += f"![{title}]({image_path})\n\n"
                
                md_content += f"## 材料\n{formatted_ingredients}\n\n"
                md_content += f"## 手順\n{formatted_steps}\n\n"
                if memo:
                    md_content += f"## メモ\n{memo}\n"

                # C. ファイル作成
                # カテゴリ末尾の余計な空白などを除去
                clean_category = final_category.strip().strip("/")
                file_path = f"docs/{clean_category}/{title}.md"
                
                repo.create_file(
                    path=file_path,
                    message=f"Add recipe: {title}",
                    content=md_content
                )
                
                st.cache_data.clear()
                st.balloons()
                st.success(f"投稿完了！\nカテゴリ: {clean_category} に保存しました。")

        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
