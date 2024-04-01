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
        rankingsURL = "https://www.thebluealliance.com/event/2024" + eventCode + "#rankings"
        page = requests.get(rankingsURL)
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
            rawDataList = []
            for value in rankings:
                value = value.strip()
                if len(value) != 0:
                    rawDataList.append(value)
            # raw data table creation
            rawDataList = np.array(rawDataList).reshape(-1, 11).tolist()
            # the first element of the list is stored as headings for the data frame
            rawDataHeadings = rawDataList[0]
            # the rest of the list is the actual raw data
            rawData = rawDataList[1:]
            rawDf = pd.DataFrame(rawData, columns=rawDataHeadings)
            # analyzed data table creation
            # the unnecessary data columns from the raw data table are dropped
            analyzedDf = rawDf.drop(
                ['Ranking Score', 'Avg Coop', 'Avg Match', 'Record (W-L-T)', 'DQ', 'Played', 'Total Ranking Points*'],
                axis=1, inplace=False)
            # To add a win percentage to the analyzed data, I convert the win record from the raw data into a list
            # so each string can be converted into a win percentage and then add that column to the analyzed data frame
            recordList = rawDf['Record (W-L-T)'].tolist()
            i = 0
            while i < len(recordList):
                # breaks each win record into a list containing win, loss, and tie values
                recordList[i] = recordList[i].split("-")
                # computes and rounds the win percentage
                recordList[i] = (int(recordList[i][0]) / (int(recordList[i][0]) + int(recordList[i][1]) + int(recordList[i][2]))) * 100
                recordList[i] = round(recordList[i], 2)
                i = i + 1

            # adds the win percentage to the analyzed data table
            analyzedDf['Win %'] = recordList

            # concactenates the URL to use for webscraping OPR
            insightsURL = "https://www.thebluealliance.com/event/2024" + eventCode + "#event-insights"
            data = requests.get(insightsURL).text
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
            # Creates a dictionary with the team number as keys and OPRs as values
            OPRdict = {}
            for i in range(0, len(OPRlist), 2):
                OPRdict[OPRlist[i]] = OPRlist[i + 1]
            # Rounds the OPR values in the dictionary
            for team, OPR in OPRdict.items():
                OPRdict[team] = round(float(OPR), 2)
            # Converts the OPR dictionary to a dataframe and adds that dataframe to the analyzed dataframe
            OPRdf = pd.DataFrame(list(OPRdict.items()), columns=['Team', 'OPR'])
            analyzedDf = pd.merge(analyzedDf, OPRdf, how="left")
            # URL for webscraping qualitative data
            qualURL = "https://docs.google.com/spreadsheets/u/1/d/e/2PACX-1vQdEySR4HFSmPRIkghkzGFKMjrSRVu-K0P9uFterllQZFikHt1bnO-m7h-mV3B2pwamRy9jIIu5-fOa/pubhtml"
            qualDf = pd.read_html(qualURL)
            qualDf = qualDf[0]
            qualDf.columns = qualDf.iloc[0]
            # removes unnecessary qualitative data columns and headings
            qualDf = qualDf.drop(["Timestamp", 1.0], axis=1)
            qualDf = qualDf.drop(labels=[0, 1])

            # modify dataframe by combining rows with same id values so the dataframe has only one row per team
            qualDf = qualDf.groupby(['Team']).agg({'Notes': ', '.join}).reset_index()

            # converts the auto, stage and rank columns in the analyzed data to floats. This allows the predicted rank
            # to be calculated using these values
            analyzedDf = pd.merge(analyzedDf, qualDf, how="left")
            analyzedDf['Avg Auto'] = analyzedDf['Avg Auto'].astype(float)
            analyzedDf['Avg Stage'] = analyzedDf['Avg Stage'].astype(float)
            analyzedDf['Rank'] = analyzedDf['Rank'].astype(float)
            # a weighted average is calculated to rank the teams by a predicted column
            analyzedDf = analyzedDf.sort_values(by=['OPR'], ascending=False).reset_index(drop=True)
            analyzedDf['Prediction'] = round((((analyzedDf['OPR']) * 0.35) + ((analyzedDf['Avg Auto']) * 0.3) + (
                    (analyzedDf['Avg Stage']) * 0.1) + (abs(analyzedDf.index - analyzedDf['Rank'])) * 0.25) / 4,
                                               2)
            # the rank column is replaced with the prediction column and the data is sorted by their prediction
            analyzedDf = analyzedDf.drop(['Rank'], axis=1)
            analyzedDf = analyzedDf.sort_values(by=['Prediction'], ascending=False)
            analyzedDf = analyzedDf.reset_index(drop=True)

            # the analyzed dataframe html is created and its rows are centered
            global analyzed
            analyzed = analyzedDf.to_html(classes=["table-bordered", "table-striped", "table-hover"])
            analyzed = analyzed.replace('<tr>', '<tr align="center">')

            # the raw dataframe html is created and its rows are centered
            global html
            html = rawDf.to_html(classes=["table-bordered", "table-striped", "table-hover"])
            html = html.replace('<tr>', '<tr align="center">')

            # returns the raw data html template with the event name and data table for display
            return render_template('rawData.html', eventName=eventName, rawDataTable=html)

# app analyzed data page
# method returns the html file analyzedData.html
# this method runs when the user clicks on the analyzed data button from the raw data page
@app.route('/analyzedData.html', methods=['GET', 'POST'])
def analyzedData():
    return render_template('analyzedData.html', analyzedDataTable=analyzed, eventName=eventName)

# app raw data page route and method if accessed from the analyzed data page
# method returns the html file rawData.html
# this method runs when returning to the raw data page after visiting the analyzed data page
# so the raw data table isn't recreated
@app.route('/rawDataDisplay.html', methods=['GET', 'POST'])
def rawDataDisplay():
    return render_template('rawData.html', rawDataTable=html, eventName=eventName)

# runs the flask app
if __name__ == '__main__':
   app.run()


