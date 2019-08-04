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
import base64
import os
# from email.mime.multipart import MIMEMultipart
# from email.mime.text      import MIMEText
# from email.mime.image     import MIMEImage
# from email.utils          import formatdate

# sendgridでのメール送信に必要
import sendgrid
import sendgrid.helpers.mail as sg_helper


class SendGridAPI:
    def __init__(self):
        if os.environ['SENDGRID_APIKEY']:
            self.__apikey = os.environ['SENDGRID_APIKEY']
            self.__FROM_ADDRESS = os.environ['MAIL_FROM']
            self.__TO_ADDRESS = os.environ['MAIL_TO']
            self.__SUBJECT = 'sendgridメールてすと'
            self.__BODY = 'pythonでメール送信する'
            self.inited = True
            self.__sg = sendgrid.SendGridAPIClient(apikey=self.__apikey)
        else:
            self.inited = False

    def __prepare_image(self):
        with open('figure.png', 'rb') as f:
            encoded = base64.b64encode(f.read()).decode()
        attachment = sg_helper.Attachment()
        attachment.content  = encoded
        attachment.type = 'image/png'
        attachment.filename = 'figure.png'
        attachment.disposition = 'attachment'
        # attachment.set_content_id = 1 # comment out しても動く
        return attachment

    def send_mail(self):
        message = sg_helper.Mail(
            from_email=sg_helper.Email(self.__FROM_ADDRESS),
            subject=self.__SUBJECT,
            to_email=sg_helper.Email(self.__TO_ADDRESS),
            content=sg_helper.Content("text/html", '<h1>{body}<h1>'.format(body='sendgridテスト'))
        )
        message.add_attachment(self.__prepare_image())

        response = self.__sg.client.mail.send.post(request_body=message.get())
        print(response.status_code)
        print(response.body)
        print(response.headers)
