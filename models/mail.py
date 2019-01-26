# # # # # # # # # # # # # # #
#         参考サイト         #
# # # # # # # # # # # # # # #
# GmailAPI公式
# https://developers.google.com/gmail/api/quickstart/python
# Pythonを使ってGmail APIからメールを取得する(認証処理の参考)
# https://qiita.com/orikei/items/73dc1ccc95d1872ab1cf

# 一般的なmail送信処理 詳しい 一番役に立った
# http://thinkami.hatenablog.com/entry/2016/06/09/062528
# Gmail送信処理
# https://qiita.com/okhrn/items/630a87ce1a44778bbeb1

# # # # # # # # # # # # # # #
#       module import       #
# # # # # # # # # # # # # # #
# Gmail認証に必要
from __future__                import print_function
from googleapiclient.discovery import build
from httplib2                  import Http
from oauth2client              import file, client, tools
import os

# メール送信に必要
import smtplib
from email.mime.text import MIMEText
from email.utils     import formatdate
import base64

# エラー処理のためにやむを得ずimport
import googleapiclient as gapi_client
import traceback

# # # # # # # # # # # # # # #
#     class definition      #
# # # # # # # # # # # # # # #
class GmailAPI:
    def __init__(self):
        # scopeの選択方法
        # https://developers.google.com/gmail/api/auth/scopes
        # If modifying these scopes, delete the file token.json.
        self.__SCOPES = 'https://www.googleapis.com/auth/gmail.send'

    ### AUTHENTICTION
    def ConnectGmail(self):
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        store = file.Storage('token.json') # token.json は touch で作成
        creds = store.get()
        if not creds or creds.invalid:
            flow = client.flow_from_clientsecrets('gmail_credentials.json', self.__SCOPES)
            creds = tools.run_flow(flow, store)
        service = build('gmail', 'v1', http=creds.authorize(Http()))

        return service

    def get_label_list(self):
        service = self.ConnectGmail()
        # Call the Gmail API
        results = service.users().labels().list(userId='me').execute()
        labels  = results.get('labels', [])

        if not labels:
            print('No labels found.')
        else:
            print('Labels:')
            for label in labels:
                print(label['name'])

    def send(self, msg, mail_from):
        ''' send mail with GmailAPI '''
        service = self.ConnectGmail()
        try:
            result = service.users().messages().send(
                userId=mail_from,
                body=msg
            ).execute()

            print("Message Id: {}".format(result["id"]))

        except gapi_client.errors.HttpError:
            print("------start trace------")
            traceback.print_exc()
            print("------end trace------")

class Mail:
    def __init__(self):
        self.FROM_ADDRESS = os.environ['MAIL_FROM']
        self.__TO_ADDRESS   = os.environ['MAIL_TO']
        # self.__BCC          = ''
        self.__SUBJECT      = 'GmailのSMTPサーバ経由てすと'
        self.__BODY         = 'pythonでメール送信する'

    def create_message(self):
        ''' メールobject生成 '''
        msg = MIMEText(self.__BODY)
        msg['Subject'] = self.__SUBJECT
        msg['From']    = self.FROM_ADDRESS
        msg['To']      = self.__TO_ADDRESS
        # msg['Bcc']     = self.__BCC
        msg['Date']    = formatdate()

        # GmailAPIでsendする時は、この変換処理が必須
        byte_msg            = msg.as_string().encode(encoding="UTF-8")
        byte_msg_b64encoded = base64.urlsafe_b64encode(byte_msg)
        str_msg_b64encoded  = byte_msg_b64encoded.decode(encoding="UTF-8")
        return {"raw": str_msg_b64encoded}

# # # # # # # # # # # # # # #
#           MAIN            #
# # # # # # # # # # # # # # #
if __name__ == '__main__':
    gmail_test  = GmailAPI()
    mail_module = Mail()
    msg         = mail_module.create_message()

    gmail_test.send(msg=msg, mail_from=mail_module.FROM_ADDRESS)
    # gmail_test.get_label_list()
