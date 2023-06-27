import os
import json
import shutil
import pypdf
import glob
import requests
from datetime import datetime
from flask import Flask, request, abort

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, TemplateSendMessage, CarouselTemplate, CarouselColumn)

app = Flask(__name__)

ABS_PATH = os.path.dirname(os.path.abspath(__file__))
with open(ABS_PATH+'/conf.json', 'r') as f:
    CONF_DATA = json.load(f)

LINE_CHANNEL_ACCESS_TOKEN = CONF_DATA["CHANNEL_ACCESS_TOKEN"]
LINE_CHANNEL_SECRET = CONF_DATA["CHANNEL_SECRET"]

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

waiting_for_pdf = False

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']

    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

user_states = {}

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    response_text = process_message(event.message.text, user_id)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response_text))

def delete_database():
    directory_to_delete = "database"
    shutil.rmtree(directory_to_delete)

def concatenate_pdfs():
    pdf_files = []
    files = glob.glob("data/*.pdf")
    for file in files:
        pdf_files.append(file)

    merger = pypdf.PdfMerger()

    for pdf_file in pdf_files:
      merger.append(pdf_file)

    merger.write("data/main/submit.pdf")
    merger.close()

def convert_url(original_url):
    # Google DriveのURLを判別
    if 'drive.google.com' in original_url:
        # Google Driveの共有URLからファイルIDを取得
        file_id = original_url.split('/')[-2]

        # ダウンロード可能なURLに変換
        download_url = f'https://drive.google.com/uc?export=download&id={file_id}'

    # DropboxのURLを判別
    elif 'dropbox.com' in original_url:
        # DropboxのURLは末尾が"dl=0"になっていることが多い。これを"dl=1"に変更すると直接ダウンロードできる
        download_url = original_url.replace('dl=0', 'dl=1')

    else:
        # その他のURL形式についてはそのまま返す（またはエラーメッセージを返すなど）
        download_url = original_url

    return download_url


from keiojp import process_message as original_process_message

waiting_for_pdf = False

def process_message(message_text, user_id):
    if user_id not in user_states:
        user_states[user_id] = False

    waiting_for_pdf = user_states[user_id]
    
    if message_text == "データベース更新":
        user_states[user_id] = True
        response_text = "データベースを更新するPDFのURLを送信してください。\n GoogleDriveの場合:共有→共有可能なリンクをコピー(リンクを知っている全員がアクセス可)\n Dropboxの場合:共有→リンクを作成"
        datainput = False

    elif waiting_for_pdf:
        try:
            message_text = convert_url(message_text)
            response = requests.get(message_text, stream=True)
            response.raise_for_status()
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            with open(f'data/{user_id}_{timestamp}_new_file.pdf', 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            user_states[user_id] = False
            datainput = True
        except requests.exceptions.RequestException as e:
            response_text = "エラーが発生しました: " + str(e)
            user_states[user_id] = False
            datainput = False
        except Exception as e:
            response_text = "予期せぬエラーが発生しました: " + str(e)
            user_states[user_id] = False
            datainput = False
            
        if datainput:
            delete_database()
            concatenate_pdfs()
            response_text = "データベースが正常に更新されました。"

    else:
        response_text = original_process_message(message_text)
    
    return response_text


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
