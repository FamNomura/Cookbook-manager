import streamlit as st
from github import Github, UnknownObjectException
from PIL import Image
import io
import datetime
import re

# --- 設定 ---
st.set_page_config(page_title="レシピ投稿", page_icon="🍳")

# セッション状態の初期化 (編集データの保持用)
if 'form_title' not in st.session_state: st.session_state.form_title = ""
if 'form_ingredients' not in st.session_state: st.session_state.form_ingredients = ""
if 'form_steps' not in st.session_state: st.session_state.form_steps = ""
if 'form_memo' not in st.session_state: st.session_state.form_memo = ""
if 'current_image_path' not in st.session_state: st.session_state.current_image_path = ""

# --- 関数定義 ---

@st.cache_data(ttl=600)
def get_existing_categories():
    try:
        if "GITHUB_TOKEN" not in st.secrets: return []
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
    except:
        return []

def get_files_in_category(category):
    """指定カテゴリ内のMarkdownファイル一覧を取得"""
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo_name = st.secrets["REPO_NAME"]
        g = Github(token)
        repo = g.get_repo(repo_name)
        path = f"docs/{category}"
        contents = repo.get_contents(path)
        files = [c.name for c in contents if c.name.endswith(".md")]
        return files
    except:
        return []

def parse_markdown_to_form(md_text):
    """Markdownテキストを解析してフォーム用のテキストに戻す"""
    # タイトル抽出 (# Title)
    title_match = re.search(r'^#\s+(.+)$', md_text, re.MULTILINE)
    title = title_match.group(1) if title_match else ""

    # 画像パス抽出 (![alt](path))
    image_match = re.search(r'!\[.*?\]\((.*?)\)', md_text)
    image_path = image_match.group(1) if image_match else ""

    # セクション分割
    sections = re.split(r'^##\s+', md_text, flags=re.MULTILINE)
    
    ingredients = ""
    steps = ""
    memo = ""

    for section in sections:
        if section.startswith("材料"):
            # "* " を削除して元のテキストに戻す
            lines = section.replace("材料\n", "").strip().split('\n')
            clean_lines = [line.strip().lstrip('* ').strip() for line in lines if line.strip()]
            ingredients = "\n".join(clean_lines)
        elif section.startswith("手順"):
            # "1. " などの数字を削除して元のテキストに戻す
            lines = section.replace("手順\n", "").strip().split('\n')
            clean_lines = [re.sub(r'^\d+\.\s*', '', line).strip() for line in lines if line.strip()]
            steps = "\n".join(clean_lines)
        elif section.startswith("メモ"):
            # メモはそのまま（ただし改行コードの処理に注意）
            raw_memo = section.replace("メモ\n", "").strip()
            # Markdown改行(space space newline)を通常の改行に戻す
            memo = raw_memo.replace("  \n", "\n")

    return title, image_path, ingredients, steps, memo

def format_list(text, is_ordered=False):
    """テキストをMarkdownリストに変換"""
    if not text: return ""
    lines = text.strip().split('\n')
    formatted = []
    for i, line in enumerate(lines):
        line = line.strip()
        if line:
            prefix = f"{i+1}. " if is_ordered else "* "
            formatted.append(f"{prefix}{line}")
    return "\n".join(formatted)

# --- UI構築 ---
st.title("🍳 レシピ管理システム Ver.4.0")

# モード選択
mode = st.radio("操作を選択", ["新規作成", "既存レシピを編集"], horizontal=True)

existing_cats = get_existing_categories()
final_category = ""
target_filename = "" # 編集時のファイル名

# --- カテゴリ・ファイル選択エリア ---
st.subheader("① 対象の選択")

if mode == "新規作成":
    # 新規作成モードのカテゴリ選択
    cat_mode = st.radio("カテゴリ入力", ["既存から選ぶ", "新規作成する"], horizontal=True, key="new_cat_mode")
    if cat_mode == "既存から選ぶ":
        if existing_cats:
            final_category = st.selectbox("カテゴリ一覧", existing_cats, key="new_cat_select")
        else:
            st.warning("カテゴリがありません。新規作成してください。")
    else:
        final_category = st.text_input("新しいカテゴリ名", placeholder="例：調味料/タレ")
    
    # 新規モードになったらフォームをクリア（一度だけ実行）
    if st.session_state.get('last_mode') != 'new':
        st.session_state.form_title = ""
        st.session_state.form_ingredients = ""
        st.session_state.form_steps = ""
        st.session_state.form_memo = ""
        st.session_state.current_image_path = ""
        st.session_state.last_mode = 'new'

