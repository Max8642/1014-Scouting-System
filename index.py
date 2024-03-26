# import libraries
import pandas as pd
import numpy as np
import flask
from flask import render_template
from flask import Flask, request


import requests
from bs4 import BeautifulSoup


app = Flask(__name__)

@app.route('/')
def index():
   #return render_template('index.html')  # this line only displays files in the templates sub directory.  To display from other directories, see below
   return flask.send_from_directory(".", path="Templates/index.html")




@app.route('/data.html', methods=["POST"])
def data():
    eventCode = request.form['eventCode']
    URL = "https://www.thebluealliance.com/event/2024" + eventCode + "#rankings"

    page = requests.get(URL)

    soup = BeautifulSoup(page.content, "html.parser")

    rankings = soup.find(id="rankingsTable").text
    rankings = rankings.split("\n")
    newList = []
    for x in rankings:
        x = x.strip()
        if len(x) != 0:
            newList.append(x)

    newList = np.array(newList).reshape(-1, 11).tolist()
    df = pd.DataFrame(newList)

    # convert dataframe to html
    html = df.to_html()

    # Option to print output to terminal
    # print(html)

    # open file and write
    file = open("Templates/data.html", 'w')
    file.write(html)
    file.close
   #return render_template('index.html')  # this line only displays files in the templates sub directory.  To display from other directories, see below
    return flask.send_from_directory(".", path="Templates/data.html")

if __name__ == '__main__':
   app.run()


