# import libraries
import pandas as pd
import numpy as np
from flask import render_template
from flask import Flask, request
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# app home page route and method
# / is the address for the home page
# method returns the home page html file index.html
@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')

# app raw data page route and method
# method returns the html file rawData.html
# this method only runs when an event code is entered in order to load the data table.
# if routing from the analyzed data page, the raw data display method is run to display, not recreate the table
@app.route('/rawData.html', methods = ['GET','POST'])
def rawData():
    # retrieves the event code from the home page
    eventCode = request.form['eventCode']

    # if the event code is empty, the user is routed to the empty event code page
    if eventCode == '':
        return render_template('emptyEventCode.html')
    else:
        # catching for uppercase codes or codes with extra spaces
        eventCode = eventCode.strip()
        eventCode = eventCode.lower()
        # concatenates the web scraping URL out of the event code
        URL = "https://www.thebluealliance.com/event/2024" + eventCode + "#rankings"
        page = requests.get(URL)
        # creates a string that contains the page html
        # if the page html returns a 404 error, the event code was invalid
        # the user is routed to the invalid event code page
        pageContent = str(page)
        if 'Response [404]' in pageContent:
            return render_template('invalidEventCode.html')
        else:
            soup = BeautifulSoup(page.content, "html.parser")
            # the event name is treated as a global variable so it can be accessed by the analyzed data page
            global eventName
            eventName = soup.find(id="event-name").text
            # isolates the data table in the html code and converts it to text
            rankings = soup.find(id="rankingsTable").text
            # breaks the data into individual strings
            rankings = rankings.split("\n")
            # appends all non-empty strings from the data to the data list with excess whitespace removed
            # This allows the data to be formatted as a table
            dataList = []
            for value in rankings:
                value = value.strip()
                if len(value) != 0:
                    dataList.append(value)
            # raw data table creation
            newList = np.array(dataList).reshape(-1, 11).tolist()
            # the first element of the list is stored as headings for the data frame
            headings = newList[0]
            # the rest of the list is the actual raw data
            data = newList[1:]
            rawData = pd.DataFrame(data, columns=headings)
            # analyzed data table creation
            # the unnecessary data columns from the raw data table are dropped
            analyzedData = rawData.drop(
                ['Ranking Score', 'Avg Coop', 'Avg Match', 'Record (W-L-T)', 'DQ', 'Played', 'Total Ranking Points*'],
                axis=1, inplace=False)
            # To add a win percentage to the analyzed data, I convert the win record from the raw data into a list
            # so each string can be converted into a win percentage and then add that column to the analyzed data frame
            record = rawData['Record (W-L-T)'].tolist()
            i = 0
            while i < len(record):
                # breaks each win record into a list containing win, loss, and tie values
                record[i] = record[i].split("-")
                # computes and rounds the win percentage
                record[i] = (int(record[i][0]) / (int(record[i][0]) + int(record[i][1]) + int(record[i][2]))) * 100
                record[i] = round(record[i], 2)
                i = i + 1

            # adds the win percentage to the analyzed data table
            analyzedData['Win %'] = record

            # concactenates the URL to use for webscraping OPR
            URL2 = "https://www.thebluealliance.com/event/2024" + eventCode + "#event-insights"
            data = requests.get(URL2).text
            soup = BeautifulSoup(data, 'html.parser')
            soup = soup.prettify()

            # parsing algorithm for the OPR data, which could not be parsed via beautiful soup.
            # a list of all mentions of OPR is created and the OPR data is isolated
            soup = soup.split('OPR')
            OPR = soup[5]
            OPR = OPR.split("]]")
            OPR = OPR[0].split(",")
            OPRlist = []
            # additional characters are removed, providing just the team numbers and OPRs
            for x in OPR:
                x = x.replace("[", " ")
                x = x.replace("]", " ")
                x = x.replace("\"", " ")
                x = x.replace("\'", " ")
                x = x.replace(":", " ")
                OPRlist.append(x.strip())

            a = 1
            while a < len(OPRlist):
                if a % 2 != 0:
                    OPRlist[a] = round(float(OPRlist[a]), 2)
                a = a + 1

            OPRdict = {}
            for i in range(0, len(OPRlist), 2):
                OPRdict[OPRlist[i]] = OPRlist[i + 1]

            OPRdf = pd.DataFrame(list(OPRdict.items()), columns=['Team', 'OPR'])
            analyzedData = pd.merge(analyzedData, OPRdf, how="left")

            URL = "https://docs.google.com/spreadsheets/u/1/d/e/2PACX-1vQdEySR4HFSmPRIkghkzGFKMjrSRVu-K0P9uFterllQZFikHt1bnO-m7h-mV3B2pwamRy9jIIu5-fOa/pubhtml"
            # concoctanates the URL to use for webscraping
            qualData = pd.read_html(URL)
            qualData = qualData[0]
            qualData.columns = qualData.iloc[0]
            qualData = qualData.drop(["Timestamp", 1.0], axis=1)
            qualData = qualData.drop(labels=[0, 1])

            # create new DataFrame by combining rows with same id values
            qualData = qualData.groupby(['Team']).agg({'Notes': ', '.join}).reset_index()

            analyzedData = pd.merge(analyzedData, qualData, how="left")
            analyzedData['Avg Auto'] = analyzedData['Avg Auto'].astype(float)
            analyzedData['Avg Stage'] = analyzedData['Avg Stage'].astype(float)
            analyzedData['Rank'] = analyzedData['Rank'].astype(float)

            analyzedData = analyzedData.sort_values(by=['OPR'], ascending=False).reset_index(drop=True)
            analyzedData['Prediction'] = round((((analyzedData['OPR']) * 0.35) + ((analyzedData['Avg Auto']) * 0.3) + (
                    (analyzedData['Avg Stage']) * 0.1) + (abs(analyzedData.index - analyzedData['Rank'])) * 0.25) / 4,
                                               2)
            analyzedData = analyzedData.drop(['Rank'], axis=1)
            analyzedData = analyzedData.sort_values(by=['Prediction'], ascending=False)
            analyzedData = analyzedData.reset_index(drop=True)
            global analyzed
            analyzed = analyzedData.to_html(classes=["table-bordered", "table-striped", "table-hover"])
            analyzed = analyzed.replace('<tr>', '<tr align="center">')
            global html
            html = rawData.to_html(classes=["table-bordered", "table-striped", "table-hover"])
            html = html.replace('<tr>', '<tr align="center">')

            return render_template('rawData.html', eventName=eventName, rawDataTable=html)

            #return flask.send_from_directory(".", path="templates/rawData.html")


@app.route('/analyzedData.html', methods=['GET', 'POST'])
def analyzedData():
    return render_template('analyzedData.html', analyzedDataTable=analyzed, eventName=eventName)

@app.route('/rawDataDisplay.html', methods=['GET', 'POST'])
def rawDataDisplay():
    return render_template('rawData.html', rawDataTable=html, eventName=eventName)


if __name__ == '__main__':
   app.run()