else:
    # 編集モード
    if existing_cats:
        select_cat = st.selectbox("カテゴリを選択", existing_cats, key="edit_cat_select")
        final_category = select_cat
        
        # ファイル一覧取得
        files = get_files_in_category(select_cat)
        if files:
            target_filename = st.selectbox("編集するレシピを選択", files)
            
            # 読み込みボタン
            if st.button("レシピを読み込む"):
                try:
                    with st.spinner("GitHubから取得中..."):
                        token = st.secrets["GITHUB_TOKEN"]
                        repo_name = st.secrets["REPO_NAME"]
                        g = Github(token)
                        repo = g.get_repo(repo_name)
                        file_path = f"docs/{select_cat}/{target_filename}"
                        file_content = repo.get_contents(file_path)
                        md_text = file_content.decoded_content.decode("utf-8")
                        
                        # パース実行
                        p_title, p_img, p_ing, p_steps, p_memo = parse_markdown_to_form(md_text)
                        
                        # セッション状態にセット
                        st.session_state.form_title = p_title
                        st.session_state.current_image_path = p_img
                        st.session_state.form_ingredients = p_ing
                        st.session_state.form_steps = p_steps
                        st.session_state.form_memo = p_memo
                        st.session_state.last_mode = 'edit'
                        
                        st.success("読み込みました！下のフォームで編集してください。")
                except Exception as e:
                    st.error(f"読み込み失敗: {e}")
        else:
            st.info("このカテゴリにはレシピがありません。")
    else:
        st.warning("カテゴリが見つかりません。")

# --- 入力フォーム ---
st.subheader("② レシピ内容")

with st.form("recipe_form"):
    # セッションステートから値を読み込むことで、編集時の自動入力を実現
    title = st.text_input("料理名", value=st.session_state.form_title, placeholder="例：豚の角煮")
    
    # 画像の扱い
    uploaded_file = st.file_uploader("料理の写真 (変更する場合のみアップロード)", type=['jpg', 'jpeg', 'png'])
    if st.session_state.current_image_path and not uploaded_file:
        st.caption(f"現在の画像設定: {st.session_state.current_image_path}")

    st.markdown("材料 (改行区切り)")
    raw_ingredients = st.text_area("材料", value=st.session_state.form_ingredients, height=150)

    st.markdown("手順 (改行区切り)")
    raw_steps = st.text_area("手順", value=st.session_state.form_steps, height=150)

    st.markdown("メモ (サイト上で改行反映されます)")
    raw_memo = st.text_area("メモ", value=st.session_state.form_memo)

    submit_label = "更新する" if mode == "既存レシピを編集" else "投稿する"
    submitted = st.form_submit_button(submit_label, type="primary")

# --- 送信処理 ---
if submitted:
    if not title:
        st.error("エラー：料理名を入力してください")
    elif not final_category:
        st.error("エラー：カテゴリが決まっていません")
    else:
        try:
            with st.spinner("GitHubに保存中..."):
                token = st.secrets["GITHUB_TOKEN"]
                repo_name = st.secrets["REPO_NAME"]
                g = Github(token)
                repo = g.get_repo(repo_name)

                # A. 画像処理
                image_path = st.session_state.current_image_path # デフォルトは既存パス
                
                if uploaded_file:
                    # 新しい画像がアップロードされた場合
                    image = Image.open(uploaded_file)
                    max_size = 1200
                    if max(image.size) > max_size:
                        image.thumbnail((max_size, max_size))
                    
                    img_byte_arr = io.BytesIO()
                    if image.mode in ("RGBA", "P"): image = image.convert("RGB")
                    image.save(img_byte_arr, format='JPEG', quality=80, optimize=True)
                    
                    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
                    img_filename = f"img_{timestamp}.jpg"
                    
                    repo.create_file(
                        path=f"docs/images/{img_filename}",
                        message=f"Add image for {title}",
                        content=img_byte_arr.getvalue()
                    )
                    image_path = f"../images/{img_filename}"

                # B. テキスト整形
                formatted_ingredients = format_list(raw_ingredients, is_ordered=False)
                formatted_steps = format_list(raw_steps, is_ordered=True)
                
                # メモの改行対応：通常の改行(\n)をMarkdownの強制改行(半角スペース2つ+\n)に変換
                formatted_memo = raw_memo.replace('\n', '  \n') if raw_memo else ""

                md_content = f"# {title}\n\n"
                if image_path:
                    md_content += f"![{title}]({image_path})\n\n"
                
                md_content += f"## 材料\n{formatted_ingredients}\n\n"
                md_content += f"## 手順\n{formatted_steps}\n\n"
                if formatted_memo:
                    md_content += f"## メモ\n{formatted_memo}\n"

                # C. 保存処理
                clean_category = final_category.strip().strip("/")
                
                # ファイル名が変わった場合の処理（古いファイルを消すべきだが、安全のため新規作成扱いにするか、今回は上書きロジックのみ）
                # ここでは「読み込んだファイル名」ではなく「入力されたタイトル」を正として保存します
                file_path = f"docs/{clean_category}/{title}.md"
                
                try:
                    contents = repo.get_contents(file_path)
                    repo.update_file(
                        path=file_path,
                        message=f"Update recipe: {title}",
                        content=md_content,
                        sha=contents.sha
                    )
                    action_msg = "上書き更新しました！"
                except UnknownObjectException:
                    repo.create_file(
                        path=file_path,
                        message=f"Add recipe: {title}",
                        content=md_content
                    )
                    action_msg = "新規作成しました！"
                
                # 完了処理
                st.cache_data.clear()
                
                # フォームをクリアしたい場合は以下を有効化
                # st.session_state.form_title = "" 
                
                st.balloons()
                st.success(f"完了！\n{action_msg}\nカテゴリ: {clean_category}")

        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
