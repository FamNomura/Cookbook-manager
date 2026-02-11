import streamlit as st
from github import Github
from PIL import Image
import io
import datetime

# --- 設定 ---
st.set_page_config(page_title="レシピ投稿", page_icon="🍳")

# GitHubへの接続とカテゴリ取得（キャッシュ機能付き）
# 毎回アクセスすると遅いため、10分間(600秒)データを保存します
@st.cache_data(ttl=600)
def get_existing_categories():
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo_name = st.secrets["REPO_NAME"]
        g = Github(token)
        repo = g.get_repo(repo_name)
        
        # リポジトリ内の全ファイルツリーを取得
        contents = repo.get_git_tree("main", recursive=True).tree
        
        categories = set()
        for content in contents:
            # docs/ 以下のフォルダを探す（imagesと隠しファイルは除外）
            if content.path.startswith("docs/") and content.type == "tree":
                cat_name = content.path.replace("docs/", "")
                if cat_name != "images" and not cat_name.startswith("."):
                    categories.add(cat_name)
        
        return sorted(list(categories))
    except Exception as e:
        # エラー時はデフォルト値を返す
        return ["主菜", "副菜"]

# テキスト整形関数：改行区切りのテキストをMarkdownリストに変換
def format_ingredients(text):
    if not text: return ""
    lines = text.strip().split('\n')
    formatted = []
    for line in lines:
        line = line.strip()
        if line:
            # 行頭に "* " を付与
            formatted.append(f"* {line}")
    return "\n".join(formatted)

def format_steps(text):
    if not text: return ""
    lines = text.strip().split('\n')
    formatted = []
    for i, line in enumerate(lines):
        line = line.strip()
        if line:
            # 行頭に "1. ", "2. " を付与
            formatted.append(f"{i+1}. {line}")
    return "\n".join(formatted)

# --- UI構築 ---
st.title("🍳 レシピ投稿アプリ Ver.2")

# カテゴリの読み込み
with st.spinner("カテゴリを読み込んでいます..."):
    existing_cats = get_existing_categories()

# フォーム開始
with st.form("recipe_form"):
    # 1. 料理名
    title = st.text_input("料理名", placeholder="例：豚の角煮")
    
    # 2. カテゴリ選択（新規作成機能付き）
    cat_options = existing_cats + ["➕ 新しいカテゴリを追加"]
    selected_cat = st.selectbox("カテゴリ", cat_options)
    
    new_cat_name = ""
    if selected_cat == "➕ 新しいカテゴリを追加":
        new_cat_name = st.text_input("新しいカテゴリ名を入力", placeholder="例：イベント料理/クリスマス")
        final_category = new_cat_name
    else:
        final_category = selected_cat

    # 3. 画像
    uploaded_file = st.file_uploader("料理の写真", type=['jpg', 'jpeg', 'png'])

    # 4. 材料（自動整形）
    st.markdown("### 材料")
    st.caption("改行で区切って入力してください（記号は不要）")
    raw_ingredients = st.text_area("材料入力", placeholder="豚肉 200g\n玉ねぎ 1個\n醤油 大さじ1", height=150, label_visibility="collapsed")

    # 5. 手順（自動整形）
    st.markdown("### 手順")
    st.caption("改行で区切って入力してください（番号は自動でつきます）")
    raw_steps = st.text_area("手順入力", placeholder="材料を切る\nフライパンで焼く\n蓋をして蒸す", height=150, label_visibility="collapsed")

    # 6. メモ
    memo = st.text_area("メモ・ポイント", placeholder="コツや代用食材など")

    submitted = st.form_submit_button("レシピを投稿する", type="primary")

# --- 送信処理 ---
if submitted:
    if not title:
        st.error("エラー：料理名を入力してください")
    elif not final_category:
        st.error("エラー：カテゴリを指定してください")
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
                    # 画像のリサイズ (長辺1200px)
                    max_size = 1200
                    if max(image.size) > max_size:
                        image.thumbnail((max_size, max_size))
                    
                    # JPEG変換・圧縮
                    img_byte_arr = io.BytesIO()
                    # RGBA(透過PNG)の場合はRGBに変換
                    if image.mode in ("RGBA", "P"): 
                        image = image.convert("RGB")
                    
                    image.save(img_byte_arr, format='JPEG', quality=80, optimize=True)
                    img_byte_arr = img_byte_arr.getvalue()
                    
                    # ファイル名生成 (タイムスタンプ)
                    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
                    img_filename = f"img_{timestamp}.jpg"
                    
                    repo.create_file(
                        path=f"docs/images/{img_filename}",
                        message=f"Add image for {title}",
                        content=img_byte_arr
                    )
                    image_path = f"../images/{img_filename}"

                # B. テキスト整形とMarkdown生成
                formatted_ingredients = format_ingredients(raw_ingredients)
                formatted_steps = format_steps(raw_steps)

                md_content = f"# {title}\n\n"
                if image_path:
                    md_content += f"![{title}]({image_path})\n\n"
                
                md_content += f"## 材料\n{formatted_ingredients}\n\n"
                md_content += f"## 手順\n{formatted_steps}\n\n"
                if memo:
                    md_content += f"## メモ\n{memo}\n"

                # C. Markdownファイル作成
                # カテゴリ内のスラッシュもそのままパスとして認識される
                file_path = f"docs/{final_category}/{title}.md"
                
                repo.create_file(
                    path=file_path,
                    message=f"Add recipe: {title}",
                    content=md_content
                )
                
                # キャッシュをクリア（次回のリロードで新カテゴリを反映させるため）
                st.cache_data.clear()
                
                st.balloons()
                st.success(f"投稿完了！\n\nカテゴリ: {final_category}\n料理名: {title}")

        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
