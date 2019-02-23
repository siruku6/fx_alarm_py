from models   import mailer
from datetime import datetime
import matplotlib.pyplot as plt
import numpy             as np

def make_figure():
    fig  = plt.figure()
    axis = fig.add_subplot(111)
    data = np.random.rand(10)
    axis.plot(data)
    plt.savefig('figure.png')

if __name__ == '__main__':
    make_figure()
    sendgrid_ins = mailer.SendGridAPI()
    sendgrid_ins.send_mail()
