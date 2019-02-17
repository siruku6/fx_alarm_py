# GmailAPI公式
# https://developers.google.com/gmail/api/quickstart/python

# Pythonを使ってGmail APIからメールを取得する(認証処理の参考)
# https://qiita.com/orikei/items/73dc1ccc95d1872ab1cf

# 一般的なmail送信処理 詳しい 一番役に立った
# http://thinkami.hatenablog.com/entry/2016/06/09/062528

# Gmail送信処理
# https://qiita.com/okhrn/items/630a87ce1a44778bbeb1

# エンコード方法わかるかも
# https://docs.python.jp/3.5/library/email.encoders.html?highlight=encoders

# 画像添付方法はここを参考にした
# https://qiita.com/obana2010/items/579f54c414d65b939457

# メール送信に必要
# import smtplib # Gmail経由ならいらない
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email.mime.image     import MIMEImage
from email.utils          import formatdate

# Gmail認証に必要
from googleapiclient.discovery import build
from httplib2                  import Http
from oauth2client              import file, client, tools
import os

# sendgridでのメール送信に必要
import sendgrid
import sendgrid.helpers.mail as sg_helper

# エラー処理のためにやむを得ずimport
import googleapiclient as gapi_client
import traceback

class GmailAPI:
    def __init__(self):
        if os.path.isfile('gmail_credentials.json_bk') and os.path.isfile('token.json'):
            # scopeの選択方法
            # https://developers.google.com/gmail/api/auth/scopes
            # If modifying these scopes, delete the file token.json.
            self.__SCOPES       = 'https://www.googleapis.com/auth/gmail.send'
            self.__FROM_ADDRESS = os.environ['MAIL_FROM']
            self.__TO_ADDRESS   = os.environ['MAIL_TO']
            # self.__BCC          = ''
            self.__SUBJECT      = 'GmailのSMTPサーバ経由てすと'
            self.__BODY         = 'pythonでメール送信する'
            self.inited         = True
        else:
            self.inited         = False

    ### AUTHENTICTION
    def __ConnectGmail(self):
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
        service = self.__ConnectGmail()
        results = service.users().labels().list(userId='me').execute()
        labels  = results.get('labels', [])

        if not labels:
            print('No labels found.')
        else:
            print('Labels:')
            for label in labels:
                print(label['name'])

    def __create_message(self):
        ''' メールobject生成 '''
        msg = MIMEText(self.__BODY)
        msg['Subject'] = self.__SUBJECT
        msg['From']    = self.__FROM_ADDRESS
        msg['To']      = self.__TO_ADDRESS
        # msg['Bcc']     = self.__BCC
        msg['Date']    = formatdate()

        # GmailAPIでsendする時は、この変換処理が必須
        byte_msg            = msg.as_string().encode(encoding="UTF-8")
        byte_msg_b64encoded = base64.urlsafe_b64encode(byte_msg)
        str_msg_b64encoded  = byte_msg_b64encoded.decode(encoding="UTF-8")
        return { "raw": str_msg_b64encoded }

    def __create_message_with_image(self):
        ''' 添付画像付きメッセージを生成 '''
        msg = MIMEMultipart()
        msg['Subject'] = self.__SUBJECT
        msg['From']    = self.__FROM_ADDRESS
        msg['To']      = self.__TO_ADDRESS
        msg['Date']    = formatdate()
        msg.attach(MIMEText(self.__BODY))

        # open(path, mode='rb') の理由
        # https://stackoverflow.com/questions/42339876/error-unicodedecodeerror-utf-8-codec-cant-decode-byte-0xff-in-position-0-in
        with open('./figure.png', mode='rb') as f:
            # email.mime: メールと MIME オブジェクトを一から作成
            # https://docs.python.org/ja/3.7/library/email.mime.html
            atchment_file = MIMEImage(f.read(), _subtype='png')

        atchment_file.set_param('name', 'figure.png')
        atchment_file.add_header('Content-Dispositon','attachment',filename='figure.png')
        msg.attach(atchment_file)

        # エンコード方法
        # http://thinkami.hatenablog.com/entry/2016/06/10/065731
        byte_msg            = msg.as_string().encode(encoding="UTF-8")
        byte_msg_b64encoded = base64.urlsafe_b64encode(byte_msg)
        str_msg_b64encoded  = byte_msg_b64encoded.decode(encoding="UTF-8")
        return { "raw": str_msg_b64encoded }

    def send(self):
        ''' send mail with GmailAPI '''
        service = self.__ConnectGmail()
        msg     = self.__create_message_with_image()
        try:
            result  = service.users().messages().send(
                userId=self.__FROM_ADDRESS,
                body=msg
            ).execute()

            print("Message Id: {}".format(result["id"]))

        except gapi_client.errors.HttpError:
            print("------start trace------")
            traceback.print_exc()
            print("------end trace------")

class SendGridAPI:
    def __init__(self):
        if os.environ['SENDGRID_APIKEY']:
            self.__apikey       = os.environ['SENDGRID_APIKEY']
            self.__FROM_ADDRESS = os.environ['MAIL_FROM']
            self.__TO_ADDRESS   = os.environ['MAIL_TO']
            self.__SUBJECT      = 'sendgridメールてすと'
            self.__BODY         = 'pythonでメール送信する'
            self.inited         = True

            self.__sg           = sendgrid.SendGridAPIClient(apikey=self.__apikey)
        else:
            self.inited         = False

    def __prepare_image(self):
        with open('figure.png', 'rb') as f:
            encoded = base64.b64encode(f.read()).decode()
        attachment = sg_helper.Attachment()
        attachment.content     = encoded
        attachment.type        = 'image/png'
        attachment.filename    = 'figure.png'
        attachment.disposition = 'attachment'
        attachment.set_content_id = 1
        return attachment

    def send_mail(self):
        message = sg_helper.Mail(
            from_email=sg_helper.Email(self.__FROM_ADDRESS),
            subject=self.__SUBJECT,
            to_email=sg_helper.Email(self.__TO_ADDRESS),
            content=sg_helper.Content("text/html", '<h1>{body}<h1>'.format(body='sendgridテスト'))
        )
        # message.add_attachment(self.__prepare_image())

        response = self.__sg.client.mail.send.post(request_body=message.get())
        print(response.status_code)
        print(response.body)
        print(response.headers)

if __name__ == '__main__':
    gmail_test = GmailAPI()
    if gmail_test.inited:
        print('success')
        # gmail_test.send()
    else:
        sendgrid_ins = SendGridAPI()
        sendgrid_ins.send_mail()
